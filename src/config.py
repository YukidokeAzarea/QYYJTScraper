"""
企研通城投债募集说明书爬虫配置文件
包含所有可配置的变量，如网站URL、登录凭据、搜索API、文件路径等
"""

import os
from pathlib import Path

# ==================== 项目路径配置 ====================
# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
# 数据库文件路径
DATABASE_PATH = DATA_DIR / "prospectuses.db"
# 债券列表Excel文件路径
BONDS_LIST_PATH = DATA_DIR / "bonds_list.xlsx"
# 账号池配置文件路径
ACCOUNTS_CONFIG_PATH = DATA_DIR / "accounts_config.json"

# ==================== 网站配置 ====================
# 目标网站基础URL
BASE_URL = "https://www.qyyjt.cn"
# 登录页面URL (需要你根据实际情况填写)
LOGIN_URL = f"{BASE_URL}/user/login"  # 示例，请根据实际登录页面URL修改
# 搜索API URL (基于你提供的curl命令)
SEARCH_API_URL = f"{BASE_URL}/finchinaAPP/v1/finchina-search/v1/multipleSearch"

# ==================== 登录凭据配置 ====================
# 手机号 (用于接收验证码)
PHONE_NUMBER = "15390314229"  # 请替换为你的手机号
# 密码 (用于账号密码登录)
PASSWORD = ""  # 请设置您的密码

# ==================== 登录页面元素配置 ====================
# 登录页面元素选择器 (基于实际页面元素)
LOGIN_SELECTORS = {
    # 账号密码登录相关选择器
    "password_login_tab": "#root > div.style__LoginPage-ixWxWf.bttGZF > div.style__MainWrapper-fawzCD.bEYJI > div.awm50eO > div > div > div:nth-child(2) > div > div.ant-tabs-nav > div.ant-tabs-nav-wrap > div > div:nth-child(1)",  # 账号密码登录标签
    "phone_input": "#username",  # 手机号输入框 (使用ID选择器)
    "password_input": "#password",  # 密码输入框 (使用ID选择器)
    "login_button": "button[type='submit']",  # 登录按钮 (使用类型选择器)
    
    # 验证码登录相关选择器 (保留备用)
    "verification_code_input": "#code",  # 手机验证码输入框选择器
    "send_code_button": "button[class*='send-code']",  # 发送验证码按钮选择器
    "captcha_image": "#rc-tabs-0-panel-1 > div > div.verification__Content-itFzmc.bhrhWw > form > div.aA8EUzk.ZcZcBas > div > div > img",    # 图形验证码图片选择器
    "captcha_input": "#validatecode",    # 图形验证码输入框选择器
    "captcha_confirm_button": "button[class*='confirm']",  # 图形验证码确定按钮选择器
}

# ==================== 搜索页面元素配置 ====================
# 搜索页面元素选择器 (暂时不需要配置，使用API搜索)
# SEARCH_SELECTORS = {
#     # 搜索相关选择器暂时不配置，优先使用API搜索
# }

# ==================== 浏览器配置 ====================
# 浏览器类型 (支持: chrome, firefox, edge)
BROWSER_TYPE = "chrome"
# 是否使用无头模式 (True: 后台运行, False: 显示浏览器窗口)
# 注意：手机验证码登录必须使用可视化模式，不能使用无头模式
HEADLESS_MODE = False
# 浏览器窗口大小
WINDOW_SIZE = (1920, 1080)
# 页面加载超时时间 (秒)
PAGE_LOAD_TIMEOUT = 30
# 元素查找超时时间 (秒)
ELEMENT_TIMEOUT = 10
# 验证码输入等待时间 (秒) - 给用户足够时间输入验证码
VERIFICATION_CODE_WAIT_TIME = 60

