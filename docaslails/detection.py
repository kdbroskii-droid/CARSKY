"""Optional Android build/system fingerprint inspection for CARSKY.

All values are self-reported by Android properties. They are useful clues,
not cryptographic proof of the phone's manufacturer or authenticity.
"""

PROPERTIES = {
    "manufacturer": "ro.product.manufacturer",
    "brand": "ro.product.brand",
    "model": "ro.product.model",
    "device": "ro.product.device",
    "product": "ro.product.name",
    "fingerprint": "ro.build.fingerprint",
    "build_id": "ro.build.display.id",
    "android_version": "ro.build.version.release",
    "build_type": "ro.build.type",
    "tags": "ro.build.tags",
    "abi": "ro.product.cpu.abi",
}


def inspect_android(serial, run):
    values = {}
    for key, prop in PROPERTIES.items():
        values[key] = run(["adb", "-s", serial, "shell", "getprop", prop]) or "Not reported"

    searchable = " ".join(str(values[k]) for k in
                          ("manufacturer", "brand", "model", "device", "product",
                           "fingerprint", "build_id")).lower()
    indicators = []
    custom_names = ("lineage", "crdroid", "pixel experience", "evolution",
                    "graphene", "calyx", "paranoid", " /test-keys", "test-keys")
    for marker in custom_names:
        if marker in searchable:
            indicators.append(marker.strip())
    if values["build_type"].lower() in ("userdebug", "eng"):
        indicators.append(values["build_type"].lower() + " build")
    if values["tags"].lower() == "test-keys":
        indicators.append("test-keys")

    if any(word in searchable for word in ("iphone", "ios", "apple")):
        classification = "Android reporting iOS-like/Apple-like identifiers"
    elif "samsung" in searchable:
        classification = "Samsung-like Android"
    else:
        classification = "Android"

    if indicators:
        system = "Custom-ROM/build indicators: " + ", ".join(sorted(set(indicators)))
    elif values["build_type"].lower() == "user" and values["tags"].lower() == "release-keys":
        system = "Standard-looking release build (not authenticated)"
    else:
        system = "Build type is inconclusive"

    return {
        "status": "Reported Android system details",
        "classification": classification,
        "system": system,
        "properties": values,
        "warning": "Android properties can be changed or spoofed. This cannot prove the device is genuine."
    }
