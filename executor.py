
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By


RESULTS_FILE = Path("execution_results.json")
LOGCAT_FILE = Path("logcat_crash.txt")
APPIUM_URL = "http://127.0.0.1:4723"

# Actions are deliberately limited to predictable UI operations.
WAIT_AFTER_ACTION = 2
MAX_ACTIONS = 30


def run_command(command, timeout=15):
    """Run a command safely and return its result."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as exc:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc)
        }


def get_online_device():
    result = run_command(["adb", "devices"])

    if result["returncode"] != 0:
        raise RuntimeError("ADB failed: " + result["stderr"])

    for line in result["stdout"].splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            if parts[0].startswith("emulator-"):
                return parts[0]

    raise RuntimeError(
        "No online Android emulator found. "
        "Connect an emulator and check adb devices."
    )


def get_ui_elements(driver):
    """Read the UI currently displayed on the device."""
    elements = driver.find_elements(By.XPATH, "//*")
    output = []

    for element in elements:
        try:
            text = element.get_attribute("text") or ""
            desc = element.get_attribute("contentDescription") or ""
            resource_id = element.get_attribute("resourceId") or ""
            clickable = element.get_attribute("clickable") == "true"
            enabled = element.get_attribute("enabled") != "false"

            output.append({
                "text": text,
                "content_desc": desc,
                "resource_id": resource_id,
                "clickable": clickable,
                "enabled": enabled,
                "element": element
            })
        except Exception:
            continue

    return output


def element_label(item):
    return " ".join([
        item["text"],
        item["content_desc"],
        item["resource_id"].split("/")[-1]
    ]).strip().lower()


def find_target(driver, target):
    """Match a requested target against the current screen."""
    target = re.sub(r"[^a-z0-9\s]", " ", str(target).lower())
    target = " ".join(target.split())

    if not target:
        return None

    elements = get_ui_elements(driver)

    # Prefer exact matches over partial matches.
    for item in elements:
        if item["enabled"] and element_label(item) == target:
            return item["element"]

    for item in elements:
        label = element_label(item)
        if (
            item["enabled"]
            and len(target) >= 3
            and target in label
        ):
            return item["element"]

    return None



def parse_action(step):
    """Convert supported natural-language steps into safe UI actions."""
    text = str(step or "").strip().rstrip(".!?")

    # Support: Press Back / Go Back
    if re.fullmatch(r"(?:press\s+)?(?:go\s+)?back", text, re.I):
        return {"type": "back"}

    # Support: Swipe up/down/left/right
    match = re.fullmatch(
        r"swipe\s+(up|down|left|right)", text, re.I
    )
    if match:
        return {
            "type": "swipe",
            "direction": match.group(1).lower()
        }

    # Support: Type "hello" into "Search"
    match = re.fullmatch(
        r"""(?:type|enter|input)\s+["'](.*?)["']\s+
        (?:into|in)\s+["'](.*?)["']""",
        text,
        re.I | re.X
    )
    if match:
        return {
            "type": "type",
            "value": match.group(1),
            "target": match.group(2).strip()
        }

    # Support quoted or unquoted click/tap/select/open targets.
    match = re.fullmatch(
        r"""(?:click|tap|press|select|choose|open)\s+
        (?:(?:on|the|a|an)\s+)*
        ["']?(.*?)["']?""",
        text,
        re.I | re.X
    )
    if match:
        target = match.group(1).strip().strip("\"'").strip()

        if target:
            if target.lower() == "back":
                return {"type": "back"}

            return {"type": "tap", "target": target}

    return {
        "type": "unsupported",
        "original": text
    }


def execute_action(driver, step):
    """Execute one supported action against the current UI."""
    action = parse_action(step)

    if action["type"] == "unsupported":
        return {
            "status": "SKIPPED",
            "reason": "Unsupported action format; no action executed."
        }

    if action["type"] == "back":
        driver.back()
        return {
            "status": "EXECUTED",
            "action": "back"
        }

    if action["type"] == "swipe":
        size = driver.get_window_size()
        width = size["width"]
        height = size["height"]
        direction = action["direction"]

        start_x, start_y = width // 2, height // 2
        end_x, end_y = start_x, start_y

        if direction == "up":
            start_y, end_y = int(height * 0.8), int(height * 0.3)
        elif direction == "down":
            start_y, end_y = int(height * 0.3), int(height * 0.8)
        elif direction == "left":
            start_x, end_x = int(width * 0.8), int(width * 0.2)
        elif direction == "right":
            start_x, end_x = int(width * 0.2), int(width * 0.8)

        driver.swipe(start_x, start_y, end_x, end_y, 500)
        return {
            "status": "EXECUTED",
            "action": "swipe",
            "direction": direction
        }

    target = action["target"]
    element = find_target(driver, target)

    if element is None:
        return {
            "status": "NOT_FOUND",
            "target": target,
            "reason": "Target not found on the current screen."
        }

    if not element.is_displayed() or not element.is_enabled():
        return {
            "status": "NOT_EXECUTED",
            "target": target,
            "reason": "Target is not visible or enabled."
        }

    if action["type"] == "type":
        element.click()
        element.send_keys(action["value"])
        return {
            "status": "EXECUTED",
            "action": "type",
            "target": target
        }

    element.click()
    return {
        "status": "EXECUTED",
        "action": "tap",
        "target": target
    }



def capture_logcat(device, package):
    """Confirm crashes only when evidence belongs to the target app."""
    result = run_command(
        ["adb", "-s", device, "logcat", "-d", "-v", "threadtime"],
        timeout=30
    )

    logs = result["stdout"]
    LOGCAT_FILE.write_text(logs, encoding="utf-8")
    lines = logs.splitlines()
    target = package.strip().lower()

    # Java/Kotlin crash: FATAL EXCEPTION must identify our app's process.
    app_fatal_lines = []
    for i, line in enumerate(lines):
        if "FATAL EXCEPTION" not in line:
            continue

        context = lines[i:min(i + 15, len(lines))]
        if any(
            re.search(
                r"\bProcess:\s*" + re.escape(package) + r"\s*(?:,|$)",
                item,
                re.IGNORECASE
            )
            for item in context
        ):
            app_fatal_lines.extend(context)

    # Native crash: require the Android crash marker to name our package.
    native_crash_lines = []
    for i, line in enumerate(lines):
        if "Fatal signal" not in line and "Fatal error" not in line:
            continue

        context = lines[max(0, i - 5):min(i + 20, len(lines))]
        if any(
            re.search(
                r">>>\s*" + re.escape(package) + r"\s*<<<",
                item,
                re.IGNORECASE
            )
            for item in context
        ):
            native_crash_lines.extend(context)

    evidence = list(dict.fromkeys(app_fatal_lines + native_crash_lines))
    confirmed = bool(evidence)

    return {
        "status": "CRASH_EVIDENCE_FOUND" if confirmed else "NOT_CONFIRMED",
        "target_package": package,
        "fatal_exception_lines": app_fatal_lines[-20:],
        "native_crash_lines": native_crash_lines[-20:],
        "evidence": evidence[-40:],
        "logcat_file": str(LOGCAT_FILE),
        "note": (
            "Target app crash evidence found in logcat."
            if confirmed else
            "No confirmed crash evidence for the target app. "
            "This does not prove the app is crash-free."
        )
    }

def execute_reproduction(apk_path, package, activity, steps):
    """Run reproduction steps and save execution and crash-verification results."""
    device = get_online_device()
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name = device
    options.udid = device
    options.app = str(Path(apk_path).resolve())
    options.app_package = package
    options.app_activity = activity
    options.no_reset = False

    driver = None
    results = {
        "package": package,
        "device": device,
        "execution_status": "FAILED",
        "steps": [],
        "crash_verification": {}
    }

    try:
        driver = webdriver.Remote(APPIUM_URL, options=options)
        driver.implicitly_wait(5)

        for index, step in enumerate(steps[:MAX_ACTIONS], start=1):
            item = {"step_number": index, "instruction": str(step)}
            try:
                item.update(execute_action(driver, step))
                time.sleep(WAIT_AFTER_ACTION)
                item["visible_elements"] = len(get_ui_elements(driver))
            except Exception as exc:
                item["status"] = "ERROR"
                item["error"] = str(exc)
            results["steps"].append(item)

        results["execution_status"] = (
            "COMPLETED"
            if all(s.get("status") == "EXECUTED" for s in results["steps"])
            else "PARTIAL"
        )

    except Exception as exc:
        results["error"] = str(exc)

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

        results["crash_verification"] = capture_logcat(device, package)
        RESULTS_FILE.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Execute Android crash reproduction steps."
    )
    parser.add_argument("--apk", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--activity", required=True)
    parser.add_argument("--steps-file", required=True)
    args = parser.parse_args()

    steps = json.loads(
        Path(args.steps_file).read_text(encoding="utf-8")
    )
    execute_reproduction(
        args.apk, args.package, args.activity, steps
    )
