from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
import platform
import os
from random_user_agent import random_ua

# 以下辅助函数已移入此文件
CHROMEDRIVER_VERSION = "134.0.6998.88"
CHROMEDRIVER_DIR = "chromedriver"

import subprocess
import zipfile
import requests
import urllib.request
import re


def get_chrome_version():
    """获取系统已安装的Chrome版本 / Get installed Chrome version from the system"""
    try:
        system = platform.system()
        if system == "Windows":
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
                version, _ = winreg.QueryValueEx(key, "version")
                print(f"检测到Chrome版本: {version} / Detected Chrome version: {version}")
                return version
            except:
                paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                ]
                for path in paths:
                    if os.path.exists(path):
                        try:
                            version = subprocess.check_output(f'wmic datafile where name="{path}" get Version /value', shell=True)
                            version = version.decode('utf-8').strip().split('=')[-1]
                            if version:
                                print(f"检测到Chrome版本: {version} / Detected Chrome version: {version}")
                                return version
                        except:
                            pass
        elif system == "Darwin":
            try:
                version = subprocess.check_output([
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"
                ], stderr=subprocess.DEVNULL).decode('utf-8')
                match = re.search(r"Chrome\s+(\d+\.\d+\.\d+\.\d+)", version)
                if match:
                    print(f"检测到Chrome版本: {match.group(1)} / Detected Chrome version: {match.group(1)}")
                    return match.group(1)
            except:
                pass
        elif system == "Linux":
            try:
                version = subprocess.check_output([
                    "google-chrome", "--version"
                ], stderr=subprocess.DEVNULL).decode('utf-8')
                match = re.search(r"Chrome\s+(\d+\.\d+\.\d+\.\d+)", version)
                if match:
                    print(f"检测到Chrome版本: {match.group(1)} / Detected Chrome version: {match.group(1)}")
                    return match.group(1)
            except:
                try:
                    version = subprocess.check_output([
                        "chromium", "--version"
                    ], stderr=subprocess.DEVNULL).decode('utf-8')
                    match = re.search(r"Chromium\s+(\d+\.\d+\.\d+\.\d+)", version)
                    if match:
                        print(f"检测到Chromium版本: {match.group(1)} / Detected Chromium version: {match.group(1)}")
                        return match.group(1)
                except:
                    pass
    except Exception as e:
        print(f"获取Chrome版本时出错 / Error getting Chrome version: {str(e)}")
    print(f"无法检测Chrome版本，将使用默认版本: {CHROMEDRIVER_VERSION} / Cannot detect Chrome version, will use default: {CHROMEDRIVER_VERSION}")
    return None


def get_latest_chromedriver_version():
    """获取最新的ChromeDriver版本号 / Get latest ChromeDriver version"""
    try:
        chrome_version = get_chrome_version()
        if chrome_version:
            major_version = chrome_version.split('.')[0]
            response = requests.get(f"https://mirrors.huaweicloud.com/chromedriver/LATEST_RELEASE_{major_version}")
            if response.status_code == 200:
                version = response.text.strip()
                print(f"找到对应ChromeDriver版本: {version} / Found matching ChromeDriver version: {version}")
                return version
        response = requests.get("https://mirrors.huaweicloud.com/chromedriver/LATEST_RELEASE")
        if response.status_code == 200:
            version = response.text.strip()
            print(f"找到最新ChromeDriver版本: {version} / Found latest ChromeDriver version: {version}")
            return version
    except Exception as e:
        print(f"获取ChromeDriver版本时出错: {str(e)} / Error getting ChromeDriver version: {str(e)}")
    print(f"使用默认ChromeDriver版本: {CHROMEDRIVER_VERSION} / Using default ChromeDriver version: {CHROMEDRIVER_VERSION}")
    return CHROMEDRIVER_VERSION


