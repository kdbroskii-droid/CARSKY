# CARSKY

A local Chromebook/Linux phone utility with a dark interface, brand selection, connected-device model detection, corner Back button, and a final-screen **Restart phone** action.

## What works

- Detects Android phones through ADB and reads the actual manufacturer/model from Android system properties (for example, Samsung model identifiers).
- Detects trusted iPhones through libimobiledevice and reads the device ProductType identifier (for example, iPhone model code).
- Sends a normal restart command to an Android phone after USB debugging has been authorized.
- Can request an iPhone restart when the phone is trusted/paired and the installed libimobiledevice version supports diagnostics restart.
- Back button returns from the action screen to the brand screen, then to Home.
- The interface runs locally; it does not upload device information.

## Chromebook setup

1. Open **Settings → Developers → Linux development environment** and start Linux.
2. Install the USB tools:

   ```bash
   sudo apt update
   sudo apt install -y adb usbutils libimobiledevice-utils
   ```

3. Download/clone this repository into Linux.
4. Start the local helper:

   ```bash
   python3 server.py
   ```

5. Open **http://127.0.0.1:8765** in Chrome.

Keep the terminal running while using CARSKY. If ChromeOS does not expose the phone to Linux, enable USB access for the Linux environment in ChromeOS settings and reconnect the cable.

### Android / Samsung

- Enable Developer options and USB debugging on the phone.
- Connect by a data-capable USB cable.
- Accept the RSA authorization prompt on the phone.
- Press Refresh in CARSKY. The exact model is read using ADB; a generic USB name is not used as the model.
- Restart requires an authorized ADB connection. If the phone is locked and has not previously authorized this Chromebook, ADB may not be available.

### iPhone

- Unlock the iPhone and tap **Trust This Computer** if prompted.
- Press Refresh. CARSKY displays the Apple ProductType identifier reported by the device; this is a precise hardware identifier, but it may look like `iPhoneXX,Y` rather than a retail name such as “iPhone 15 Pro”.
- Restart requires a trusted pairing and a compatible `idevicediagnostics` installation. If the phone does not accept the request, restart it manually.

## Important limits

CARSKY does not guess passcodes, bypass device locks, remove Apple Activation Lock, bypass Google FRP or Samsung account verification, or defeat device-management controls. Those protections require the owner's credentials or the manufacturer's official recovery process.

The **UNDISABLE** and **UNLOCK** screens provide official recovery guidance rather than bypasses. **DELETE ALL APPS** does not perform a destructive bulk removal; review and remove apps from the phone itself. **FBOT** is currently an unconfigured placeholder.

## Security

The helper binds only to `127.0.0.1` and uses fixed ADB/libimobiledevice commands. Do not expose this service to your network.
