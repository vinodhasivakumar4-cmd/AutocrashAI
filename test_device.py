from appium import webdriver
from appium.options.android import UiAutomator2Options

options = UiAutomator2Options()
options.platform_name = "Android"
options.automation_name = "UiAutomator2"
options.device_name = "Redmi 9"
options.udid = "emulator-5556"
options.no_reset = True
options.ignore_hidden_api_policy_error = True

driver = webdriver.Remote(
    "http://127.0.0.1:4723",
    options=options
)

try:
    print("CONNECTED SUCCESSFULLY")
    print("Device:", driver.capabilities.get("deviceModel"))
    print("Android:", driver.capabilities.get("platformVersion"))
    print("Current package:", driver.current_package)
finally:
    driver.quit()
