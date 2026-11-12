#!/usr/bin/env python3
"""Local CARSKY helper. Only listens on localhost."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import shutil
import subprocess
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8765


def run(args, timeout=8):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


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
        found.append({"id": serial, "platform": "android", "brand": maker, "model": model.strip(), "name": model.strip(), "authorized": True})
    return found


def apple_devices():
    ids = run(["idevice_id", "-l"])
    found = []
    for udid in ids.splitlines():
        if not udid.strip():
            continue
        product = run(["ideviceinfo", "-u", udid, "-k", "ProductType"]) or "iPhone (model unavailable)"
        name = run(["ideviceinfo", "-u", udid, "-k", "DeviceName"]) or "iPhone"
        found.append({"id": udid.strip(), "platform": "apple", "brand": "Apple", "model": product.strip(), "name": name.strip(), "authorized": True})
    return found


class Handler(BaseHTTPRequestHandler):
    def send_json(self, code, data):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if urlparse(self.path).path == "/api/devices":
            self.send_json(200, {
                "devices": android_devices() + apple_devices(),
                "tools": {
                    "adb": bool(shutil.which("adb")),
                    "libimobiledevice": bool(shutil.which("idevice_id") and shutil.which("ideviceinfo"))
                }
            })
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/restart":
            self.send_json(404, {"error": "Not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 2048:
                raise ValueError("Request too large")
            body = json.loads(self.rfile.read(size) or b"{}")
            device_id = str(body.get("id", ""))
            platform = str(body.get("platform", ""))
            if not device_id or platform not in ("android", "apple"):
                raise ValueError("Choose a detected device first")

            current = android_devices() if platform == "android" else apple_devices()
            if not any(d["id"] == device_id for d in current):
                self.send_json(409, {"error": "That device is no longer detected. Reconnect it and refresh."})
                return

            if platform == "android":
                result = run(["adb", "-s", device_id, "reboot"], timeout=5)
                # adb reboot normally closes the connection immediately; an empty result is expected.
                self.send_json(200, {"ok": True, "message": "Restart command sent to the Android device."})
            else:
                if not shutil.which("idevicediagnostics"):
                    self.send_json(501, {"error": "Install the libimobiledevice tools to enable iPhone restart."})
                    return
                p = subprocess.run(["idevicediagnostics", "-u", device_id, "restart"], capture_output=True, text=True, timeout=12)
                if p.returncode != 0:
                    self.send_json(403, {"error": (p.stderr or "The iPhone did not accept the restart command. Unlock it, tap Trust if prompted, then reconnect.").strip()})
                    return
                self.send_json(200, {"ok": True, "message": "Restart command sent to the iPhone."})
        except (ValueError, json.JSONDecodeError) as e:
            self.send_json(400, {"error": str(e)})
        except subprocess.TimeoutExpired:
            self.send_json(504, {"error": "The device did not respond in time."})

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print(f"CARSKY helper running at http://{HOST}:{PORT}")
    print("Keep this terminal open while using CARSKY.")
    HTTPServer((HOST, PORT), Handler).serve_forever()
