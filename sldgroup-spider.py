"""
SLD集团网站图片爬虫 - 使用Selenium抓取动态加载内容
SLD Group Website Image Crawler - Using Selenium to capture dynamically loaded content

此程序适用于不同国家/地区使用，支持自动下载ChromeDriver和断点续传功能
This program is suitable for use in different countries/regions, supports auto-downloading ChromeDriver and resume download
"""

import os
import sys
import time
import random
import re
import platform
import zipfile
import subprocess
from pathlib import Path
import urllib.request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import json
from random_user_agent import random_ua

# 全局配置 / Global Configuration
PICTURE_DIR = 'picture'  # 主图片目录 / Main image directory
DEFAULT_SAVE_DIRS = ["residential", "clubhouse", "salesoffice", "hospitality", "commercial"]

# 默认子页面URL最大ID / Maximum ID for subpages (will be updated dynamically if possible)
DEFAULT_MAX_IDS = {
    "residential": 34,  # 住宅 / Residential
    "clubhouse": 7,     # 会所 / Clubhouse
    "salesoffice": 12,  # 销售中心 / Sales Office
    "hospitality": 24,  # 酒店 / Hospitality
    "commercial": 18    # 商业 / Commercial
}

# ChromeDriver配置 / ChromeDriver Configuration
CHROMEDRIVER_PATH = None  # 设置为None则自动查找，或手动指定路径 / Set to None for auto-detection, or manually specify the path
CHROMEDRIVER_VERSION = "134.0.6998.88"  # 默认使用更新的ChromeDriver版本 / Default to newer ChromeDriver version
CHROMEDRIVER_DIR = "chromedriver"  # ChromeDriver下载目录 / Download directory
SKIP_DOWNLOAD = False  # 设置为True跳过下载，强制使用本地ChromeDriver / Set to True to skip download and force using local ChromeDriver

# 爬取设置 / Crawler Settings
MAX_PAGE_RETRIES = 5       # 页面加载最大重试次数 / Maximum page load retries
MAX_IMG_RETRIES = 3        # 图片下载最大重试次数 / Maximum image download retries
REQUEST_TIMEOUT = 60       # 请求超时时间(秒) / Request timeout in seconds
MIN_WAIT_TIME = 1.0        # 最小等待时间(秒) / Minimum wait time between requests
MAX_WAIT_TIME = 3.0        # 最大等待时间(秒) / Maximum wait time between requests
STATUS_SAVE_INTERVAL = 5   # 状态保存间隔(处理N个图片后保存一次) / Status save interval (save after processing N images)

# 记录下载状态的文件 / File to record download status
DOWNLOAD_STATUS_FILE = os.path.join(PICTURE_DIR, "download_status.json")

# 内存中缓存下载状态 / In-memory download status cache
_download_status_cache = None
_status_modified = False
_processed_count = 0

# 记录当前项目的重试记录，用于实现指数退避策略 
# Record retry attempts for current project, for exponential backoff
_current_project_retries = {}

def get_chrome_version():
    """
    获取系统已安装的Chrome版本
    Get installed Chrome version from the system
    
    返回值 / Returns:
        str or None: Chrome版本号或None（如果未检测到） / Chrome version or None if not detected
    """
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
                # 尝试其他Windows路径 / Try other Windows paths
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
        elif system == "Darwin":  # macOS
            try:
                version = subprocess.check_output(
                    ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
                    stderr=subprocess.DEVNULL
                ).decode('utf-8')
                match = re.search(r"Chrome\s+(\d+\.\d+\.\d+\.\d+)", version)
                if match:
                    print(f"检测到Chrome版本: {match.group(1)} / Detected Chrome version: {match.group(1)}")
                    return match.group(1)
            except:
                pass
        elif system == "Linux":
            try:
                # 尝试标准Google Chrome / Try standard Google Chrome
                version = subprocess.check_output(
                    ["google-chrome", "--version"],
                    stderr=subprocess.DEVNULL
                ).decode('utf-8')
                match = re.search(r"Chrome\s+(\d+\.\d+\.\d+\.\d+)", version)
                if match:
                    print(f"检测到Chrome版本: {match.group(1)} / Detected Chrome version: {match.group(1)}")
                    return match.group(1)
            except:
                try:
                    # 尝试Chromium / Try Chromium
                    version = subprocess.check_output(
                        ["chromium", "--version"],
                        stderr=subprocess.DEVNULL
                    ).decode('utf-8')
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
        # 首先尝试获取Chrome版本 / First try to get Chrome version
        chrome_version = get_chrome_version()
        if chrome_version:
            # 提取Chrome主版本号（如134.0.6998.89中的134）/ Extract major version (e.g. 134 from 134.0.6998.89)
            major_version = chrome_version.split('.')[0]
            # 尝试获取该主版本对应的ChromeDriver版本 / Try to get matching ChromeDriver version
            response = requests.get(f"https://mirrors.huaweicloud.com/chromedriver/LATEST_RELEASE_{major_version}")
            if response.status_code == 200:
                version = response.text.strip()
                print(f"找到对应ChromeDriver版本: {version} / Found matching ChromeDriver version: {version}")
                return version
        
        # 如果没有获取到Chrome版本或找不到对应版本的ChromeDriver，尝试获取最新版本
        # If Chrome version is not found or matching ChromeDriver not available, try to get latest version
        response = requests.get("https://mirrors.huaweicloud.com/chromedriver/LATEST_RELEASE")
        if response.status_code == 200:
            version = response.text.strip()
            print(f"找到最新ChromeDriver版本: {version} / Found latest ChromeDriver version: {version}")
            return version
    except Exception as e:
        print(f"获取ChromeDriver版本时出错: {str(e)} / Error getting ChromeDriver version: {str(e)}")
    
    # 如果以上所有尝试都失败，使用默认版本 / If all attempts fail, use default version
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
        
        # 清理旧版本
        if os.path.exists(chromedriver_path):
            try:
                os.remove(chromedriver_path)
                print("删除旧版ChromeDriver / Removing old ChromeDriver")
            except:
                pass
        
        # 确定ChromeDriver版本
        version = CHROMEDRIVER_VERSION if CHROMEDRIVER_VERSION else get_latest_chromedriver_version()
        print(f"使用ChromeDriver版本 / Using ChromeDriver version: {version}")
        
        zip_name = None
        if system == "Windows":
            if machine.endswith('64'):
                zip_name = "chromedriver-win64.zip"
            else:
                zip_name = "chromedriver-win32.zip"
        elif system == "Darwin":  # macOS
            if 'arm' in machine or 'aarch64' in machine:
                zip_name = "chromedriver-mac-arm64.zip"
            else:
                zip_name = "chromedriver-mac-x64.zip"
        elif system == "Linux":
            zip_name = "chromedriver-linux64.zip"
        
        if not zip_name:
            print(f"无法确定系统类型，尝试使用通用版本 / Cannot determine system type, using generic version")
            # 尝试使用通用版本
            if system == "Windows":
                zip_name = "chromedriver-win32.zip"
            else:
                zip_name = "chromedriver-linux64.zip"
        
        # 构建下载URL - 先尝试华为镜像，再尝试其他镜像
        download_urls = [
            f"https://mirrors.huaweicloud.com/chromedriver/{version}/{zip_name}",
            f"https://registry.npmmirror.com/binary.html?path=chromedriver/{version}/{zip_name}",
            f"https://cdn.npmmirror.com/binaries/chromedriver/{version}/{zip_name}"
        ]
        
        zip_path = os.path.join(CHROMEDRIVER_DIR, zip_name)
        downloaded = False
        
        # 尝试从多个镜像下载
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
                        print(f"下载成功 / Download successful")
            except Exception as e:
                print(f"从 {url} 下载失败: {str(e)} / Download failed from {url}")
        
        # 如果下载失败，尝试使用urllib
        if not downloaded:
            try:
                print("尝试使用urllib下载 / Trying download with urllib")
                urllib.request.urlretrieve(download_urls[0], zip_path)
                if os.path.exists(zip_path) and os.path.getsize(zip_path) > 1000000:
                    downloaded = True
            except:
                pass
        
        # 如果仍然下载失败
        if not downloaded or not os.path.exists(zip_path) or os.path.getsize(zip_path) < 1000000:
            print(f"所有下载尝试都失败 / All download attempts failed")
            # 提示用户手动下载
            print(f"请手动下载ChromeDriver: / Please download ChromeDriver manually:")
            print(f"1. 访问 / Visit: https://registry.npmmirror.com/binary.html?path=chromedriver/{version}/")
            print(f"2. 下载 / Download: {zip_name}")
            print(f"3. 解压并将ChromeDriver放在当前目录 / Extract and place ChromeDriver in current directory")
            return None
        
        # 解压文件
        success = False
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 尝试直接提取chromedriver
                chromedriver_files = [f for f in zip_ref.namelist() if os.path.basename(f) == chromedriver_filename]
                if chromedriver_files:
                    for file in chromedriver_files:
                        source = zip_ref.open(file)
                        target = open(chromedriver_path, "wb")
                        with source, target:
                            target.write(source.read())
                        success = True
                        break
                # 如果没有找到，解压整个目录
                if not success:
                    zip_ref.extractall(CHROMEDRIVER_DIR)
                    success = True
        except Exception as e:
            print(f"解压失败: {str(e)} / Extraction failed")
            return None
        
        # 确保文件存在
        if not os.path.exists(chromedriver_path):
            # 查找解压后的目录中的chromedriver
            for root, dirs, files in os.walk(CHROMEDRIVER_DIR):
                for file in files:
                    if file.startswith("chromedriver"):
                        src = os.path.join(root, file)
                        print(f"找到ChromeDriver: {src} / Found ChromeDriver")
                        # 复制到目标位置
                        import shutil
                        shutil.copy2(src, chromedriver_path)
                        success = True
                        break
        
        # 设置执行权限
        if system != "Windows" and os.path.exists(chromedriver_path):
            os.chmod(chromedriver_path, 0o755)
        
        # 验证ChromeDriver是否可执行
        if os.path.exists(chromedriver_path) and os.path.getsize(chromedriver_path) > 1000000:
            print(f"ChromeDriver下载成功: {chromedriver_path} / ChromeDriver downloaded successfully")
            
            # 在Windows上可能需要将.exe添加到路径中
            if system == "Windows" and not chromedriver_path.endswith('.exe'):
                os.rename(chromedriver_path, chromedriver_path + '.exe')
                chromedriver_path += '.exe'
            
            # 清理临时文件
            try:
                os.remove(zip_path)
            except:
                pass
                
            return chromedriver_path
        else:
            print(f"ChromeDriver下载或解压失败 / ChromeDriver download or extraction failed")
            return None
    
    except Exception as e:
        print(f"下载ChromeDriver时出错: {str(e)} / Error downloading ChromeDriver")
        return None

