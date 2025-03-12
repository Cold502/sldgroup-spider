你好, 我是来自大陆北方的网友.

sldgroup.com写了个动态web不让你爬, 你爬不爬? 赶紧说, 你死都得爬. 那要是被SLD逮住了怎么办, 那只能很尴尬地笑. 然后捂着头.

# SLD集团网站图片爬虫 / SLD Group Website Image Crawler

## 项目介绍 / Project Introduction

这是一个专门用于爬取 [SLD集团网站](https://www.sldgroup.com/) 图片的爬虫程序。它使用Selenium抓取动态加载的内容，支持自动下载ChromeDriver和断点续传功能。

This is a crawler specifically designed to download images from the [SLD Group website](https://www.sldgroup.com/). It uses Selenium to capture dynamically loaded content and supports automatic ChromeDriver download and resume download functionality.

本项目包含两个主要脚本：
The project contains two main scripts:

1. `sldgroup-spider.py`: 主爬虫程序，用于下载SLD集团网站的项目图片
   Main crawler program for downloading project images from the SLD Group website

2. `convert_to_png.py`: 辅助工具，用于将下载的图片统一转换为PNG格式
   Utility tool for converting downloaded images to PNG format

## 安装依赖 / Installation of Dependencies

在使用前，请确保已安装以下依赖：
Before using, please ensure you have installed the following dependencies:

```bash
# 安装爬虫所需依赖 / Install dependencies for the crawler
pip install selenium requests pillow
```

另外，您需要安装Chrome浏览器。爬虫程序会尝试自动下载并使用匹配的ChromeDriver。
Additionally, you need to install Chrome browser. The crawler will attempt to automatically download and use the matching ChromeDriver.

## 使用指南 / Usage Guide

### 爬虫程序 / Crawler Program

运行爬虫程序，下载SLD集团网站的项目图片：
Run the crawler program to download project images from the SLD Group website:

```bash
python sldgroup-spider.py
```

可选参数：
Optional parameters:

- `--driver PATH`: 指定ChromeDriver路径
  Specify ChromeDriver path
  
- `--skip-download`: 跳过下载ChromeDriver，仅使用本地已有的ChromeDriver
  Skip downloading ChromeDriver and only use the local ChromeDriver
  
- `--help` 或 `-h`: 显示帮助信息
  Show help information

### 图片格式转换工具 / Image Format Conversion Tool

将下载好的图片转换为PNG格式：
Convert downloaded images to PNG format:

```bash
python convert_to_png.py
```

默认处理`picture`目录下的所有图片。您也可以指定其他目录：
By default, it processes all images in the `picture` directory. You can also specify another directory:

```bash
python convert_to_png.py 路径/到/您的/图片目录
python convert_to_png.py path/to/your/image/directory
```

## 项目结构 / Project Structure

```
.
├── sldgroup-spider.py    # 主爬虫程序 / Main crawler program
├── convert_to_png.py     # 图片格式转换工具 / Image format conversion tool
├── picture/              # 下载的图片保存目录 / Directory for saved images
│   ├── residential/      # 住宅项目图片 / Residential project images
│   ├── clubhouse/        # 会所项目图片 / Clubhouse project images
│   ├── salesoffice/      # 销售中心项目图片 / Sales office project images
│   ├── hospitality/      # 酒店项目图片 / Hospitality project images
│   ├── commercial/       # 商业项目图片 / Commercial project images
│   └── download_status.json  # 下载状态记录文件 / Download status record file
└── chromedriver/         # ChromeDriver下载目录 / ChromeDriver download directory
```

## 特点功能 / Key Features

- **自动化爬取** / **Automated Crawling**：使用Selenium模拟浏览器行为，自动处理动态加载内容
  Uses Selenium to simulate browser behavior and automatically handle dynamically loaded content

- **断点续传** / **Resume Downloads**：支持从上次中断的位置继续下载，避免重复工作
  Supports resuming downloads from where it was interrupted, avoiding duplicate work

- **自动查找ChromeDriver** / **Auto-detect ChromeDriver**：自动查找或下载与Chrome浏览器版本匹配的ChromeDriver
  Automatically detects or downloads ChromeDriver matching your Chrome browser version

- **多分类爬取** / **Multi-category Crawling**：支持爬取网站的所有项目分类（住宅、会所、销售中心、酒店、商业）
  Supports crawling all project categories on the website (residential, clubhouse, sales office, hospitality, commercial)

- **智能检测** / **Smart Detection**：智能检测已下载图片，避免重复下载
  Intelligently detects already downloaded images to avoid redundant downloads

- **反爬虫策略** / **Anti-scraping Measures**：实现多种反爬虫检测技术，减少被网站屏蔽的可能性
  Implements various anti-detection techniques to reduce the possibility of being blocked by the website

## 注意事项 / Notes

1. 此程序仅供学习和研究使用，请勿用于商业目的
   This program is for learning and research purposes only, please do not use it for commercial purposes

2. 请尊重网站所有者的权利，不要过度频繁地访问网站
   Please respect the rights of website owners and do not access the website too frequently

3. 图片格式转换工具会删除原始图片文件，如需保留，请提前备份
   The image format conversion tool will delete the original image files, please back up in advance if you need to keep them

4. 如果自动下载ChromeDriver失败，您可以手动下载并指定路径
   If the automatic download of ChromeDriver fails, you can manually download it and specify the path

5. 爬虫程序支持断点续传，意外中断后可以继续从上次中断的地方开始下载
   The crawler program supports resuming downloads, allowing you to continue from where you left off after an unexpected interruption

## 故障排除 / Troubleshooting

如果遇到以下问题，可以尝试相应的解决方法：
If you encounter the following issues, you can try the corresponding solutions:

1. **ChromeDriver初始化失败** / **ChromeDriver initialization failed**
   - 确保Chrome浏览器已正确安装 / Ensure Chrome browser is correctly installed
   - 手动下载匹配版本的ChromeDriver / Manually download the matching version of ChromeDriver
   - 使用`--driver`参数指定ChromeDriver路径 / Use the `--driver` parameter to specify ChromeDriver path

2. **图片下载失败** / **Image download failed**
   - 检查网络连接 / Check network connection
   - 适当增加等待时间 / Increase wait time appropriately
   - 可能需要配置代理 / May need to configure a proxy

3. **被网站封禁** / **Blocked by the website**
   - 减少访问频率 / Reduce access frequency
   - 增加随机等待时间 / Increase random wait time
   - 更换IP地址或使用代理 / Change IP address or use a proxy

## 贡献与改进 / Contribution and Improvement

欢迎提出建议和改进，或者提交问题报告。您可以通过以下方式参与项目：

Suggestions for improvement and bug reports are welcome. You can participate in the project by:

1. 提交Bug报告或功能请求 / Submit bug reports or feature requests
2. 改进代码并提交拉取请求 / Improve the code and submit pull requests
3. 分享您的使用经验和建议 / Share your experience and suggestions

