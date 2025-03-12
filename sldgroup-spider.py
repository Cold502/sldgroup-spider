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
from webdriver import init_browser, cleanup_browser

# 全局配置 / Global Configuration
PICTURE_DIR = 'picture'  # 主图片目录 / Main image directory
DEFAULT_SAVE_DIRS = ["salesoffice", "residential", "clubhouse", "hospitality", "commercial"]

# 默认子页面URL最大ID / Maximum ID for subpages (will be updated dynamically if possible)
DEFAULT_MAX_IDS = {
    "salesoffice": 12,  # 销售中心 / Sales Office
    "residential": 34,  # 住宅 / Residential
    "clubhouse": 7,     # 会所 / Clubhouse
    "hospitality": 24,  # 酒店 / Hospitality
    "commercial": 18    # 商业 / Commercial
}

# URL路径映射（确保使用正确的URL格式）/ URL path mapping (ensure correct URL format)
URL_PATH_MAPPING = {
    "salesoffice": "saleoffice",  # 特殊情况：销售中心URL路径是saleoffice而非salesoffice
    # 其他分类使用相同的名称
}

# ChromeDriver配置 / ChromeDriver Configuration
CHROMEDRIVER_PATH = None  # 设置为None则自动查找，或手动指定路径 / Set to None for auto-detection, or manually specify the path
CHROMEDRIVER_VERSION = "134.0.6998.88"  # 默认使用更新的ChromeDriver版本 / Default to newer ChromeDriver version
CHROMEDRIVER_DIR = "chromedriver"  # ChromeDriver下载目录 / Download directory
SKIP_DOWNLOAD = False  # 设置为True跳过下载，强制使用本地ChromeDriver / Set to True to skip download and force using local ChromeDriver