# ==================== 请求配置 ====================
# 请求间隔时间 (秒) - 避免请求过于频繁
REQUEST_DELAY = 5
# 随机延迟范围 (秒) - 反爬虫机制
RANDOM_DELAY_MIN = 3.0
RANDOM_DELAY_MAX = 7.0
# 请求超时时间 (秒)
REQUEST_TIMEOUT = 30
# 最大重试次数
MAX_RETRIES = 5
# 重试间隔时间 (秒)
RETRY_DELAY = 10
# API限流时的额外等待时间 (秒)
RATE_LIMIT_DELAY = 30

# ==================== 搜索配置 ====================
# 搜索关键词 (用于筛选文档类型)
SEARCH_KEYWORDS = [
    "募集说明书",
    "发行公告", 
    "评级报告",
    "财务报告"
]
# 主要搜索关键词 (优先级最高)
PRIMARY_KEYWORD = "募集说明书"

# ==================== 数据库配置 ====================
# 数据库表名
TABLE_NAME = "bond_documents"
# 是否在每次运行前清空数据库
CLEAR_DATABASE_ON_START = False

# ==================== 日志配置 ====================
# 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = "INFO"
# 日志文件路径
LOG_FILE = PROJECT_ROOT / "logs" / "scraper.log"
# 是否同时输出到控制台
LOG_TO_CONSOLE = True

# ==================== 生产环境配置 ====================
# 是否启用防休眠模式
PREVENT_SLEEP = True
# 是否启用反爬虫机制
ANTI_CRAWLING = True
# 批量处理时的进度保存间隔
PROGRESS_SAVE_INTERVAL = 1000
# 统计信息显示间隔
STATS_DISPLAY_INTERVAL = 100
# 是否在出错时继续处理下一个债券
CONTINUE_ON_ERROR = True
# 最大并发请求数 (暂时设为1，避免对服务器造成压力)
MAX_CONCURRENT_REQUESTS = 1

# ==================== 其他配置 ====================
# 是否启用进度条显示
SHOW_PROGRESS_BAR = True

# ==================== 请求头配置 ====================
# 默认请求头
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Ch-Ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Priority": "u=1, i",
    "Client": "pc-web;pro",
    "System": "new",
    "System1": "Macintosh; Intel Mac OS X 10_15_7;Chrome;139.0.0.0",
    "Terminal": "pc-web;pro",
    "Ver": "20250903",
}

# ==================== 搜索API配置 ====================
# 搜索API参数配置
SEARCH_API_PARAMS = {
    "pagesize": 30,
    "skip": 0,
    "template": "list",
    "source": "",
    "isRelationSearch": 0
}

# 搜索API特殊请求头（这些会在登录后动态设置）
SEARCH_API_SPECIAL_HEADERS = {
    "pcuss": "",  # 登录后的JWT token，会在登录后动态设置
    "user": "",   # 用户标识，会在登录后动态设置
    "x-request-id": "",  # 请求ID，每次请求都会生成
    "x-request-url": "",  # 请求URL，每次请求都会生成
}

# ==================== 验证配置 ====================
def validate_config():
    """验证配置文件的完整性"""
    errors = []
    
    # 检查必要的路径
    if not DATA_DIR.exists():
        errors.append(f"数据目录不存在: {DATA_DIR}")
    
    if not BONDS_LIST_PATH.exists():
        errors.append(f"债券列表文件不存在: {BONDS_LIST_PATH}")
    
    # 检查登录凭据
    if PHONE_NUMBER == "your_phone_number_here":
        errors.append("请设置正确的手机号")
    
    # 检查URL配置
    if LOGIN_URL == f"{BASE_URL}/login":
        errors.append("请设置正确的登录页面URL")
    
    if SEARCH_API_URL == f"{BASE_URL}/api/search":
        errors.append("请设置正确的搜索API URL")
    
    if errors:
        print("配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print("配置验证通过!")
    return True

# ==================== 环境变量支持 ====================
# 支持从环境变量读取敏感信息
import os
PHONE_NUMBER = os.getenv("QYYJT_PHONE", PHONE_NUMBER)

if __name__ == "__main__":
    # 运行配置验证
    validate_config()
