# E:\BaiduSyncdisk\数据库\1-城投公司\QYYJTScraper\src\config.py

# -- 文件路径 --

ACCOUNTS_FILE_PATH = "data/accounts.json"
BONDS_LIST_PATH = "data/bonds_list.xlsx"
BONDS_LIST_COLUMN_NAME = "债券简称" # [新增] 定义要读取的列名

# -- 爬虫行为设置 --
REQUESTS_PER_ACCOUNT = 50  # 每个账号连续爬取50次后切换
DELAY_BETWEEN_PAGES = (1, 3) # 爬取公告时，每页之间的随机延迟秒数范围
DELAY_BETWEEN_BONDS = (3, 7) # 完成一个债券后，开始下一个之前的随机延迟秒数范围

# --- [新增] 开发与测试 ---
TEST_MODE = False  # 设置为 True 开启测试模式，False 则运行完整任务
TEST_MODE_BOND_COUNT = 5 # 在测试模式下，只爬取列表中的前 N 个债券


# -- 网站URL --
LOGIN_URL = "https://www.qyyjt.cn/user/login"
SEARCH_API_URL = "https://www.qyyjt.cn/finchinaAPP/v1/finchina-search/v1/multipleSearch"
NOTICE_API_URL = "https://www.qyyjt.cn/finchinaAPP/v1/finchina-search/v1/webNotice/getF9NoticeList"

# -- 登录XPaths --
LOGIN_XPATHS = {
    "password_login_tab": "//div[text()='账户密码登录']",
    "phone_input": "//input[@placeholder='请输入手机号']",
    "password_input": "//input[@type='password']",
    "login_button": "//button[contains(., '登 录')]",
    "home_search_input": "//input[@placeholder='企业/证券/功能/集团户/区域/关键字']",
    "search_result_securities_tab": "//div[@role='tab' and contains(text(), '证券')]"
}

# -- 数据库 --
DATABASE_NAME = "qyyjt_data.db"
