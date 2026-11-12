# CARSKY

A local Chromebook/Linux phone manager with USB detection, Android device inventory, generated diagnostic scripts, restart, and individually selected Android app removal.

## Real operations

- Detects authorized Android devices with ADB and trusted iPhones with libimobiledevice.
- Reads reported Android manufacturer, model, build fingerprint, build type, Android version and related properties.
- Labels Samsung-like and iOS-like Android identifiers and reports common custom-ROM/build indicators.
- Inspects Android model/build details, display, memory, storage, battery, kernel and accessible script filenames.
- Generates a model-labelled, read-only diagnostic script and previews it.
- Before transfer, CARSKY opens the **CARSKY Verification companion app** on the Android phone. The app displays a random 1–99 code in a full-screen activity designed to appear over the lock screen. Enter the code on the Chromebook within 2 minutes (maximum 3 attempts). Only then does CARSKY transfer and run the diagnostic script and request a restart after successful execution.
- The verification activity does not dismiss the keyguard, unlock the phone, change its passcode, or bypass device security. Android version, manufacturer restrictions, and lock-screen policy may prevent an activity from appearing over the keyguard.
- Existing scripts are inventoried by filename only; unknown scripts are never executed.
- Restarts a selected connected phone using ADB or a trusted libimobiledevice pairing.
- Lists third-party Android packages and removes only the individual package selected by the user. System packages are excluded from this list.
- Keeps helper endpoints bound to localhost.

## Install the verification companion app

The lock-screen verification screen requires the companion APK to be installed on the Android phone once.

1. Open this repository on GitHub and select **Actions**.
2. Open the latest **Build CARSKY verification app** workflow run.
3. Download the `carsky-verification-apk` artifact and extract `companion-debug.apk`.
4. Connect the Android phone with USB debugging enabled and authorized.
5. Install the APK from the Chromebook Linux terminal:

   ```bash
   adb install companion-debug.apk
   ```

6. Start CARSKY and use **DEVICE SCRIPT BUILDER**. When you request verification, CARSKY launches the companion activity on the phone.

The activity is a visible screen, not a notification. It uses Android's show-when-locked activity feature and leaves the actual keyguard in place. Some manufacturers or security states may block apps from appearing over the lock screen. If that happens, unlock the phone normally and retry; CARSKY will not bypass the lock.

## Optional `docaslails` folder

The `docaslails/` folder contains the extra Android system detector. It is loaded optionally by `server.py`.

**If you delete `docaslails/`, CARSKY still starts and its core features continue to work**: Android/iPhone detection, basic model reporting, restart and Android user-app management. Only extended Android build/system classification and detailed property display are disabled.

The detector reads Android properties reported by the connected device. These can be modified or spoofed, so its labels are clues, not proof that hardware is genuine. An iOS-like Android clone is still managed through the Android/ADB path; it is not treated as a real iPhone.

## Chromebook setup

1. Start the Linux development environment.
2. Install the tools:

   ```bash
   sudo apt update
   sudo apt install -y adb usbutils libimobiledevice-utils
   ```

3. Clone/download this repository into Linux.
4. Start CARSKY:

   ```bash
   python3 server.py
   ```

5. Open **http://127.0.0.1:8765** in Chrome.

Keep the terminal open. ChromeOS must expose the USB device to Linux. Android requires Developer options → USB debugging and approval of the Chromebook's RSA prompt. iPhone requires unlocking it and tapping **Trust This Computer**.

## Security and unsupported operations

- **UNDISABLE / UNLOCK:** account and lock protections cannot be removed by this app. These screens identify the official recovery route; no bypass is attempted.
- **DELETE ALL APPS:** CARSKY does not run a destructive bulk-removal command. It lists user-installed Android apps so each removal can be reviewed and confirmed. iOS app removal is not implemented.
- **FBOT:** no action is sent because no safe, defined FBOT operation has been configured.
- Android properties can be spoofed; CARSKY cannot certify a clone or authenticate physical hardware from these values alone.
- Restart and uninstall require an authorized connection. App removal may erase that app's local data.
- The helper listens only on `127.0.0.1`; do not expose it to your network.