# 爬取设置 / Crawler Settings
MAX_PAGE_RETRIES = 5       # 页面加载最大重试次数 / Maximum page load retries
MAX_IMG_RETRIES = 3        # 图片下载最大重试次数 / Maximum image download retries
REQUEST_TIMEOUT = 5       # 请求超时时间(秒) / Request timeout in seconds
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
    return get_chromedriver_path()

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
        _status_modified = True
    
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
    def __init__(self, chromedriver_path=None):
        """初始化爬虫 / Initialize the crawler"""
        self.save_dirs = DEFAULT_SAVE_DIRS
        # 直接创建保存图片的目录 / Create directories for saving images
        if not os.path.exists(PICTURE_DIR):
            os.makedirs(PICTURE_DIR)
        for d in self.save_dirs:
            dir_path = os.path.join(PICTURE_DIR, d)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

        self.driver = None
        self.chromedriver_path = chromedriver_path

        # 初始化浏览器 / Initialize browser
        driver_tuple = init_browser(self.chromedriver_path)
        if driver_tuple and driver_tuple[0]:
            self.driver, self.wait = driver_tuple
        else:
            print("浏览器初始化失败 / Browser initialization failed")

    def _download_images(self, save_dir, project_detail_url, project_id):
        """下载项目页面中的所有图片 / Download all images in the project page"""
        global _current_project_retries, _download_status_cache, _status_modified
        _current_project_retries = {}

        # 强制加载当前项目详情页，确保页面正确
        print(f"加载项目详情页: {project_detail_url} / Loading project detail page: {project_detail_url}")
        self.driver.get(project_detail_url)
        time.sleep(3)

        # 通过aria-label获取图片总数
        current_url = self.driver.current_url
        if f"id={project_id}" not in current_url:
            print(f"当前页面URL不包含期望的项目id({project_id}), 重新加载详情页: {project_detail_url}")
            self.driver.get(project_detail_url)
            time.sleep(3)
        try:
            print(f"已进入子页面, 当前URL: {self.driver.current_url} / Entered subpage, current URL")
            element = self.wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='mSwiperDiv']/div[1]")))
            aria_label = element.get_attribute("aria-label")
            print(f"获取到 aria-label: {aria_label}")
            match = re.search(r"\s*(\d+)\s*/\s*(\d+)", aria_label)
            if match:
                total_image_count = int(match.group(2))
                print(f"解析图片总数: {total_image_count} / Parsed total images: {total_image_count}")
            else:
                total_image_count = 0
        except Exception as e:
            print(f"无法获取图片数量: {str(e)}")
            total_image_count = 0

        if total_image_count > 0:
            print(f"  • 初步检测到 {total_image_count} 张图片 / Preliminary detected {total_image_count} images")
            all_downloaded = True
            for idx in range(total_image_count):
                if not is_image_downloaded(save_dir, project_id, idx):
                    all_downloaded = False
                    print(f"  • 图片 {idx} 缺失，需要下载 / Image {idx} missing, will download")
                    break
            if all_downloaded:
                print(f"  ✓ 所有 {total_image_count} 张图片已下载，跳过 / All {total_image_count} images downloaded, skipping")
                return
            else:
                print("  • 图片不完整，继续下载 / Images incomplete, continuing download")

        image_status = {"total": total_image_count, "downloaded": 0, "skipped": 0, "failed": 0, "retried": 0, "details": []}

        for idx in range(total_image_count):
            try:
                img_element = self.driver.find_element(By.XPATH, "//*[@id='mSwiperDiv']//img")
                img_src = img_element.get_attribute('src')
                if not img_src or img_src.strip() == '':
                    print(f"  ✗ 第 {idx+1} 张图片URL为空 / Empty image URL for image {idx+1}")
                    continue
                print(f"  • 第 {idx+1} 张图片的源URL: {img_src} / Source URL for image {idx+1}")

                file_ext = ".jpg"
                for ext in ['.png', '.jpeg', '.gif', '.webp']:
                    if img_src.lower().endswith(ext):
                        file_ext = ext
                        break

                img_save_path = os.path.join(PICTURE_DIR, save_dir, f"id{project_id}_{idx}{file_ext}")

                print(f"  • 正在下载第 {idx+1} 张图片 ({file_ext}) / Downloading image {idx+1}")
                headers = {
                    'User-Agent': random_ua()["User-Agent"],
                    'Referer': project_detail_url,
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive'
                }
                response = requests.get(img_src, headers=headers, stream=True, timeout=REQUEST_TIMEOUT, verify=False)
                if response.status_code == 200:
                    with open(img_save_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                else:
                    print(f"  ✗ 第 {idx+1} 张图片下载失败，HTTP状态码: {response.status_code}")
                    continue

                if os.path.exists(img_save_path) and os.path.getsize(img_save_path) > 10000:
                    mark_image_downloaded(save_dir, project_id, idx)
                    print(f"  ✓ 成功保存第 {idx+1} 张图片 / Image {idx+1} saved successfully")
                else:
                    print(f"  ✗ 第 {idx+1} 张图片保存失败或文件太小 / Image {idx+1} save failed or file too small")
            except Exception as e:
                print(f"  ✗ 处理第 {idx+1} 张图片出错: {str(e)}")
            if idx < total_image_count - 1:
                try:
                    self.driver.execute_script("document.querySelector('#mSwiperDiv').swiper.slideNext()")
                    time.sleep(1)
                except Exception as slide_e:
                    print(f"切换到下一张图片失败: {slide_e}")

        print("\n下载总结 / Download summary:")
        print(f"• 总图片数: {image_status['total']}")
        print(f"• 成功下载: {image_status['downloaded']}")
        print(f"• 已存在跳过: {image_status['skipped']}")
        print(f"• 重试次数: {image_status['retried']}")
        print(f"• 下载失败: {image_status['failed']}")

        if image_status['failed'] > 0:
            print("\n失败详情 / Failure details:")
            for img in image_status["details"]:
                if img["status"] == "failed":
                    print(f"• {img['path']} - 原因: {img['reason']}")

        save_download_status(force=True)

    def crawl_and_download(self):
        """
        爬取并下载所有分类的图片
        Crawl and download images for all categories
        """
        try:
            global _download_status_cache
            if _download_status_cache is None:
                _download_status_cache = load_download_status()

            for category in self.save_dirs:
                print(f"\n开始处理分类 / Starting category: {category}")

                # 构建分类页面URL
                if category == "salesoffice":
                    category_url = "https://www.sldgroup.com/tc/salesoffice.aspx"
                else:
                    url_path = URL_PATH_MAPPING.get(category, category)
                    category_url = f"https://www.sldgroup.com/tc/{url_path}.aspx"

                print(f"访问分类页面 / Visiting category page: {category_url}")
                try:
                    self.driver.get(category_url)
                    time.sleep(3)
                    self.wait.until(EC.presence_of_element_located((By.ID, "mWorkDiv")))
                    project_links = self.driver.find_elements(By.XPATH, '//*[@id="mWorkDiv"]/li/a')
                    max_id = 0
                    print("开始寻找项目ID / Starting to find project IDs")
                    for link in project_links:
                        href = link.get_attribute('href')
                        print(f"找到链接 / Found link: {href}")
                        m = re.search(r"id=(\d+)", href)
                        if m:
                            id_value = int(m.group(1))
                            if id_value > max_id:
                                max_id = id_value
                    if max_id == 0:
                        max_id = DEFAULT_MAX_IDS.get(category, 5)
                    print(f"分类 {category} 的最大ID为 / Maximum ID for {category} is: {max_id}")
                except Exception as e:
                    print(f"访问分类 {category} 时出错: {str(e)} / Error visiting category {category}: {str(e)}")
                    max_id = DEFAULT_MAX_IDS.get(category, 5)

                # 遍历所有项目
                for project_id in range(1, max_id + 1):
                    try:
                        print(f"处理项目 / Processing project: {project_id}/{max_id}")
                        if category == "salesoffice":
                            detail_url = f"https://www.sldgroup.com/tc/saleoffice-detail.aspx?id={project_id}"
                        else:
                            detail_url = f"https://www.sldgroup.com/tc/{URL_PATH_MAPPING.get(category, category)}-detail.aspx?id={project_id}"
                        print(f"使用URL: {detail_url} / Using URL: {detail_url}")
                        self._download_images(category, detail_url, project_id)
                        wait_time = random.uniform(MIN_WAIT_TIME, MAX_WAIT_TIME)
                        print(f"等待 {wait_time:.1f} 秒后继续... / Waiting {wait_time:.1f}s before continuing...")
                        time.sleep(wait_time)
                    except Exception as project_e:
                        print(f"处理项目 {project_id} 时出错: {str(project_e)} / Error processing project")
                        save_download_status(force=True)
                        continue

                # 分类之间添加额外延迟
                pause_time = random.uniform(10, 20)
                print(f"\n在处理下一个分类前暂停 {pause_time:.1f} 秒... / Pausing for {pause_time:.1f}s before next category...")
                time.sleep(pause_time)

            print("\n所有分类爬取完成 / All categories crawled")
            save_download_status(force=True)
        except Exception as e:
            print(f"爬取过程中出错 / Error during crawl: {str(e)}")
            try:
                import traceback
                print("详细错误信息: / Detailed error information:")
                traceback.print_exc()
            except:
                pass
            save_download_status(force=True)
        finally:
            self.cleanup()

    def cleanup(self):
        """
        清理资源，关闭浏览器
        Clean up resources and close the browser
        """
        cleanup_browser(self.driver)

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
        
        # 导入traceback模块，用于详细错误报告
        import traceback
        
        # 增加更强健的错误处理
        max_init_retries = 3
        init_retry_count = 0
        spider = None
        
        while init_retry_count < max_init_retries:
            try:
                # 直接初始化爬虫，让Selenium自动寻找ChromeDriver / Initialize spider, let Selenium find ChromeDriver automatically
                spider = SLDSpider(chromedriver_path=CHROMEDRIVER_PATH)
                
                # 检查爬虫是否成功初始化 / Check if spider is successfully initialized
                if not spider.driver:
                    print("\n自动检测失败，正在尝试更多方法... / Automatic detection failed, trying more methods...")
                    # 尝试使用get_chromedriver_path找到ChromeDriver / Try to find ChromeDriver using get_chromedriver_path
                    detected_path = get_chromedriver_path()
                    if detected_path:
                        print(f"尝试使用检测到的ChromeDriver: {detected_path} / Trying detected ChromeDriver: {detected_path}")
                        spider = SLDSpider(chromedriver_path=detected_path)
                
                # 检查是否成功初始化，成功则跳出循环
                if spider and spider.driver:
                    print("✓ 爬虫初始化成功 / Spider initialized successfully")
                    break
                else:
                    raise Exception("爬虫初始化失败 / Spider initialization failed")
                    
            except Exception as init_e:
                init_retry_count += 1
                print(f"爬虫初始化失败 (尝试 {init_retry_count}/{max_init_retries}): {str(init_e)} / Spider initialization failed")
                
                # 输出详细的错误信息
                print("详细错误信息: / Detailed error information:")
                traceback.print_exc()
                
                if init_retry_count < max_init_retries:
                    wait_time = random.uniform(MIN_WAIT_TIME, MAX_WAIT_TIME)
                    print(f"等待 {wait_time} 秒后重试... / Waiting {wait_time}s before retrying...")
                    time.sleep(wait_time)
                else:
                    print("达到最大重试次数，退出... / Maximum retries reached, exiting...")
                    raise
        
        # 最终检查 / Final check
        if not spider or not spider.driver:
            raise Exception("无法初始化浏览器，请确保已安装最新的Chrome并将ChromeDriver放在正确位置 / Cannot initialize browser, please make sure Chrome is installed and ChromeDriver is in the correct location")
            
        # 爬取并下载图片 / Crawl and download images
        spider.crawl_and_download()
        
        print("\n爬取完成 / Crawling completed")
        print(f"图片保存在 / Images saved in: {os.path.abspath(PICTURE_DIR)}")
    
    except KeyboardInterrupt:
        print("\n用户中断爬取过程 / User interrupted the crawling process")
        # 尝试保存当前状态
        try:
            save_download_status(force=True)
            print("已保存当前下载状态 / Current download status saved")
        except:
            pass
    except Exception as e:
        print(f"\n爬取过程中出错 / Error during crawling: {str(e)}")
        
        # 输出详细的错误信息
        try:
            import traceback
            print("详细错误信息: / Detailed error information:")
            traceback.print_exc()
        except:
            pass
            
        print("\n可能的解决方法 / Possible solutions:")
        print("1. 确保已安装Chrome浏览器 / Make sure Chrome browser is installed")
        print("2. 下载与Chrome版本匹配的ChromeDriver并放在程序目录 / Download ChromeDriver matching Chrome version and place it in program directory:")
        print("   下载地址 / Download from: https://registry.npmmirror.com/binary.html?path=chromedriver/")
        print("3. 使用命令行选项指定ChromeDriver路径 / Use command line option to specify ChromeDriver path:")
        print("   python sldgroup-spider.py --driver /path/to/chromedriver")
        print("4. 如果您已经有ChromeDriver但自动检测失败，请使用命令行选项手动指定路径 / If you already have ChromeDriver but auto-detection fails, manually specify the path")
    finally:
        # 确保保存下载状态
        try:
            save_download_status(force=True)
        except:
            pass
        
        # 清理浏览器资源
        if 'spider' in locals() and spider:
            try:
                spider.cleanup()
            except:
                pass

if __name__ == "__main__":
    main() 
