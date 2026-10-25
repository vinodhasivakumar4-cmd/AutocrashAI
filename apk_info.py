import subprocess
import re


def get_apk_package(apk_path):

    command = [
        r"C:\Users\vinod\AppData\Local\Android\Sdk\build-tools\36.0.0\aapt.exe",
        "dump",
        "badging",
        apk_path
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or
            "Unable to read APK information."
        )

    match = re.search(
        r"package:\s+name='([^']+)'",
        result.stdout
    )

    if not match:
        raise RuntimeError(
            "Package name could not be detected from APK."
        )

    return match.group(1)


def get_launchable_activity(apk_path):

    command = [
         r"C:\Users\vinod\AppData\Local\Android\Sdk\build-tools\36.0.0\aapt.exe",
        "dump",
        "badging",
        apk_path
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or
            "Unable to read APK information."
        )

    match = re.search(
        r"launchable-activity:\s+name='([^']+)'",
        result.stdout
    )

    if not match:
        raise RuntimeError(
            "Launchable activity could not be detected from APK."
        )

    return match.group(1)


def get_apk_info(apk_path):

    return {
        "package": get_apk_package(apk_path),
        "activity": get_launchable_activity(apk_path)
    }