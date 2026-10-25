import os
import json
import re
import requests

from dotenv import load_dotenv
from google import genai


load_dotenv()


def extract_json(text):

    try:
        return json.loads(text)

    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)

        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass

    return None
def fetch_source_code(crash_report):

    match = re.search(
        r"https?://github\.com/[^\s]+/blob/[^\s]+",
        crash_report
    )

    if not match:
        return ""

    github_url = match.group(0).rstrip(".,)")

    try:
        raw_url = github_url.replace(
            "https://github.com/",
            "https://raw.githubusercontent.com/"
        ).replace("/blob/", "/")

        response = requests.get(raw_url, timeout=10)

        if response.status_code == 200:
            return response.text

    except Exception:
        pass

    return ""


def analyze_crash(crash_report, apk_name):

    api_key = os.getenv("GEMINI_API_KEY")
    source_code = fetch_source_code(crash_report)

    if not api_key:

        return {
            "apk": apk_name,
            "crash_type": "API Key Missing",
            "reason": "GEMINI_API_KEY was not found",
            "root_cause": "Please configure the Gemini API key in the .env file.",
            "trigger": "Not analyzed",
            "validation": {
                "ui_action": "PENDING",
                "crash_trigger": "PENDING",
                "reproduction_path": "PENDING"
            },
            "steps": []
        }

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are an Android crash analysis system.

Analyze the following crash report carefully.

Do NOT invent information that is not supported by the crash report.

Return ONLY valid JSON.

Required JSON structure:

{{
    "crash_type": "",
    "reason": "",
    "root_cause": "",
    "trigger": "",
    "crash_location": "",
    "steps": [
        "",
        "",
        ""
    ]
}}

The reproduction steps should describe the actions that are supported
by the crash report. If exact UI actions are not available, clearly say
that the action could not be determined from the report.

APK name:
{apk_name}

Crash report:
{crash_report}

Faulty source code:
{source_code}
"""

    try:

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )

        result = extract_json(response.text)

        if not result:

            raise ValueError("LLM did not return valid JSON")

        return {
            "apk": apk_name,

            "crash_type":
                result.get("crash_type", "Unknown"),

            "reason":
                result.get("reason", "Unknown"),

            "root_cause":
                result.get("root_cause", "Unable to determine"),

            "trigger":
                result.get("trigger", "Unknown"),

            "crash_location":
                result.get("crash_location", "Unknown"),

            "validation": {
                "ui_action": "PENDING",
                "crash_trigger": "PENDING",
                "reproduction_path": "PENDING"
            },

            "steps":
                result.get("steps", [])
        }

    except Exception as e:

        return {
            "apk": apk_name,
            "crash_type": "Analysis Error",
            "reason": str(e),
            "root_cause": "LLM analysis could not be completed.",
            "trigger": "Unknown",
            "validation": {
                "ui_action": "PENDING",
                "crash_trigger": "PENDING",
                "reproduction_path": "PENDING"
            },
            "steps": []
        }