def get_chromedriver_path():
    """获取ChromeDriver路径，如果不存在则尝试下载 / Get ChromeDriver path, try to download if not exists"""
    system = platform.system()
    chromedriver_name = "chromedriver.exe" if system == "Windows" else "chromedriver"
    
    # 1. 首先检查用户是否在命令行指定了路径
    if "--driver" in sys.argv:
        for i, arg in enumerate(sys.argv):
            if arg == "--driver" and i+1 < len(sys.argv):
                driver_path = sys.argv[i+1]
                if os.path.exists(driver_path):
                    print(f"使用命令行指定的ChromeDriver: {driver_path} / Using command-line specified ChromeDriver")
                    return driver_path
                else:
                    print(f"⚠ 命令行指定的ChromeDriver不存在: {driver_path} / Command-line specified ChromeDriver does not exist")
    
    # 2. 检查全局配置中是否指定了路径
    if CHROMEDRIVER_PATH and os.path.exists(CHROMEDRIVER_PATH):
        print(f"使用全局配置的ChromeDriver: {CHROMEDRIVER_PATH} / Using global configuration ChromeDriver")
        return CHROMEDRIVER_PATH
    
    # 3. 查找系统PATH中的ChromeDriver
    print("在系统PATH中查找ChromeDriver... / Searching for ChromeDriver in system PATH...")
    
    path_dirs = os.environ["PATH"].split(os.pathsep)
    for path_dir in path_dirs:
        driver_path = os.path.join(path_dir, chromedriver_name)
        if os.path.exists(driver_path):
            print(f"✓ 在系统PATH中找到ChromeDriver: {driver_path} / Found ChromeDriver in system PATH")
            return driver_path
    
    # 4. 检查常见位置
    print("在常见位置查找ChromeDriver... / Searching for ChromeDriver in common locations...")
    check_locations = [
        # 当前目录
        os.path.abspath(chromedriver_name),
        # ChromeDriver目录
        os.path.abspath(os.path.join(CHROMEDRIVER_DIR, chromedriver_name)),
        # Windows可能的位置
        os.path.abspath(os.path.join(".", "chromedriver", chromedriver_name)),
        # 尝试更多可能的位置
        os.path.join(".", chromedriver_name),
        os.path.join("..", chromedriver_name),
        os.path.join("..", "bin", chromedriver_name),
        os.path.join("..", "drivers", chromedriver_name),
        os.path.join(os.path.expanduser("~"), chromedriver_name),
        os.path.join(os.path.expanduser("~"), "bin", chromedriver_name),
        os.path.join(os.path.expanduser("~"), "drivers", chromedriver_name),
        os.path.join(os.path.expanduser("~"), "Downloads", chromedriver_name)
    ]
    
    for location in check_locations:
        if os.path.exists(location):
            print(f"✓ 在常见位置找到ChromeDriver: {location} / Found ChromeDriver in common location")
            return location
    
    # 5. 如果设置了跳过下载，或在命令行指定了--skip-download，返回第一个检查位置
    if SKIP_DOWNLOAD or "--skip-download" in sys.argv:
        print(f"⚠ 已启用跳过下载选项，但未找到ChromeDriver / Skip download enabled, but ChromeDriver not found")
        default_path = os.path.join(".", chromedriver_name)
        print(f"返回默认路径: {default_path} / Returning default path")
        return default_path
    
    # 6. 如果都找不到，打印所有检查过的位置并提示下载
    print("✗ 所有以下路径均未找到ChromeDriver: / ChromeDriver not found in any of these paths:")
    for path_dir in path_dirs:
        print(f"  - {os.path.join(path_dir, chromedriver_name)}")
    for location in check_locations:
        print(f"  - {location}")
    print("将尝试下载ChromeDriver... / Will try to download ChromeDriver...")
    return download_chromedriver()

