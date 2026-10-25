
import re


ACTION_WORDS = {
    "click", "tap", "press", "select", "choose",
    "open", "start", "launch", "swipe", "scroll",
    "enter", "type", "input", "toggle", "restart",
    "close", "allow", "deny", "confirm", "back"
}

STOP_WORDS = {
    "the", "a", "an", "to", "on", "in", "and",
    "then", "app", "button", "option", "icon"
}

# Known descriptions for common Android controls.
SYNONYMS = {
    "menu": {"more options", "overflow", "menu"},
    "search": {"search"},
    "back": {"navigate up", "back"},
    "allow": {"allow", "while using the app"},
    "deny": {"deny", "don't allow"},
}


def normalize(value):
    value = str(value or "").lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return " ".join(value.split())


def get_target(action):
    """Extract the target from a natural-language UI action."""
    action = str(action or "").strip()

    quoted = re.findall(r'["\']([^"\']+)["\']', action)
    if quoted:
        return normalize(quoted[0])

    words = normalize(action).split()
    target_words = [
        word for word in words
        if word not in ACTION_WORDS and word not in STOP_WORDS
    ]
    return " ".join(target_words)


def element_description(element):
    return normalize(" ".join([
        str(element.get("text", "") or ""),
        str(element.get("content_desc", "") or ""),
        str(element.get("resource_id", "") or ""),
    ]))


def validate_action(action, ui_elements):
    """Check whether the requested target exists in the captured UI."""

    if not isinstance(ui_elements, list) or not ui_elements:
        return {
            "action": action,
            "status": "FAIL",
            "reason": "No UI elements detected. Capture the current screen first."
        }

    target = get_target(action)

    if not target:
        return {
            "action": action,
            "status": "INCONCLUSIVE",
            "reason": "Could not identify the target of this action."
        }

    target_terms = target.split()
    candidates = set(SYNONYMS.get(target, {target}))

    # Also support known aliases inside longer action descriptions.
    for term in target_terms:
        candidates.update(SYNONYMS.get(term, set()))

    for element in ui_elements:
        description = element_description(element)

        if not description:
            continue

        for candidate in candidates:
            candidate = normalize(candidate)

            if candidate and (
                candidate == description
                or candidate in description
            ):
                return {
                    "action": action,
                    "status": "PASS",
                    "reason": f"Target '{target}' found in the current UI.",
                    "matched_element": description
                }

    return {
        "action": action,
        "status": "FAIL",
        "reason": (
            f"Target '{target}' was not found in the captured UI. "
            "The screen may need to change before this action can be checked."
        )
    }


def validate_path(steps, ui_elements):
    """Validate candidate actions against one captured UI snapshot."""

    results = [
        validate_action(step, ui_elements)
        for step in steps
    ]

    passed = sum(
        result["status"] == "PASS"
        for result in results
    )

    failed = sum(
        result["status"] == "FAIL"
        for result in results
    )

    inconclusive = sum(
        result["status"] == "INCONCLUSIVE"
        for result in results
    )

    total = len(results)

    if total > 0 and passed == total:
        overall = "VALIDATED"
    elif passed > 0:
        overall = "PARTIALLY VALIDATED"
    else:
        overall = "NOT VALIDATED"

    return {
        "overall": overall,
        "passed": passed,
        "failed": failed,
        "inconclusive": inconclusive,
        "total": total,
        "steps": results,
        "validation_scope": "Current UI snapshot only; actions were not executed."
    }
