"""
随机用户代理生成器

提供随机用户代理字符串，帮助避免爬虫被网站封禁
"""

import random

# 当前UA索引
current_ua_index = 0

# 常用用户代理列表
ua_list = [
    # Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:91.0) Gecko/20100101 Firefox/91.0",
    
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36 Edg/92.0.902.67",
    
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
    
    # Mobile
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
]

def get_browser_headers(user_agent):
    """
    根据User-Agent生成更真实的浏览器请求头
    
    Args:
        user_agent (str): 用户代理字符串
        
    Returns:
        dict: 浏览器请求头
    """
    # 基础请求头
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "sec-ch-ua": "\"Not.A/Brand\";v=\"8\", \"Chromium\";v=\"114\", \"Google Chrome\";v=\"114\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "DNT": "1"
    }
    
    # 添加浏览器特定的请求头
    if "Firefox" in user_agent:
        headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "sec-ch-ua": None,
            "sec-ch-ua-mobile": None,
            "sec-ch-ua-platform": None
        })
    elif "Safari" in user_agent and "Chrome" not in user_agent:
        headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "sec-ch-ua": None,
            "sec-ch-ua-mobile": None,
            "sec-ch-ua-platform": None
        })
    elif "Edg" in user_agent:
        headers.update({
            "sec-ch-ua": "\"Chromium\";v=\"114\", \"Microsoft Edge\";v=\"114\", \"Not-A.Brand\";v=\"99\""
        })
        
    # 移除None值
    headers = {k: v for k, v in headers.items() if v is not None}
    
    return headers

def test_all_user_agents():
    """
    测试所有用户代理是否可用
    
    Returns:
        list: 可用的用户代理列表
    """
    import requests
    working_agents = []
    test_url = "https://www.pexels.com/"
    
    print("开始测试所有用户代理...")
    for ua in ua_list:
        try:
            headers = get_browser_headers(ua)
            
            # 请求链接
            session = requests.Session()
            response = session.get(test_url, headers=headers, timeout=10, allow_redirects=True)
            
            if response.status_code == 200:
                working_agents.append(ua)
                print(f"✓ 代理可用: {ua[:50]}...")
            else:
                print(f"✗ 代理不可用: {ua[:50]}... (状态码: {response.status_code})")
        except Exception as e:
            print(f"✗ 代理测试失败: {ua[:50]}... (错误: {e})")
    
    print(f"测试完成: {len(working_agents)}/{len(ua_list)} 个代理可用")
    return working_agents if working_agents else ua_list  # 如果没有可用代理，返回原列表

def random_ua():
    """
    获取下一个用户代理的完整请求头（循环方式）
    
    Returns:
        dict: 包含User-Agent和其他浏览器特征的请求头字典
    """
    global current_ua_index
    
    # 获取当前UA
    ua = ua_list[current_ua_index]
    
    # 更新索引，循环使用
    current_ua_index = (current_ua_index + 1) % len(ua_list)
    
    # 获取完整请求头
    return get_browser_headers(ua)

# 当作为独立脚本运行时，测试所有用户代理
if __name__ == "__main__":
    test_all_user_agents()
