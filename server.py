#!/usr/bin/env python3
"""Local CARSKY helper. Only listens on localhost."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HOST = "127.0.0.1"
PORT = 8765
ROOT = Path(__file__).resolve().parent

# Optional extension: deleting docaslails/ disables only extended system
# fingerprinting. Core detection, restart and app management still run.
try:
    from docaslails.detection import inspect_android
except (ImportError, OSError):
    inspect_android = None


def run(args, timeout=8):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def checked(args, timeout=12):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode == 0, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return False, "", f"Required command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return False, "", "The device did not respond in time."


def android_devices():
    output = run(["adb", "devices", "-l"])
    found = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2 or parts[1] != "device":
            continue
        serial = parts[0]
        model = run(["adb", "-s", serial, "shell", "getprop", "ro.product.model"]) or "Android device"
        maker = run(["adb", "-s", serial, "shell", "getprop", "ro.product.manufacturer"]) or "Android"
        item = {"id": serial, "platform": "android", "brand": maker, "model": model,
                "name": model, "authorized": True}
        if inspect_android:
            try:
                item["system_details"] = inspect_android(serial, run)
            except Exception:
                item["system_details"] = {"status": "Extended detection failed"}
        else:
            item["system_details"] = {"status": "Optional docaslails detector not installed"}
        found.append(item)
    return found


def apple_devices():
    ids = run(["idevice_id", "-l"])
    found = []
    for udid in ids.splitlines():
        if not udid.strip():
            continue
        product = run(["ideviceinfo", "-u", udid, "-k", "ProductType"]) or "iPhone (model unavailable)"
        name = run(["ideviceinfo", "-u", udid, "-k", "DeviceName"]) or "iPhone"
        found.append({"id": udid.strip(), "platform": "apple", "brand": "Apple",
                      "model": product, "name": name, "authorized": True,
                      "system_details": {"status": "Apple device reported through trusted pairing",
                                         "model_identifier": product}})
    return found


def get_android_device(serial):
    return next((d for d in android_devices() if d["id"] == serial), None)


def installed_user_apps(serial):
    ok, output, error = checked(["adb", "-s", serial, "shell", "pm", "list", "packages", "-3"])
    if not ok:
        raise RuntimeError(error or "Could not read installed apps.")
    return sorted({line.strip().replace("package:", "", 1) for line in output.splitlines()
                   if line.strip().startswith("package:")})


class Handler(BaseHTTPRequestHandler):
    def send_json(self, code, data):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def read_body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size > 4096:
            raise ValueError("Request too large")
        return json.loads(self.rfile.read(size) or b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/":
            try:
                raw = (ROOT / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except OSError:
                self.send_json(500, {"error": "index.html is missing"})
        elif route == "/api/devices":
            self.send_json(200, {
                "devices": android_devices() + apple_devices(),
                "tools": {
                    "adb": bool(shutil.which("adb")),
                    "libimobiledevice": bool(shutil.which("idevice_id") and shutil.which("ideviceinfo")),
                    "extended_detection": inspect_android is not None
                }
            })
        elif route == "/api/apps":
            serial = parse_qs(parsed.query).get("id", [""])[0]
            if not serial or not get_android_device(serial):
                self.send_json(409, {"error": "Select a connected, authorized Android device."})
                return
            try:
                self.send_json(200, {"apps": installed_user_apps(serial)})
            except RuntimeError as e:
                self.send_json(502, {"error": str(e)})
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        route = urlparse(self.path).path
        try:
            body = self.read_body()
            device_id = str(body.get("id", ""))
            platform = str(body.get("platform", ""))
            if not device_id or platform not in ("android", "apple"):
                raise ValueError("Choose a detected device first")

            if route == "/api/restart":
                current = android_devices() if platform == "android" else apple_devices()
                if not any(d["id"] == device_id for d in current):
                    self.send_json(409, {"error": "That device is no longer detected. Reconnect it and refresh."})
                    return
                if platform == "android":
                    ok, _, error = checked(["adb", "-s", device_id, "reboot"], timeout=8)
                    if not ok:
                        self.send_json(502, {"error": error or "Android did not accept the restart command."})
                        return
                    self.send_json(200, {"ok": True, "message": "Restart command accepted by Android."})
                else:
                    if not shutil.which("idevicediagnostics"):
                        self.send_json(501, {"error": "idevicediagnostics is not installed."})
                        return
                    ok, _, error = checked(["idevicediagnostics", "-u", device_id, "restart"], timeout=12)
                    if not ok:
                        self.send_json(403, {"error": error or "The paired iPhone did not accept the restart command."})
                        return
                    self.send_json(200, {"ok": True, "message": "Restart command accepted by the iPhone."})
                return

            if route == "/api/uninstall":
                if platform != "android" or not get_android_device(device_id):
                    self.send_json(409, {"error": "App removal requires a connected, authorized Android device."})
                    return
                package = str(body.get("package", ""))
                if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package):
                    raise ValueError("Invalid Android package name.")
                if package not in installed_user_apps(device_id):
                    self.send_json(403, {"error": "Only listed user-installed apps can be removed. System apps are blocked."})
                    return
                ok, output, error = checked(["adb", "-s", device_id, "uninstall", package], timeout=30)
                if not ok or "Success" not in output:
                    self.send_json(502, {"error": error or output or "Android did not uninstall the app."})
                    return
                self.send_json(200, {"ok": True, "message": "Uninstalled " + package})
                return

            self.send_json(404, {"error": "Not found"})
        except (ValueError, json.JSONDecodeError) as e:
            self.send_json(400, {"error": str(e)})
        except RuntimeError as e:
            self.send_json(502, {"error": str(e)})
        except Exception:
            self.send_json(500, {"error": "Unexpected local helper error."})

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print(f"CARSKY helper running at http://{HOST}:{PORT}")
    print("Keep this terminal open while using CARSKY.")
    HTTPServer((HOST, PORT), Handler).serve_forever()