def download_chromedriver():
    """下载与系统匹配的ChromeDriver / Download ChromeDriver matching the system"""
    try:
        print("\n>>> 开始下载ChromeDriver... / Starting ChromeDriver download...")
        if not os.path.exists(CHROMEDRIVER_DIR):
            os.makedirs(CHROMEDRIVER_DIR)
        system = platform.system()
        machine = platform.machine().lower()
        chromedriver_filename = "chromedriver"
        if system == "Windows":
            chromedriver_filename += ".exe"
        chromedriver_path = os.path.join(CHROMEDRIVER_DIR, chromedriver_filename)
        if os.path.exists(chromedriver_path):
            try:
                os.remove(chromedriver_path)
                print("删除旧版ChromeDriver / Removing old ChromeDriver")
            except:
                pass
        version = CHROMEDRIVER_VERSION if CHROMEDRIVER_VERSION else get_latest_chromedriver_version()
        print(f"使用ChromeDriver版本 / Using ChromeDriver version: {version}")
        zip_name = None
        if system == "Windows":
            if machine.endswith('64'):
                zip_name = "chromedriver-win64.zip"
            else:
                zip_name = "chromedriver-win32.zip"
        elif system == "Darwin":
            if 'arm' in machine or 'aarch64' in machine:
                zip_name = "chromedriver-mac-arm64.zip"
            else:
                zip_name = "chromedriver-mac-x64.zip"
        elif system == "Linux":
            zip_name = "chromedriver-linux64.zip"
        if not zip_name:
            print("无法确定系统类型，尝试使用通用版本 / Cannot determine system type, using generic version")
            if system == "Windows":
                zip_name = "chromedriver-win32.zip"
            else:
                zip_name = "chromedriver-linux64.zip"
        download_urls = [
            f"https://mirrors.huaweicloud.com/chromedriver/{version}/{zip_name}",
            f"https://registry.npmmirror.com/binary.html?path=chromedriver/{version}/{zip_name}",
            f"https://cdn.npmmirror.com/binaries/chromedriver/{version}/{zip_name}"
        ]
        zip_path = os.path.join(CHROMEDRIVER_DIR, zip_name)
        downloaded = False
        for url in download_urls:
            if downloaded:
                break
            print(f"尝试下载: {url} / Trying download from: {url}")
            try:
                response = requests.get(url, stream=True)
                if response.status_code == 200 and int(response.headers.get('content-length', 0)) > 1000000:
                    with open(zip_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    if os.path.exists(zip_path) and os.path.getsize(zip_path) > 1000000:
                        downloaded = True
                        print("下载成功 / Download successful")
            except Exception as e:
                print(f"从 {url} 下载失败: {str(e)} / Download failed from: {url}")
        if not downloaded:
            try:
                print("尝试使用urllib下载 / Trying download with urllib")
                urllib.request.urlretrieve(download_urls[0], zip_path)
                if os.path.exists(zip_path) and os.path.getsize(zip_path) > 1000000:
                    downloaded = True
            except:
                pass
        if not downloaded or not os.path.exists(zip_path) or os.path.getsize(zip_path) < 1000000:
            print("所有下载尝试都失败 / All download attempts failed")
            print(f"请手动下载ChromeDriver: / Please download ChromeDriver manually:")
            print(f"1. 访问 / Visit: https://registry.npmmirror.com/binary.html?path=chromedriver/{version}/")
            print(f"2. 下载 / Download: {zip_name}")
            print("3. 解压并将ChromeDriver放在当前目录 / Extract and place ChromeDriver in current directory")
            return None
        success = False
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                chromedriver_files = [f for f in zip_ref.namelist() if os.path.basename(f) == chromedriver_filename]
                if chromedriver_files:
                    for file in chromedriver_files:
                        with zip_ref.open(file) as source, open(chromedriver_path, "wb") as target:
                            target.write(source.read())
                        success = True
                        break
                if not success:
                    zip_ref.extractall(CHROMEDRIVER_DIR)
                    success = True
        except Exception as e:
            print(f"解压失败: {str(e)} / Extraction failed")
            return None
        if not os.path.exists(chromedriver_path):
            for root, dirs, files in os.walk(CHROMEDRIVER_DIR):
                for file in files:
                    if file.startswith("chromedriver"):
                        src = os.path.join(root, file)
                        print(f"找到ChromeDriver: {src} / Found ChromeDriver")
                        import shutil
                        shutil.copy2(src, chromedriver_path)
                        success = True
                        break
        if system != "Windows" and os.path.exists(chromedriver_path):
            os.chmod(chromedriver_path, 0o755)
        if os.path.exists(chromedriver_path) and os.path.getsize(chromedriver_path) > 1000000:
            print(f"ChromeDriver下载成功: {chromedriver_path} / ChromeDriver downloaded successfully")
            if system == "Windows" and not chromedriver_path.endswith('.exe'):
                os.rename(chromedriver_path, chromedriver_path + '.exe')
                chromedriver_path += '.exe'
            try:
                os.remove(zip_path)
            except:
                pass
            return chromedriver_path
        else:
            print("ChromeDriver下载或解压失败 / ChromeDriver download or extraction failed")
            return None
    except Exception as e:
        print(f"下载ChromeDriver时出错: {str(e)} / Error downloading ChromeDriver")
        return None


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