def load_download_status():
    """加载下载状态 / Load download status"""
    global _download_status_cache, _status_modified
    
    # 如果已缓存，直接返回缓存
    if _download_status_cache is not None:
        if isinstance(_download_status_cache, dict) and "downloaded_images" in _download_status_cache:
            return _download_status_cache
        else:
            print("缓存状态无效，将重新初始化 / Cache status invalid, will reinitialize")
    
    # 尝试从文件加载
    if os.path.exists(DOWNLOAD_STATUS_FILE):
        try:
            with open(DOWNLOAD_STATUS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 验证数据格式是否正确
                if isinstance(data, dict) and "downloaded_images" in data:
                    _download_status_cache = data
                    _status_modified = False
                    print("已从文件加载下载状态记录 / Download status loaded from file")
                    return _download_status_cache
                else:
                    print("下载状态文件格式无效，将使用新的状态 / Download status file has invalid format, will use new status")
        except Exception as e:
            print(f"加载下载状态失败: {str(e)} / Failed to load download status: {str(e)}")
    
    # 初始化新状态
    _download_status_cache = {"downloaded_images": {}}
    _status_modified = False
    print("初始化新的下载状态 / Initialized new download status")
    return _download_status_cache

def save_download_status(force=False):
    """
    保存下载状态 / Save download status
    
    Args:
        force (bool): 是否强制保存 / Whether to force save regardless of modification status
    """
    global _download_status_cache, _status_modified, _processed_count
    
    # 如果状态未修改且不是强制保存，则跳过
    if not _status_modified and not force:
        return
    
    # 确保目录存在
    if not os.path.exists(PICTURE_DIR):
        try:
            os.makedirs(PICTURE_DIR)
        except Exception as e:
            print(f"创建图片目录失败: {str(e)} / Failed to create image directory")
            return
    
    # 确保缓存有效
    if _download_status_cache is None or not isinstance(_download_status_cache, dict):
        print("下载状态缓存无效，无法保存 / Download status cache invalid, cannot save")
        return
    
    # 确保downloaded_images字段存在
    if "downloaded_images" not in _download_status_cache:
        _download_status_cache = {"downloaded_images": {}}
    
    try:
        with open(DOWNLOAD_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(_download_status_cache, f, ensure_ascii=False, indent=2)
        _status_modified = False
        _processed_count = 0
        print("✓ 下载状态已保存 / Download status saved")
    except Exception as e:
        print(f"保存下载状态失败: {str(e)} / Failed to save download status: {str(e)}")
        
        # 尝试备份保存，以防文件系统问题
        try:
            backup_file = f"{DOWNLOAD_STATUS_FILE}.bak"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(_download_status_cache, f, ensure_ascii=False, indent=2)
            print(f"✓ 下载状态已保存到备份文件: {backup_file} / Download status saved to backup file")
        except Exception as be:
            print(f"保存到备份文件也失败: {str(be)} / Failed to save to backup file as well")

def is_image_downloaded(category, image_id, image_index):
    """检查图片是否已下载 / Check if image is already downloaded"""
    global _download_status_cache, _status_modified
    
    try:
        # 确保缓存已初始化
        if _download_status_cache is None:
            _download_status_cache = load_download_status()
        
        # 进行空值检查，增强健壮性
        if not _download_status_cache or not isinstance(_download_status_cache, dict):
            print(f"下载状态缓存无效，重新初始化 / Download status cache invalid, reinitializing")
            _download_status_cache = {"downloaded_images": {}}
            _status_modified = True
        
        # 确保downloaded_images字段存在
        if "downloaded_images" not in _download_status_cache:
            _download_status_cache["downloaded_images"] = {}
            _status_modified = True
        
        # 首先检查内存中的状态
        image_key = f"id{image_id}_{image_index}"
        if category in _download_status_cache["downloaded_images"] and image_key in _download_status_cache["downloaded_images"][category]:
            # 再确认文件是否真的存在（防止状态不一致）
            for ext in ['.jpg', '.png', '.jpeg', '.webp', '.gif']:
                image_path = os.path.join(PICTURE_DIR, category, f"{image_key}{ext}")
                if os.path.exists(image_path) and os.path.getsize(image_path) > 10000:
                    return True
        
        # 检查文件是否存在但未记录（可能是之前下载但没记录状态）
        for ext in ['.jpg', '.png', '.jpeg', '.webp', '.gif']:
            image_path = os.path.join(PICTURE_DIR, category, f"{image_key}{ext}")
            if os.path.exists(image_path) and os.path.getsize(image_path) > 10000:
                # 更新缓存状态
                if category not in _download_status_cache["downloaded_images"]:
                    _download_status_cache["downloaded_images"][category] = {}
                _download_status_cache["downloaded_images"][category][image_key] = True
                _status_modified = True
                return True
        
        return False
    except Exception as e:
        print(f"检查图片下载状态时出错: {str(e)} / Error checking image download status")
        # 出错时默认返回False，这样图片会被重新下载，比丢失数据要好
        return False

def mark_image_downloaded(category, image_id, image_index):
    """标记图片为已下载 / Mark image as downloaded"""
    global _download_status_cache, _status_modified, _processed_count
    
    try:
        # 确保缓存已初始化
        if _download_status_cache is None:
            _download_status_cache = load_download_status()
        
        # 进行空值检查，增强健壮性
        if not _download_status_cache or not isinstance(_download_status_cache, dict):
            print(f"下载状态缓存无效，重新初始化 / Download status cache invalid, reinitializing")
            _download_status_cache = {"downloaded_images": {}}
            _status_modified = True
        
        # 确保downloaded_images字段存在
        if "downloaded_images" not in _download_status_cache:
            _download_status_cache["downloaded_images"] = {}
            _status_modified = True
        
        # 确保分类存在
        if category not in _download_status_cache["downloaded_images"]:
            _download_status_cache["downloaded_images"][category] = {}
        
        # 标记图片为已下载
        image_key = f"id{image_id}_{image_index}"
        _download_status_cache["downloaded_images"][category][image_key] = True
        _status_modified = True
        _processed_count += 1
        
        # 每处理一定数量的图片就保存一次状态
        if _processed_count >= STATUS_SAVE_INTERVAL:
            save_download_status()
    except Exception as e:
        print(f"标记图片下载状态时出错: {str(e)} / Error marking image download status")
        # 尝试强制保存当前状态
        try:
            save_download_status(force=True)
        except:
            pass

class SLDSpider:
    def __init__(self, chromedriver_path=None, auto_detect_ids=True):
        """初始化爬虫 / Initialize the crawler"""
        self.save_dirs = DEFAULT_SAVE_DIRS
        self._create_directories()  # 先创建目录
        self.driver = None
        self.max_ids = DEFAULT_MAX_IDS.copy()
        self.chromedriver_path = chromedriver_path
        
        # 先尝试初始化浏览器，如果失败再考虑其他方法
        if self._init_browser():
            # 尝试获取最大ID
            if auto_detect_ids:
                try:
                    self._get_max_ids()
                except Exception as e:
                    print(f"动态获取最大ID失败: {str(e)}，使用默认值 / Failed to get maximum IDs: {str(e)}, using default values")
    
    def _init_browser(self):
        """初始化浏览器，返回是否成功 / Initialize the browser, return whether successful"""
        print("\n初始化浏览器... / Initializing browser...")
        
        # 创建基本的Chrome选项 / Create basic Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--ignore-certificate-errors")  # 忽略SSL证书错误 / Ignore SSL certificate errors
        chrome_options.add_argument("--allow-insecure-localhost")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--ignore-ssl-errors=yes")
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # 使用随机User-Agent / Use random User-Agent
        user_agent = random_ua()["User-Agent"]
        chrome_options.add_argument(f"--user-agent={user_agent}")
        
        # 直接尝试使用系统中的chromedriver，不做过多检查 / Try to use chromedriver in the system directly, without too many checks
        try:
            # 方法1: 使用简单的Service调用，让系统自动查找 / Method 1: Use simple Service call, let system find automatically
            print("尝试让系统自动查找ChromeDriver... / Trying to let system find ChromeDriver automatically...")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)
            
            # 执行额外的反检测代码 / Execute additional anti-detection code
            self._apply_stealth_techniques()
            
            print("✓ 自动查找成功! / Automatic detection successful!")
            return True
        except Exception as e:
            print(f"系统自动查找失败: {str(e)} / System auto-detection failed")
        
        # 如果指定了ChromeDriver路径，直接尝试使用 / If ChromeDriver path is specified, try to use it directly
        if self.chromedriver_path:
            return self._try_init_with_driver(self.chromedriver_path, chrome_options)
        
        # 没有指定路径，尝试所有可能的位置 / No path specified, try all possible locations
        return self._try_local_drivers(chrome_options)
    
    def _apply_stealth_techniques(self):
        """
        应用反爬虫检测技术，修改浏览器特征以避免被检测
        Apply anti-detection techniques by modifying browser characteristics to avoid being detected
        """
        if not self.driver:
            return
            
        try:
            # 执行JavaScript来掩盖Selenium特征 / Execute JavaScript to hide Selenium characteristics
            self.driver.execute_script("""
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
                
                // 重写一些可能被用于检测的属性 / Rewrite some properties that might be used for detection
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
    
    def _try_local_drivers(self, chrome_options):
        """尝试所有可能的本地ChromeDriver / Try all possible local ChromeDriver"""
        system = platform.system()
        chromedriver_name = "chromedriver.exe" if system == "Windows" else "chromedriver"
        
        # 1. 尝试在常见位置查找ChromeDriver / 1. Try to find ChromeDriver in common locations
        check_locations = [
            # 当前目录和子目录 / Current directory and subdirectories
            os.path.abspath(chromedriver_name),
            os.path.abspath(os.path.join(CHROMEDRIVER_DIR, chromedriver_name)),
            os.path.abspath(os.path.join(".", "chromedriver", chromedriver_name)),
            # 其他常见位置 / Other common locations
            os.path.join(".", chromedriver_name),
            os.path.join("..", chromedriver_name),
            os.path.join(os.path.expanduser("~"), chromedriver_name),
            os.path.join(os.path.expanduser("~"), "Downloads", chromedriver_name)
        ]
        
        # 2. 添加系统PATH中的位置 / 2. Add locations from system PATH
        
        # 3. 逐个尝试每个位置 / 3. Try each location one by one
        
        # 4. 如果所有本地路径都失败，而且没有跳过下载选项，则尝试下载 / 4. If all local paths fail and skip download option is not enabled, try to download
        success = False
        for location in check_locations:
            if os.path.exists(location):
                print(f"尝试ChromeDriver: {location} / Trying ChromeDriver")
                if self._try_init_with_driver(location, chrome_options):
                    success = True
                    break
        
        # 4. 如果所有本地路径都失败，而且没有跳过下载选项，则尝试下载 / 4. If all local paths fail and skip download option is not enabled, try to download
        if not success and not SKIP_DOWNLOAD and "--skip-download" not in sys.argv:
            print("所有本地ChromeDriver尝试失败，将下载新版本 / All local ChromeDriver attempts failed, will download new version")
            new_driver_path = download_chromedriver()
            if new_driver_path:
                success = self._try_init_with_driver(new_driver_path, chrome_options)
        
        return success
    
    def _try_init_with_driver(self, driver_path, chrome_options):
        """尝试使用指定的ChromeDriver初始化浏览器 / Try to initialize browser with specified ChromeDriver"""
        if not os.path.exists(driver_path):
            return False
            
        # 设置执行权限（非Windows系统） / Set execution permissions (non-Windows systems)
        if platform.system() != "Windows":
            try:
                os.chmod(driver_path, 0o755)
            except:
                pass
                
        print(f"初始化浏览器，使用: {driver_path} / Initializing browser using ChromeDriver")
        
        try:
            # 尝试使用Service方式初始化 / Try to initialize using Service method
            service = Service(executable_path=driver_path, log_path=os.path.devnull)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)
            
            # 应用反检测技术 / Apply anti-detection techniques
            self._apply_stealth_techniques()
            
            print("✓ 浏览器初始化成功 / Browser initialized successfully")
            # 保存成功的路径供后续使用 / Save successful path for later use
            self.chromedriver_path = driver_path
            return True
        except Exception as e:
            print(f"常规初始化失败: {str(e)} / Regular initialization failed")
            
            try:
                # 尝试兼容模式（适用于旧版本Selenium） / Try compatibility mode (for older Selenium versions)
                print("尝试兼容模式 / Trying compatibility mode")
                os.environ["webdriver.chrome.driver"] = driver_path
                self.driver = webdriver.Chrome(options=chrome_options)
                self.wait = WebDriverWait(self.driver, 20)
                
                # 应用反检测技术 / Apply anti-detection techniques
                self._apply_stealth_techniques()
                
                print("✓ 浏览器初始化成功（兼容模式） / Browser initialized successfully (compatibility mode)")
                self.chromedriver_path = driver_path
                return True
            except Exception as e2:
                print(f"兼容模式也失败: {str(e2)} / Compatibility mode also failed")
                return False
    
    def _get_max_ids(self):
        """动态获取每个分类的最大ID / Dynamically get maximum IDs for each category"""
        print("获取各分类最大ID / Getting maximum IDs for each category")
        
        for category in self.save_dirs:
            try:
                category_url = f"https://www.sldgroup.com/tc/{category}.aspx"
                print(f"访问分类页面 / Visiting category page: {category_url}")
                self.driver.get(category_url)
                time.sleep(3)
                
                # 使用指定的XPath获取所有项目列表项
                try:
                    # 等待页面元素加载
                    self.wait.until(EC.presence_of_element_located((By.ID, "mWorkDiv")))
                    
                    # 使用用户提供的XPath获取所有项目链接
                    project_links = self.driver.find_elements(By.XPATH, '//*[@id="mWorkDiv"]/li/a')
                    
                    if not project_links:
                        print(f"分类 {category} 未找到项目链接，尝试其他方法 / No project links found for {category}, trying other methods")
                        # 尝试直接使用JavaScript获取
                        project_links_js = self.driver.execute_script("""
                            return Array.from(document.querySelectorAll('#mWorkDiv li a')).map(a => a.href);
                        """)
                        
                        # 打印调试信息 / Print debug information
                        print(f"JavaScript找到链接数: {len(project_links_js) if project_links_js else 0} / JavaScript found links count")
                        
                        if project_links_js:
                            max_id = 0
                            id_pattern = re.compile(r'id=(\d+)')
                            
                            for link in project_links_js:
                                match = id_pattern.search(link)
                                if match:
                                    id_value = int(match.group(1))
                                    if id_value > max_id:
                                        max_id = id_value
                            
                            if max_id > 0:
                                self.max_ids[category] = max_id
                                print(f"分类 {category} 的最大ID为 / Maximum ID for {category} is: {max_id}")
                            continue  # 继续下一个分类
                    
                    # 从项目链接中提取ID并找出最大值
                    max_id = 0
                    for link in project_links:
                        href = link.get_attribute('href')
                        # 打印调试信息 / Print debug information
                        print(f"找到链接 / Found link: {href}")
                        
                        # 使用正则表达式提取ID
                        match = re.search(r'id=(\d+)', href)
                        if match:
                            id_value = int(match.group(1))
                            if id_value > max_id:
                                max_id = id_value
                    
                    if max_id > 0:
                        self.max_ids[category] = max_id
                        print(f"分类 {category} 的最大ID为 / Maximum ID for {category} is: {max_id}")
                
                except Exception as e:
                    print(f"处理分类 {category} 时出错: {str(e)} / Error processing category {category}: {str(e)}")
                    # 这里可以添加更多的错误处理逻辑 / More error handling logic can be added here
            
            except Exception as e:
                print(f"访问分类 {category} 时出错: {str(e)} / Error visiting category {category}: {str(e)}")
        
    def _create_directories(self):
        """创建保存图片的目录 / Create directories for saving images"""
        if not os.path.exists(PICTURE_DIR):
            os.makedirs(PICTURE_DIR)
        
        for save_dir in self.save_dirs:
            dir_path = os.path.join(PICTURE_DIR, save_dir)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

    def _download_images(self, save_dir, project_detail_url, project_id):
        """下载项目页面中的所有图片 / Download all images in the project page"""
        # 重置当前项目的重试记录
        global _current_project_retries, _download_status_cache, _status_modified
        _current_project_retries = {}
        
        # 首先检查该项目是否已有部分图片被下载
        existing_count = self._get_project_image_count(save_dir, project_id)
        if existing_count > 0:
            print(f"  • 已有 {existing_count} 张图片被下载 / Already have {existing_count} images downloaded")
            
            # 再次确认是否所有图片都已下载
            all_downloaded = True
            for idx in range(existing_count):
                if not is_image_downloaded(save_dir, project_id, idx):
                    all_downloaded = False
                    print(f"  • 图片 {idx} 缺失，需要重新下载 / Image {idx} missing, need to download")
                    break
            
            if all_downloaded:
                print(f"  ✓ 所有 {existing_count} 张图片已下载，跳过 / All {existing_count} images downloaded, skipping")
                return
            else:
                print(f"  • 图片不完整，继续下载 / Images incomplete, continuing download")
        
        # 加载页面时的重试机制（使用指数退避） / Retry mechanism for page loading (using exponential backoff)
        page_loaded = False
        retry_count = 0
        max_retries = MAX_PAGE_RETRIES  # 增加最大重试次数
        
        while not page_loaded and retry_count <= max_retries:
            try:
                if retry_count > 0:
                    # 使用指数退避算法，等待时间随着重试次数增加而增加 / Using exponential backoff algorithm, increase wait time with retry count
                    wait_time = min(30, 2 ** retry_count)  # 最大等待30秒 / Maximum wait time is 30 seconds
                    print(f"重试加载页面 ({retry_count}/{max_retries})... 等待{wait_time}秒 / Retrying page load, waiting {wait_time}s")
                    time.sleep(wait_time)
                    
                    # 在重试时更换随机UA，减少被识别为爬虫的可能 / Change random UA during retry to reduce the chance of being detected as a crawler
                    new_ua = random_ua()["User-Agent"]
                    self.driver.execute_script(f"Object.defineProperty(navigator, 'userAgent', {{get: function() {{return '{new_ua}';}}}});")
                
                # 可以尝试清除cookies，模拟新的会话 / Can try to clear cookies to simulate a new session
                if retry_count >= 2:
                    print("清除cookies，模拟新会话 / Clearing cookies to simulate new session")
                    self.driver.delete_all_cookies()
                
                # 访问页面
                self.driver.get(project_detail_url)
                print(f"等待页面加载... / Waiting for page loading...")
                
                # 增加页面加载等待时间和检测更多可能的元素 / Increase page load wait time and detect more possible elements
                try:
                    # 调整超时时间，基于重试次数动态增加
                    timeout = 20 + (retry_count * 5)  # 20 + 0/5/10/15/20秒
                    wait = WebDriverWait(self.driver, timeout)
                    
                    # 尝试多种可能的元素检测页面加载 / Try multiple possible elements to detect page loading
                    selectors = [
                        (By.XPATH, '//*[@id="mSwiperDiv"]/div'),
                        (By.CLASS_NAME, 'swiper-slide'),
                        (By.CLASS_NAME, 'getWidth'),
                        (By.ID, 'mSwiperDiv')
                    ]
                    
                    for selector_type, selector in selectors:
                        try:
                            wait.until(EC.presence_of_element_located((selector_type, selector)))
                            page_loaded = True
                            print(f"页面加载完成，使用选择器: {selector} / Page loaded using selector")
                            break
                        except:
                            continue
                            
                    # 如果选择器检测都失败，但页面有内容，也认为加载成功 / If selector detection fails but page has content, consider loading successful
                    if not page_loaded and len(self.driver.page_source) > 1000:
                        print("页面内容已加载，尝试继续处理 / Page content loaded, trying to proceed")
                        page_loaded = True
                        
                except Exception as inner_e:
                    # 如果还是失败，抛出原始异常 / If still fails, throw the original exception
                    raise inner_e
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    print(f"页面加载失败，已达到最大重试次数: {str(e)} / Page loading failed, max retries reached: {str(e)}")
                    # 如果所有尝试都失败，则这个链接可能是无效的，抛出异常让上层函数尝试其他URL格式 / If all attempts fail, this link may be invalid, raise exception for upper function to try other URL formats
                    raise Exception(f"页面加载失败: {str(e)} / Page loading failed")
                print(f"页面加载错误，将重试: {str(e)} / Page loading error, will retry: {str(e)}")
        
        try:
            # 寻找所有图片元素 - 尝试多种可能的选择器 / Find all image elements - try multiple possible selectors
            image_elements = []
            possible_selectors = [
                '//*[@id="mSwiperDiv"]/div/img',
                '//div[@class="swiper-slide"]//img',
                '//img[@class="getWidth"]',
                '//*[@id="mSwiperDiv"]//img',
                '//img[contains(@src, "Work/Detail")]'  # 更宽泛的选择器，基于图片路径特征
            ]
            
            for selector in possible_selectors:
                try:
                    found_elements = self.driver.find_elements(By.XPATH, selector)
                    if found_elements:
                        # 排除空src的元素 / Exclude elements with empty src
                        valid_elements = [e for e in found_elements if e.get_attribute('src') and e.get_attribute('src').strip() != '']
                        if valid_elements:
                            image_elements = valid_elements
                            print(f"使用选择器 {selector} 找到 {len(image_elements)} 个图片 / Found images using selector")
                            break
                except:
                    continue
            
            # 如果所有选择器都失败，尝试使用JavaScript直接提取所有图片 / If all selectors fail, try to extract all images directly using JavaScript
            if not image_elements:
                try:
                    print("尝试使用JavaScript提取图片 / Trying to extract images using JavaScript")
                    js_images = self.driver.execute_script("""
                        return Array.from(document.querySelectorAll('img'))
                               .filter(img => img.src && img.src.includes('Work/Detail'))
                               .map(img => img);
                    """)
                    if js_images:
                        image_elements = js_images
                        print(f"通过JavaScript找到 {len(image_elements)} 个图片 / Found images using JavaScript")
                except Exception as js_e:
                    print(f"JavaScript提取图片失败: {str(js_e)} / JavaScript image extraction failed")
            
            if not image_elements:
                print(f"未找到图片，可能是空项目或无效URL / No images found, might be an empty project or invalid URL")
                return
            
            # 找到新的图片数量，更新到项目数据中
            total_image_count = len(image_elements)
            if total_image_count > existing_count:
                # 更新项目图片数量信息
                print(f"发现新图片：原有{existing_count}张，现有{total_image_count}张 / Found new images: had {existing_count}, now {total_image_count}")
            
            print(f"找到 {total_image_count} 个图片 / Found {total_image_count} images")
            
            # 创建图片状态追踪
            image_status = {
                "total": total_image_count,
                "downloaded": 0,
                "skipped": 0,
                "failed": 0,
                "retried": 0,
                "details": []
            }
            
            # 保存总数到缓存，这样其他函数可以使用这个信息 / Save total count to cache so other functions can use this information
            if f"{save_dir}_image_counts" not in _download_status_cache:
                _download_status_cache[f"{save_dir}_image_counts"] = {}
            _download_status_cache[f"{save_dir}_image_counts"][str(project_id)] = total_image_count
            _status_modified = True
            
            # 获取项目基础URL，用于构建完整图片URL
            base_url = "https://www.sldgroup.com"
            
            for idx, img_element in enumerate(image_elements):
                image_info = {
                    "index": idx,
                    "path": f"{save_dir}/id{project_id}_{idx}",  # 先不添加扩展名，等确定后再添加
                    "status": "pending",
                    "retries": 0
                }
                
                # 单张图片处理的重试机制
                img_retry_count = 0
                max_img_retries = MAX_IMG_RETRIES
                img_processed = False
                
                while not img_processed and img_retry_count <= max_img_retries:
                    try:
                        # 检查图片是否已下载（检查多种可能的扩展名）
                        if is_image_downloaded(save_dir, project_id, idx):
                            print(f"• 图片 {idx+1}/{len(image_elements)} 已存在，跳过 [id{project_id}_{idx}.*] / Skip existing image")
                            image_info["status"] = "skipped"
                            image_info["reason"] = "already exists"
                            image_status["skipped"] += 1
                            img_processed = True
                            break  # 已存在则跳出重试循环
                        
                        if img_retry_count > 0:
                            # 重试等待也使用指数退避
                            retry_wait = min(10, (img_retry_count * 2))
                            print(f"• 重试图片 {idx+1}/{len(image_elements)} [id{project_id}_{idx}] ({img_retry_count}/{max_img_retries}) 等待{retry_wait}秒 / Retrying image, waiting {retry_wait}s")
                            image_status["retried"] += 1
                            time.sleep(retry_wait)
                        else:
                            print(f"• 处理图片 {idx+1}/{len(image_elements)} [id{project_id}_{idx}] / Processing image")
                        
                        # 获取图片src属性
                        img_src = img_element.get_attribute('src')
                        if not img_src or img_src.strip() == '':
                            print(f"  ✗ 图片URL为空 / Empty image URL")
                            img_retry_count += 1
                            if img_retry_count > max_img_retries:
                                image_info["status"] = "failed"
                                image_info["reason"] = "empty src attribute (after retries)"
                                image_status["failed"] += 1
                                img_processed = True
                            else:
                                time.sleep(2)  # 等待2秒后重试
                            continue
                        
                        # 处理相对URL
                        if img_src.startswith("../"):
                            img_url = f"{base_url}/{img_src.replace('../', '', 1)}"
                        elif img_src.startswith("/"):
                            img_url = f"{base_url}{img_src}"
                        elif not img_src.startswith(("http://", "https://")):
                            img_url = f"{base_url}/{img_src}"
                        else:
                            img_url = img_src
                            
                        # 打印源URL
                        print(f"  • 源URL: {img_url} / Source URL")
                        
                        # 从URL确定文件扩展名（默认为jpg，但如果URL中包含其他扩展名则使用它）
                        file_ext = ".jpg"  # 默认扩展名
                        for ext in ['.png', '.jpeg', '.gif', '.webp']:
                            if img_url.lower().endswith(ext):
                                file_ext = ext
                                break
                        
                        # 完整的保存路径 / Complete save path
                        img_save_path = os.path.join(PICTURE_DIR, save_dir, f"id{project_id}_{idx}{file_ext}")
                        image_info["path"] = f"{save_dir}/id{project_id}_{idx}{file_ext}"
                        
                        # 下载图片 / Download image
                        print(f"  • 正在下载原始图片 ({file_ext}) / Downloading original image")
                        headers = {
                            'User-Agent': random_ua()["User-Agent"],
                            'Referer': project_detail_url,
                            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Connection': 'keep-alive'
                        }
                        
                        try:
                            response = requests.get(
                                img_url, 
                                headers=headers, 
                                stream=True, 
                                timeout=REQUEST_TIMEOUT,
                                verify=False  # 忽略SSL证书验证
                            )
                            if response.status_code == 200:
                                with open(img_save_path, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                            else:
                                raise Exception(f"HTTP状态码: {response.status_code} / HTTP status code")
                        except Exception as download_err:
                            print(f"  ✗ 图片下载出错: {str(download_err)} / Download error")
                            img_retry_count += 1
                            if img_retry_count > max_img_retries:
                                image_info["status"] = "failed"
                                image_info["reason"] = f"download error: {str(download_err)} (after retries)"
                                image_status["failed"] += 1
                                img_processed = True
                            else:
                                time.sleep(2)  # 等待2秒后重试
                            continue
                        
                        # 检查保存结果
                        if os.path.exists(img_save_path) and os.path.getsize(img_save_path) > 10000:
                            # 更新下载状态记录 / Update download status record
                            mark_image_downloaded(save_dir, project_id, idx)
                            
                            print(f"  ✓ 成功保存图片{' (重试成功)' if img_retry_count > 0 else ''} / Image saved successfully{' (retry succeeded)' if img_retry_count > 0 else ''}")
                            image_info["status"] = "success"
                            image_info["retries"] = img_retry_count
                            image_status["downloaded"] += 1
                            img_processed = True
                        else:
                            print(f"  ✗ 图片保存失败或太小 (< 10KB) / Image save failed or too small")
                            img_retry_count += 1
                            if img_retry_count > max_img_retries:
                                image_info["status"] = "failed"
                                image_info["reason"] = "save failed or file too small (after retries)"
                                image_status["failed"] += 1
                                img_processed = True
                            else:
                                # 如果文件存在但太小，删除它再重试 / If file exists but is too small, delete it and retry
                                if os.path.exists(img_save_path):
                                    os.remove(img_save_path)
                                time.sleep(2)  # 等待2秒后重试
                            
                    except Exception as e:
                        print(f"  ✗ 图片处理出错: {str(e)} / Error processing image")
                        img_retry_count += 1
                        if img_retry_count > max_img_retries:
                            image_info["status"] = "failed"
                            image_info["reason"] = f"{str(e)} (after retries)"
                            image_status["failed"] += 1
                            img_processed = True
                        else:
                            time.sleep(2)  # 等待2秒后重试
                
                image_info["retries"] = img_retry_count
                image_status["details"].append(image_info)
                
                # 更加随机的等待时间，避免请求过于规律 / More random wait time to avoid regular request patterns
                time.sleep(random.uniform(MIN_WAIT_TIME, MAX_WAIT_TIME))
            
            # 打印下载总结 / Print download summary
            print(f"\n下载总结 / Download summary:")
            print(f"• 总图片数: {image_status['total']} / Total images")
            print(f"• 成功下载: {image_status['downloaded']} / Successfully downloaded")
            print(f"• 已存在跳过: {image_status['skipped']} / Skipped (already exists)")
            print(f"• 重试次数: {image_status['retried']} / Retries")
            print(f"• 下载失败: {image_status['failed']} / Failed")
            
            if image_status['failed'] > 0:
                print("\n失败详情 / Failure details:")
                for img in image_status["details"]:
                    if img["status"] == "failed":
                        print(f"• {img['path']} - 原因: {img['reason']}")
            
            # 每处理完一个项目，强制保存状态 / After processing each project, force save the status
            save_download_status(force=True)
            
        except Exception as e:
            print(f"下载过程中出错 / Error during download: {str(e)}")
            # 强制保存状态，确保不丢失进度
            save_download_status(force=True)
    
    def crawl_and_download(self):
        """爬取并下载所有分类的图片 / Crawl and download images for all categories"""
        try:
            # 确保max_ids有效 / Ensure max_ids is valid
            if not self.max_ids:
                print("警告：max_ids为空，使用默认值 / Warning: max_ids is empty, using default values")
                self.max_ids = DEFAULT_MAX_IDS.copy()
                
            # 确保下载状态缓存已初始化 / Ensure download status cache is initialized
            global _download_status_cache
            if _download_status_cache is None:
                _download_status_cache = load_download_status()
                
            # 分类循环，每个分类独立处理，一个分类出错不影响其他分类 / Category loop, each category is processed independently, an error in one category does not affect others
            for category, max_id in self.max_ids.items():
                if category not in self.save_dirs:
                    continue
                
                print(f"\n开始处理分类 / Starting category: {category}")
                try:
                    for project_id in range(1, max_id + 1):
                        try:
                            # 先检查该项目是否已全部下载
                            if self._is_project_fully_downloaded(category, project_id):
                                print(f"项目 {project_id}/{max_id} 所有图片已下载，跳过 / Project {project_id}/{max_id} all images already downloaded, skipping")
                                continue
                            
                            # 简化URL构建，使用网站实际使用的格式
                            print(f"处理项目 / Processing project: {project_id}/{max_id}")
                            
                            # 针对销售中心使用正确的URL格式
                            if category == "salesoffice":
                                url = f"https://www.sldgroup.com/tc/salesoffice-detail.aspx?id={project_id}"
                            else:
                                url = f"https://www.sldgroup.com/tc/{category}-detail.aspx?id={project_id}"
                                
                            print(f"使用URL: {url} / Using URL")
                            try:
                                self._download_images(category, url, project_id)
                            except Exception as url_e:
                                print(f"项目下载失败: {url} - {str(url_e)} / Project download failed")
                                # 继续处理下一个项目
                                continue
                            
                            # 更随机的等待时间，避免触发反爬 / More random wait time to avoid triggering anti-crawling
                            wait_time = random.uniform(MIN_WAIT_TIME * 2, MAX_WAIT_TIME * 2)
                            print(f"等待 {wait_time:.1f} 秒后继续... / Waiting {wait_time:.1f}s before continuing...")
                            time.sleep(wait_time)
                            
                        except Exception as project_e:
                            print(f"处理项目 {project_id} 时出错: {str(project_e)} / Error processing project")
                            # 出错了也要保存状态
                            save_download_status(force=True)
                            # 继续处理下一个项目
                            continue
                    
                    print(f"完成分类 / Completed category: {category}")
                    # 每完成一个分类，强制保存状态 / After completing each category, force save the status
                    save_download_status(force=True)
                    
                except Exception as category_e:
                    print(f"处理分类 {category} 时出错: {str(category_e)} / Error processing category")
                    # 出错了也要保存状态
                    save_download_status(force=True)
                    # 继续处理下一个分类
                    continue
            
            print("\n所有分类爬取完成 / All categories crawled")
            # 最终保存状态 / Final save status
            save_download_status(force=True)
            
        except Exception as e:
            print(f"爬取过程中出错 / Error during crawl: {str(e)}")
            # 即使出错也保存当前状态 / Save current status even if there is an error
            save_download_status(force=True)
        finally:
            self.cleanup()
            
    def _is_project_fully_downloaded(self, category, project_id):
        """检查项目的所有图片是否已下载 / Check if all images of a project are already downloaded"""
        global _download_status_cache
        
        # 确保缓存已初始化
        if _download_status_cache is None:
            _download_status_cache = load_download_status()
        
        # 获取该项目已知图片数量
        known_image_count = self._get_project_image_count(category, project_id)
        
        # 如果已知有图片，则检查这些图片是否都已下载
        if known_image_count > 0:
            # 检查所有已知索引的图片是否都存在
            for idx in range(known_image_count):
                if not is_image_downloaded(category, project_id, idx):
                    return False  # 只要有一张未下载，就返回False
            # 所有图片都已下载
            print(f"  • 检测到项目有 {known_image_count} 张图片且全部已下载 / Detected project has {known_image_count} images and all downloaded")
            return True
        
        # 没有已知数量，使用保守策略：项目中通常有5张图片，如果前5张都存在，认为已下载
        # No known count, use conservative strategy: projects typically have 5 images, if the first 5 exist, consider it downloaded
        expected_image_count = 5
        
        # 检查是否有连续的图片记录
        found_images = 0
        for idx in range(expected_image_count):
            if is_image_downloaded(category, project_id, idx):
                found_images += 1
            else:
                break  # 遇到第一个不存在的图片就停止
        
        # 保守策略：如果找到的图片数量与预期相同，认为已全部下载
        if found_images == expected_image_count:
            print(f"  • 检测到项目已下载 {found_images} 张图片，符合预期数量 / Detected project has {found_images} images downloaded, meets expected count")
            return True
        
        # 否则需要访问页面
        return False
    
    def _get_project_image_count(self, category, project_id):
        """从历史记录或文件系统获取项目的图片数量 / Get the image count of a project from history or filesystem"""
        global _download_status_cache, _status_modified
        
        # 确保缓存已初始化
        if _download_status_cache is None:
            _download_status_cache = load_download_status()
            
        # 进行空值检查，增强健壮性
        if not _download_status_cache or not isinstance(_download_status_cache, dict):
            print(f"  • 下载状态缓存无效，重新初始化 / Download status cache invalid, reinitializing")
            _download_status_cache = {"downloaded_images": {}}
            _status_modified = True
        
        # 确保downloaded_images字段存在
        if "downloaded_images" not in _download_status_cache:
            _download_status_cache["downloaded_images"] = {}
            _status_modified = True
        
        # 使用缓存机制，避免重复检查
        # 如果已经有缓存的图片数量，直接返回 / If there is already a cached image count, return it directly
        try:
            if f"{category}_image_counts" in _download_status_cache and str(project_id) in _download_status_cache[f"{category}_image_counts"]:
                count = _download_status_cache[f"{category}_image_counts"][str(project_id)]
                print(f"  • 从缓存获取项目图片数量: {count} / Got project image count from cache: {count}")
                return count
        except Exception as e:
            print(f"  • 读取缓存图片数量失败: {str(e)} / Failed to read cache image count")
            # 继续执行下面的代码，尝试其他方法获取图片数量
        
        # 1. 从下载状态缓存中尝试获取
        try:
            if category in _download_status_cache["downloaded_images"]:
                # 查找形如 id{project_id}_X 的键，找出最大的X+1
                max_index = -1
                for key in _download_status_cache["downloaded_images"][category].keys():
                    if key.startswith(f"id{project_id}_"):
                        try:
                            index = int(key.split('_')[1])
                            max_index = max(max_index, index)
                        except:
                            pass
                
                if max_index >= 0:
                    count = max_index + 1  # 最大索引+1就是图片数量
                    
                    # 保存到缓存
                    try:
                        if f"{category}_image_counts" not in _download_status_cache:
                            _download_status_cache[f"{category}_image_counts"] = {}
                        _download_status_cache[f"{category}_image_counts"][str(project_id)] = count
                        _status_modified = True
                    except Exception as e:
                        print(f"  • 保存图片数量到缓存失败: {str(e)} / Failed to save image count to cache")
                    
                    return count
        except Exception as e:
            print(f"  • 从下载状态缓存获取图片数量失败: {str(e)} / Failed to get image count from download status cache")
        
        # 2. 如果缓存中没有，从文件系统查找
        try:
            max_index = -1
            for idx in range(20):  # 假设最多20张图片
                for ext in ['.jpg', '.png', '.jpeg', '.webp', '.gif']:
                    image_path = os.path.join(PICTURE_DIR, category, f"id{project_id}_{idx}{ext}")
                    if os.path.exists(image_path) and os.path.getsize(image_path) > 10000:
                        max_index = max(max_index, idx)
                        break
            
            if max_index >= 0:
                count = max_index + 1  # 最大索引+1就是图片数量
                
                # 保存到缓存
                try:
                    if f"{category}_image_counts" not in _download_status_cache:
                        _download_status_cache[f"{category}_image_counts"] = {}
                    _download_status_cache[f"{category}_image_counts"][str(project_id)] = count
                    _status_modified = True
                except Exception as e:
                    print(f"  • 保存图片数量到缓存失败: {str(e)} / Failed to save image count to cache")
                
                return count
        except Exception as e:
            print(f"  • 从文件系统获取图片数量失败: {str(e)} / Failed to get image count from filesystem")
        
        # 3. 没有找到任何图片
        return 0
    
    def cleanup(self):
        """
        清理资源，关闭浏览器
        Clean up resources and close the browser
        """
        if self.driver:
            self.driver.quit()

def main():
    """
    主函数，处理命令行参数并启动爬虫
    Main function that processes command-line arguments and starts the crawler
    """
    try:
        global SKIP_DOWNLOAD, CHROMEDRIVER_PATH
        
        # 解析命令行参数 / Parse command line arguments
        for i, arg in enumerate(sys.argv):
            if arg == "--driver" and i+1 < len(sys.argv):
                CHROMEDRIVER_PATH = sys.argv[i+1]
                print(f"使用命令行指定的ChromeDriver: {CHROMEDRIVER_PATH} / Using command-line specified ChromeDriver: {CHROMEDRIVER_PATH}")
            elif arg == "--skip-download":
                SKIP_DOWNLOAD = True
                print("已启用跳过下载选项 / Skip download option enabled")
        
        print("SLD集团网站图片爬虫 / SLD Group Website Image Crawler")
        print("支持自动下载ChromeDriver和断点续传功能 / Auto-downloads ChromeDriver and supports resume download")
        
        # 显示使用帮助 / Show usage help
        if "--help" in sys.argv or "-h" in sys.argv:
            print("\n使用方法 / Usage:")
            print("  python sldgroup-spider.py [选项 / options]")
            print("\n选项 / Options:")
            print("  --driver PATH       指定ChromeDriver路径 / Specify ChromeDriver path")
            print("  --skip-download     跳过下载，仅尝试本地ChromeDriver / Skip download, only try local ChromeDriver")
            print("  --help, -h          显示此帮助信息 / Show this help message")
            return
        
        # 确保目录存在 / Ensure directory exists
        if not os.path.exists(PICTURE_DIR):
            os.makedirs(PICTURE_DIR)
        
        # 直接初始化爬虫，让Selenium自动寻找ChromeDriver / Initialize spider, let Selenium find ChromeDriver automatically
        spider = SLDSpider(chromedriver_path=CHROMEDRIVER_PATH, auto_detect_ids=True)
        
        # 检查爬虫是否成功初始化 / Check if spider is successfully initialized
        if not spider.driver:
            print("\n自动检测失败，正在尝试更多方法... / Automatic detection failed, trying more methods...")
            # 尝试使用get_chromedriver_path找到ChromeDriver / Try to find ChromeDriver using get_chromedriver_path
            detected_path = get_chromedriver_path()
            if detected_path:
                print(f"尝试使用检测到的ChromeDriver: {detected_path} / Trying detected ChromeDriver: {detected_path}")
                spider = SLDSpider(chromedriver_path=detected_path, auto_detect_ids=True)
        
        # 最终检查 / Final check
        if not spider.driver:
            raise Exception("无法初始化浏览器，请确保已安装最新的Chrome并将ChromeDriver放在正确位置 / Cannot initialize browser, please make sure Chrome is installed and ChromeDriver is in the correct location")
            
        # 爬取并下载图片 / Crawl and download images
        spider.crawl_and_download()
        
        print("\n爬取完成 / Crawling completed")
        print(f"图片保存在 / Images saved in: {os.path.abspath(PICTURE_DIR)}")
    
    except KeyboardInterrupt:
        print("\n用户中断爬取过程 / User interrupted the crawling process")
    except Exception as e:
        print(f"\n爬取过程中出错 / Error during crawling: {str(e)}")
        print("\n可能的解决方法 / Possible solutions:")
        print("1. 确保已安装Chrome浏览器 / Make sure Chrome browser is installed")
        print("2. 下载与Chrome版本匹配的ChromeDriver并放在程序目录 / Download ChromeDriver matching Chrome version and place it in program directory:")
        print("   下载地址 / Download from: https://registry.npmmirror.com/binary.html?path=chromedriver/")
        print("3. 使用命令行选项指定ChromeDriver路径 / Use command line option to specify ChromeDriver path:")
        print("   python sldgroup-spider.py --driver /path/to/chromedriver")
        print("4. 如果您已经有ChromeDriver但自动检测失败，请使用命令行选项手动指定路径 / If you already have ChromeDriver but auto-detection fails, manually specify the path")

if __name__ == "__main__":
    main() 
