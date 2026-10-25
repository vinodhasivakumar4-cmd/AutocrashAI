import json
import time
import subprocess
import argparse

from appium import webdriver
from appium.options.android import UiAutomator2Options

from apk_info import get_apk_info


def get_device():
    result = subprocess.run(
        ["adb", "devices"],
        capture_output=True,
        text=True,
        check=True
    )

    devices = []
    for line in result.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])

    # Prefer the known working emulator.
    

    # Otherwise use any online emulator, never an offline one.
    for device in devices:
        if device.startswith("emulator-"):
            return device

    raise RuntimeError(
        "No online Android emulator detected. Check `adb devices`."
    )


def capture_ui_state(apk_path):

    apk_info = get_apk_info(apk_path)

    package = apk_info["package"]
    activity = apk_info["activity"]

    device = get_device()

    print("APK:", apk_path)
    print("Package:", package)
    print("Activity:", activity)
    print("Device:", device)

    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name = device
    options.udid = device

    options.app = apk_path
    options.app_package = package
    options.app_activity = activity
    options.no_reset = True

    driver = webdriver.Remote(
        "http://127.0.0.1:4723",
        options=options
    )

    try:
        time.sleep(5)
        elements = driver.find_elements("xpath", "//*")

        ui_elements = []
        for element in elements:
            ui_elements.append({
                "text": element.get_attribute("text"),
                "content_desc": element.get_attribute("contentDescription"),
                "resource_id": element.get_attribute("resourceId"),
                "class": element.get_attribute("className"),
                "clickable": element.get_attribute("clickable"),
                "enabled": element.get_attribute("enabled")
            })

        with open("ui_state.json", "w", encoding="utf-8") as f:
            json.dump({
                "apk": apk_path,
                "package": package,
                "activity": activity,
                "device": device,
                "elements": ui_elements
            }, f, indent=4)

        print(f"Captured {len(ui_elements)} UI elements.")

    finally:
        driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apk",
        required=True,
        help="Path to APK file"
    )
    args = parser.parse_args()
    capture_ui_state(args.apk)
