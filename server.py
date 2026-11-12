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


def android_inventory(serial):
    """Read public device details and inventory accessible script filenames."""
    commands = {
        "manufacturer": ["shell","getprop","ro.product.manufacturer"],
        "brand": ["shell","getprop","ro.product.brand"],
        "model": ["shell","getprop","ro.product.model"],
        "device": ["shell","getprop","ro.product.device"],
        "android_version": ["shell","getprop","ro.build.version.release"],
        "sdk": ["shell","getprop","ro.build.version.sdk"],
        "fingerprint": ["shell","getprop","ro.build.fingerprint"],
        "abi": ["shell","getprop","ro.product.cpu.abi"],
        "screen": ["shell","wm","size"],
        "density": ["shell","wm","density"],
        "memory": ["shell","cat","/proc/meminfo"],
        "storage": ["shell","df","-h","/data"],
        "battery": ["shell","dumpsys","battery"],
        "kernel": ["shell","uname","-a"],
    }
    data = {}
    for key, args in commands.items():
        ok, out, err = checked(["adb","-s",serial] + args, timeout=10)
        data[key] = out if ok else (err or "Not available")
    scan = 'for d in /sdcard/Download /sdcard/Documents /sdcard/CARSKY-scripts; do [ -d "$d" ] && find "$d" -maxdepth 3 -type f -name "*.sh" 2>/dev/null; done'
    ok, out, _ = checked(["adb","-s",serial,"shell",scan], timeout=12)
    data["accessible_scripts"] = out.splitlines() if ok and out else []
    data["script_policy"] = "Filenames only; existing scripts are never executed automatically."
    return data


def build_diagnostic_script(device):
    model = re.sub(r"[^A-Za-z0-9 _.-]", "", str(device.get("model","Android device")))[:80]
    return """#!/system/bin/sh
# CARSKY generated read-only diagnostic script
# Device profile: %s
set -u
OUT="/sdcard/Download/CARSKY-device-report.txt"
{
 echo "CARSKY DEVICE REPORT"
 date 2>/dev/null
 echo "MANUFACTURER: $(getprop ro.product.manufacturer)"
 echo "BRAND: $(getprop ro.product.brand)"
 echo "MODEL: $(getprop ro.product.model)"
 echo "DEVICE: $(getprop ro.product.device)"
 echo "ANDROID: $(getprop ro.build.version.release)"
 echo "SDK: $(getprop ro.build.version.sdk)"
 echo "BUILD: $(getprop ro.build.fingerprint)"
 echo "ABI: $(getprop ro.product.cpu.abi)"
 echo "SCREEN:"; wm size 2>&1; wm density 2>&1
 echo "MEMORY:"; cat /proc/meminfo 2>&1
 echo "STORAGE:"; df -h /data 2>&1
 echo "BATTERY:"; dumpsys battery 2>&1
 echo "KERNEL:"; uname -a 2>&1
 echo "ACCESSIBLE SCRIPT FILES:"
 for d in /sdcard/Download /sdcard/Documents /sdcard/CARSKY-scripts; do
  [ -d "$d" ] && find "$d" -maxdepth 3 -type f -name "*.sh" 2>/dev/null
 done
} > "$OUT" 2>&1
echo "Report saved to $OUT"
""" % model


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
        elif route == "/api/inspect":
            serial = parse_qs(parsed.query).get("id", [""])[0]
            if not serial or not get_android_device(serial):
                self.send_json(409, {"error":"Select a connected, authorized Android device."})
                return
            device = get_android_device(serial)
            self.send_json(200, {"device":device,"inventory":android_inventory(serial),
                                 "script":build_diagnostic_script(device)})
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

            if route == "/api/script/run":
                if platform != "android" or not get_android_device(device_id):
                    self.send_json(409, {"error":"Generated scripts require a connected, authorized Android device."})
                    return
                script = build_diagnostic_script(get_android_device(device_id))
                local_script = ROOT / "carsky_generated_diagnostic.sh"
                try:
                    local_script.write_text(script, encoding="utf-8")
                    ok, _, error = checked(["adb","-s",device_id,"push",str(local_script),
                                            "/data/local/tmp/carsky_generated_diagnostic.sh"], timeout=20)
                    if not ok:
                        self.send_json(502, {"error":error or "Could not transfer the script."})
                        return
                    ok, output, error = checked(["adb","-s",device_id,"shell","sh",
                                                 "/data/local/tmp/carsky_generated_diagnostic.sh"], timeout=45)
                    if not ok:
                        self.send_json(502, {"error":error or output or "Script failed; phone was not restarted."})
                        return
                    reboot_ok, _, reboot_error = checked(["adb","-s",device_id,"reboot"], timeout=10)
                    if not reboot_ok:
                        self.send_json(502, {"error":"Script completed, but restart was not accepted: " + (reboot_error or "unknown error")})
                        return
                    self.send_json(200, {"ok":True,"message":"Diagnostic script completed. The phone accepted the restart command.",
                                         "report":"/sdcard/Download/CARSKY-device-report.txt"})
                finally:
                    try: local_script.unlink(missing_ok=True)
                    except OSError: pass
                return

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
