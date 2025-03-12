from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
import platform
import os
from random_user_agent import random_ua


def apply_stealth_techniques(driver):
    try:
        driver.execute_script("""
            // 覆盖WebDriver属性 / Override WebDriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
            // 清除自动化相关特征 / Clear automation-related features
            delete navigator.__proto__.webdriver;
            // 模拟插件数量(增加真实性) / Simulate plugin count (increase authenticity)
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    return {
                        length: 5,
                        item: function() { return null; },
                        refresh: function() { return undefined; },
                        namedItem: function() { return null; }
                    };
                },
            });
            // 模拟语言列表 / Simulate language list
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en'],
            });
            // 重写可能被检测的属性 / Rewrite properties used for detection
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        print("应用了反检测技术 / Applied anti-detection techniques")
    except Exception as e:
        print(f"应用反检测技术失败: {str(e)} / Failed to apply anti-detection techniques: {str(e)}")


def try_init_with_driver(driver_path, chrome_options):
    if not os.path.exists(driver_path):
        return None, None
    if platform.system() != "Windows":
        try:
            os.chmod(driver_path, 0o755)
        except:
            pass
    print(f"初始化浏览器，使用: {driver_path} / Initializing browser using ChromeDriver")
    try:
        service = Service(executable_path=driver_path, log_path=os.path.devnull)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 20)
        apply_stealth_techniques(driver)
        print("✓ 浏览器初始化成功 / Browser initialized successfully")
        return driver, wait
    except Exception as e:
        print(f"常规初始化失败: {str(e)} / Regular initialization failed")
        try:
            os.environ["webdriver.chrome.driver"] = driver_path
            driver = webdriver.Chrome(options=chrome_options)
            wait = WebDriverWait(driver, 20)
            apply_stealth_techniques(driver)
            print("✓ 浏览器初始化成功（兼容模式） / Browser initialized successfully (compatibility mode)")
            return driver, wait
        except Exception as e2:
            print(f"兼容模式也失败: {str(e2)} / Compatibility mode also failed")
            return None, None


def try_local_drivers(chrome_options):
    system = platform.system()
    chromedriver_name = "chromedriver.exe" if system == "Windows" else "chromedriver"
    check_locations = [
        os.path.abspath(chromedriver_name),
        os.path.abspath(os.path.join("chromedriver", chromedriver_name)),
        os.path.join(".", chromedriver_name),
        os.path.join("..", chromedriver_name),
        os.path.join(os.path.expanduser("~"), chromedriver_name),
        os.path.join(os.path.expanduser("~"), "Downloads", chromedriver_name)
    ]
    for location in check_locations:
        if os.path.exists(location):
            print(f"尝试ChromeDriver: {location} / Trying ChromeDriver")
            driver, wait = try_init_with_driver(location, chrome_options)
            if driver is not None:
                return driver, wait
    return None, None


def init_browser(chromedriver_path=None):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-insecure-localhost")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--ignore-ssl-errors=yes")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    user_agent = random_ua()["User-Agent"]
    chrome_options.add_argument(f"--user-agent={user_agent}")

    try:
        print("尝试让系统自动查找ChromeDriver... / Trying to let system find ChromeDriver automatically...")
        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, 20)
        apply_stealth_techniques(driver)
        print("✓ 自动查找成功! / Automatic detection successful!")
        return driver, wait
    except Exception as e:
        print(f"自动查找失败: {str(e)} / Automatic detection failed")
    if chromedriver_path:
        return try_init_with_driver(chromedriver_path, chrome_options)
    else:
        return try_local_drivers(chrome_options)


def cleanup_browser(driver):
    if driver:
        driver.quit() 