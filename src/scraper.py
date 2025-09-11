"""
企研通城投债募集说明书爬虫核心模块
负责登录、搜索、数据解析等功能
"""

import os
import time
import json
import requests
import uuid
import urllib.parse
import hashlib
import random
import string
import traceback
from pathlib import Path
# 使用标准 selenium，通过浏览器开发者工具拦截网络请求
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger
from typing import Dict, List, Optional, Tuple

from .config import *
from .account_pool import AccountPool, AccountInfo


def format_error_info(error: Exception, context: str = "") -> str:
    """
    格式化错误信息，包含文件名、行号和详细堆栈
    
    Args:
        error: 异常对象
        context: 上下文信息
        
    Returns:
        str: 格式化的错误信息
    """
    # 获取异常类型和消息
    error_type = type(error).__name__
    error_msg = str(error)
    
    # 获取堆栈信息
    tb_lines = traceback.format_exc().strip().split('\n')
    
    # 提取文件名和行号
    file_info = "未知文件"
    line_info = "未知行"
    
    for line in tb_lines:
        if 'File "' in line and 'line ' in line:
            # 提取文件路径和行号
            parts = line.split('", line ')
            if len(parts) == 2:
                file_path = parts[0].split('File "')[1]
                line_num = parts[1].split(',')[0]
                # 只保留文件名，不包含完整路径
                file_name = os.path.basename(file_path)
                file_info = f"{file_name}:{line_num}"
                break
    
    # 构建详细错误信息
    error_info = f"❌ 错误类型: {error_type}"
    error_info += f"\n📍 位置: {file_info}"
    error_info += f"\n💬 消息: {error_msg}"
    
    if context:
        error_info += f"\n🔍 上下文: {context}"
    
    # 添加简化的堆栈信息（只显示最后几行）
    if len(tb_lines) > 2:
        error_info += f"\n📚 堆栈: {tb_lines[-2].strip()}"
    
    return error_info


class QYYJTScraper:
    """企研通爬虫主类"""
    
    def __init__(self, use_account_pool: bool = True, accounts_config: List[Dict] = None):
        self.driver = None
        self.session = requests.Session()
        self.is_logged_in = False
        self.cookies = {}
        self.pcuss_token = ""  # JWT token (s_tk)
        self.r_tk = ""         # JWT token (r_tk)
        self.s_tk = ""         # JWT token (s_tk)
        self.user_id = ""      # 用户标识
        self.phone = ""        # 手机号
        self.chromedriver_path = None
        
        # 账号池相关
        self.use_account_pool = use_account_pool
        self.account_pool = None
        self.current_account = None
        
        if use_account_pool:
            self.account_pool = AccountPool(accounts_config)
            logger.info("已启用账号池模式")
        
    def _get_chromedriver_path(self) -> str:
        """获取ChromeDriver路径，优先使用本地缓存的版本"""
        # 创建本地ChromeDriver缓存目录
        cache_dir = Path.home() / ".qyyjt_scraper" / "chromedriver"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取Chrome版本
        try:
            import subprocess
            result = subprocess.run(['reg', 'query', 'HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon', '/v', 'version'], 
                                 capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                chrome_version = result.stdout.split()[-1]
            else:
                # 如果注册表查询失败，尝试其他方法
                chrome_version = "latest"
        except:
            chrome_version = "latest"
        
        # 生成版本特定的路径
        version_hash = hashlib.md5(chrome_version.encode()).hexdigest()[:8]
        chromedriver_path = cache_dir / f"chromedriver_{version_hash}.exe"
        
        # 如果本地文件不存在，下载并缓存
        if not chromedriver_path.exists():
            logger.info(f"本地ChromeDriver不存在，开始下载版本 {chrome_version}...")
            try:
                # 使用webdriver-manager下载
                manager = ChromeDriverManager()
                downloaded_path = manager.install()
                
                # 复制到本地缓存
                import shutil
                shutil.copy2(downloaded_path, chromedriver_path)
                logger.info(f"ChromeDriver已下载并缓存到: {chromedriver_path}")
            except Exception as e:
                logger.warning(f"下载ChromeDriver失败: {e}，将使用webdriver-manager默认路径")
                return None
        else:
            logger.info(f"使用本地缓存的ChromeDriver: {chromedriver_path}")
        
        return str(chromedriver_path)
    
    def cleanup_old_chromedrivers(self, keep_days: int = 30):
        """清理过期的ChromeDriver缓存文件"""
        try:
            cache_dir = Path.home() / ".qyyjt_scraper" / "chromedriver"
            if not cache_dir.exists():
                return
            
            import time
            current_time = time.time()
            cutoff_time = current_time - (keep_days * 24 * 60 * 60)
            
            cleaned_count = 0
            for file_path in cache_dir.glob("chromedriver_*.exe"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    cleaned_count += 1
                    logger.info(f"已清理过期ChromeDriver: {file_path.name}")
            
            if cleaned_count > 0:
                logger.info(f"共清理了 {cleaned_count} 个过期的ChromeDriver文件")
        except Exception as e:
            logger.warning(f"清理ChromeDriver缓存失败: {e}")
    
    def setup_driver(self) -> webdriver.Chrome:
        """设置并返回Chrome浏览器驱动（支持网络请求拦截）"""
        try:
            logger.info("开始初始化Chrome浏览器驱动...")
            
            # 清理过期的ChromeDriver缓存
            self.cleanup_old_chromedrivers()
            # Chrome选项配置
            chrome_options = Options()
            
            # 禁用无头模式（手机验证码登录需要可视化界面）
            if HEADLESS_MODE:
                logger.warning("手机验证码登录需要可视化界面，已自动禁用无头模式")
                chrome_options.add_argument("--headless=new")
            
            # 基础配置
            chrome_options.add_argument(f"--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            
            # 基础性能优化（保持输入响应性）
            chrome_options.add_argument("--disable-background-timer-throttling")  # 禁用后台定时器限制
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")  # 禁用被遮挡窗口的后台处理
            chrome_options.add_argument("--disable-renderer-backgrounding")  # 禁用渲染器后台处理
            chrome_options.add_argument("--disable-features=TranslateUI")  # 禁用翻译UI
            chrome_options.add_argument("--disable-sync")  # 禁用同步
            chrome_options.add_argument("--disable-default-apps")  # 禁用默认应用
            chrome_options.add_argument("--disable-extensions")  # 禁用扩展
            chrome_options.add_argument("--disable-plugins")  # 禁用插件
            
            # 输入响应性优化
            chrome_options.add_argument("--disable-background-networking")  # 禁用后台网络
            chrome_options.add_argument("--disable-component-update")  # 禁用组件更新
            chrome_options.add_argument("--disable-domain-reliability")  # 禁用域可靠性
            
            # 内存优化（不影响输入）
            chrome_options.add_argument("--memory-pressure-off")  # 关闭内存压力检测
            chrome_options.add_argument("--max_old_space_size=4096")  # 增加内存限制
            
            # 实验性选项
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 输入响应性优化选项
            prefs = {
                "profile.default_content_setting_values": {
                    "notifications": 2,  # 禁用通知
                    "media_stream": 2,   # 禁用媒体流
                },
                "profile.managed_default_content_settings": {
                    "images": 1  # 允许图片加载
                },
                "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 1
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # 禁用日志
            chrome_options.add_argument("--log-level=3")  # 只显示致命错误
            chrome_options.add_argument("--silent")  # 静默模式
            
            # 设置User-Agent
            chrome_options.add_argument(f"--user-agent={DEFAULT_HEADERS['User-Agent']}")
            
            # 使用本地Chrome驱动
            driver = None
            try:
                logger.info("使用本地Chrome驱动...")
                chromedriver_path = str(Path(__file__).parent.parent / "chromedriver-mac-x64" / "chromedriver")
                service = Service(chromedriver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e:
                logger.error(f"本地Chrome驱动失败: {e}")
                # 如果本地驱动失败，尝试使用系统PATH
                try:
                    logger.info("尝试使用系统PATH中的chromedriver...")
                    driver = webdriver.Chrome(options=chrome_options)
                except Exception as e2:
                    logger.error(f"webdriver-manager下载ChromeDriver失败: {e2}")
                    raise Exception(f"ChromeDriver初始化失败: 系统PATH({e}), webdriver-manager({e2})")
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # 设置超时时间（增加页面加载超时）
            driver.set_page_load_timeout(60)  # 增加到60秒
            driver.implicitly_wait(ELEMENT_TIMEOUT)
            
            # 设置脚本超时
            driver.set_script_timeout(30)
            
            logger.info("Chrome浏览器驱动初始化成功")
            return driver
            
        except Exception as e:
            error_info = format_error_info(e, "浏览器驱动初始化")
            logger.error(error_info)
            raise
    
    def setup_account_pool(self, accounts_config: List[Dict] = None) -> bool:
        """设置账号池"""
        try:
            if not self.use_account_pool:
                logger.warning("账号池模式未启用")
                return False
            
            if accounts_config:
                self.account_pool = AccountPool(accounts_config)
            elif not self.account_pool:
                self.account_pool = AccountPool()
            
            logger.info("账号池设置完成")
            return True
            
        except Exception as e:
            error_info = format_error_info(e, "设置账号池")
            logger.error(error_info)
            return False
    
    def login_with_account_pool(self) -> bool:
        """使用账号池登录"""
        if not self.use_account_pool or not self.account_pool:
            logger.error("账号池未初始化")
            return False
        
        # 尝试登录所有账号
        success_count = self.account_pool.login_all_accounts()
        
        if success_count == 0:
            logger.error("所有账号登录失败")
            return False
        
        logger.info(f"账号池登录完成，成功 {success_count} 个账号")
        return True
    
    def get_available_account(self) -> Optional[AccountInfo]:
        """获取可用账号"""
        if not self.use_account_pool or not self.account_pool:
            return None
        
        return self.account_pool.get_available_account()
    
    def switch_to_account(self, account: AccountInfo) -> bool:
        """切换到指定账号"""
        try:
            if not account or not account.is_logged_in:
                logger.error("账号未登录或不可用")
                return False
            
            # 更新当前账号信息
            self.current_account = account
            self.pcuss_token = account.pcuss_token
            self.r_tk = account.r_tk
            self.s_tk = account.s_tk
            self.user_id = account.user_id
            self.phone = account.phone
            self.cookies = account.cookies.copy()
            self.is_logged_in = True
            
            # 更新session的cookies
            self.session.cookies.clear()
            for name, value in account.cookies.items():
                self.session.cookies.set(name, value)
            
            logger.info(f"已切换到账号 {account.phone}")
            return True
            
        except Exception as e:
            logger.error(f"切换账号失败: {e}")
            return False
    
    def mark_account_error(self, error_msg: str = ""):
        """标记当前账号出错"""
        if self.current_account and self.account_pool:
            self.account_pool.mark_account_error(self.current_account, error_msg)
            # 尝试切换到其他账号
            self.switch_to_available_account()
    
    def switch_to_available_account(self) -> bool:
        """切换到其他可用账号"""
        if not self.use_account_pool or not self.account_pool:
            return False
        
        available_account = self.account_pool.get_available_account()
        if available_account and available_account != self.current_account:
            return self.switch_to_account(available_account)
        
        logger.warning("没有其他可用账号")
        return False
    
    def get_pool_status(self) -> Dict:
        """获取账号池状态"""
        if not self.use_account_pool or not self.account_pool:
            return {"error": "账号池未启用"}
        
        return self.account_pool.get_pool_status()

    def auto_login_with_password(self, phone: str = None, password: str = None) -> bool:
        """
        自动登录流程（使用账号密码）
        返回: 登录是否成功
        """
        try:
            if not self.driver:
                self.driver = self.setup_driver()
            
            # 使用传入的参数或配置文件中的默认值
            phone = phone or PHONE_NUMBER
            password = password or PASSWORD
            
            if not phone or not password:
                logger.error("手机号或密码未设置")
                return False
            
            logger.info(f"开始自动登录: {phone}")
            self.driver.get(LOGIN_URL)
            
            # 等待页面加载
            time.sleep(3)
            
            # 1. 点击账号密码登录标签
            logger.info("点击账号密码登录标签")
            password_tab = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, LOGIN_SELECTORS["password_login_tab"]))
            )
            password_tab.click()
            time.sleep(1)
            
            # 2. 输入手机号
            logger.info("输入手机号")
            phone_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, LOGIN_SELECTORS["phone_input"]))
            )
            phone_input.clear()
            phone_input.send_keys(phone)
            time.sleep(1)
            
            # 3. 输入密码
            logger.info("输入密码")
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, LOGIN_SELECTORS["password_input"]))
            )
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(1)
            
            # 4. 点击登录按钮
            logger.info("点击登录按钮")
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, LOGIN_SELECTORS["login_button"]))
            )
            login_button.click()
            
            # 5. 等待登录完成并检查状态
            logger.info("等待登录完成...")
            time.sleep(5)  # 等待登录处理
            
            # 检查登录状态
            return self._check_login_status()
            
        except Exception as e:
            error_info = format_error_info(e, "自动登录")
            logger.error(error_info)
            return False
    
    def _check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            # 检查当前URL是否还在登录页面
            current_url = self.driver.current_url
            if "login" in current_url.lower():
                logger.warning("仍在登录页面，登录可能失败")
                return False
            
            # 提取认证信息
            self._extract_cookies()
            self._extract_auth_tokens()
            
            # 检查是否有有效的认证信息
            if self.pcuss_token and self.user_id:
                self.is_logged_in = True
                self.phone = self.phone or "已登录"
                logger.info("✅ 登录状态检查成功")
                return True
            else:
                logger.warning("❌ 认证信息不完整，登录失败")
                return False
                
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False

    def login_with_verification_code(self) -> bool:
        """
        手动登录流程（完全手动操作）
        返回: 登录是否成功
        """
        try:
            if not self.driver:
                self.driver = self.setup_driver()
            
            logger.info(f"开始访问登录页面: {LOGIN_URL}")
            self.driver.get(LOGIN_URL)
            
            # 等待页面加载
            time.sleep(3)
            
            # 显示手动操作提示
            print("=" * 80)
            print("🔐 手动登录流程")
            print("=" * 80)
            print("📋 请按以下步骤手动操作：")
            print("   1. 手动输入手机号码")
            print("   2. 手动点击获取验证码按钮")
            print("   3. 如果出现图形验证码，请手动输入并点击确定")
            print("   4. 等待手机验证码发送")
            print("   5. 手动输入手机验证码")
            print("   6. 手动点击登录按钮")
            print("=" * 80)
            print("⏰ 请在浏览器中完成所有操作，程序将等待您完成...")
            print("💡 完成后程序会自动检测登录状态")
            print("=" * 80)
            
            # 等待用户完成所有手动操作
            logger.info("等待用户完成手动登录操作...")
            
            # 循环检查登录状态，最多等待5分钟
            max_wait_time = 300  # 5分钟
            check_interval = 5   # 每5秒检查一次
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                try:
                    current_url = self.driver.current_url
                    
                    # 检查是否已经登录成功（URL不再包含login或跳转到其他页面）
                    if "login" not in current_url.lower() or "dashboard" in current_url.lower() or "home" in current_url.lower():
                        logger.info("检测到登录成功！")
                        self.is_logged_in = True
                        
                        # 提取Cookies并设置到session中
                        self._extract_cookies()
                        
                        # 提取认证token
                        self._extract_auth_tokens()
                        
                        print("✅ 登录成功！")
                        return True
                    
                    # 检查是否有错误信息
                    try:
                        # 这里可以添加检查错误信息的逻辑
                        pass
                    except:
                        pass
                    
                    # 等待下次检查
                    time.sleep(check_interval)
                    
                except Exception as e:
                    logger.warning(f"检查登录状态时出错: {e}")
                    time.sleep(check_interval)
            
            # 超时处理
            logger.error("登录超时，请检查是否完成所有步骤")
            print("❌ 登录超时！")
            print("💡 可能的原因：")
            print("   - 未完成所有登录步骤")
            print("   - 手机号或验证码错误")
            print("   - 网络连接问题")
            return False
                
        except Exception as e:
            logger.error(f"登录过程中发生错误: {e}")
            return False
    
    def _extract_cookies(self):
        """从浏览器中提取Cookies并设置到requests session中"""
        try:
            # 获取所有cookies
            selenium_cookies = self.driver.get_cookies()
            
            # 转换为requests可用的格式
            for cookie in selenium_cookies:
                self.session.cookies.set(
                    name=cookie['name'],
                    value=cookie['value'],
                    domain=cookie.get('domain'),
                    path=cookie.get('path')
                )
            
            # 设置请求头
            self.session.headers.update(DEFAULT_HEADERS)
            
            # 提取JWT token和用户标识
            self._extract_auth_tokens()
            
            logger.info(f"成功提取 {len(selenium_cookies)} 个Cookies")
            
        except Exception as e:
            logger.error(f"提取Cookies失败: {e}")
    
    def _extract_auth_tokens(self):
        """从浏览器中提取认证token"""
        try:
            # 从localStorage中提取r_tk token (JWT token)
            r_tk = self.driver.execute_script("return localStorage.getItem('r_tk');")
            if r_tk:
                # 移除可能存在的双引号
                r_tk = r_tk.strip('"')
                self.r_tk = r_tk
                logger.info(f"成功提取r_tk token: {r_tk[:20]}...")
            else:
                logger.warning("localStorage中没有找到r_tk token")
            
            # 从localStorage中提取s_tk token (JWT token) - 这个用作pcuss_token
            s_tk = self.driver.execute_script("return localStorage.getItem('s_tk');")
            if s_tk:
                # 移除可能存在的双引号
                s_tk = s_tk.strip('"')
                self.s_tk = s_tk
                self.pcuss_token = s_tk  # s_tk用作pcuss_token
                logger.info(f"成功提取s_tk token: {s_tk[:20]}...")
            else:
                logger.warning("localStorage中没有找到s_tk token")
            
            # 从localStorage中提取用户信息
            u_info = self.driver.execute_script("return localStorage.getItem('u_info');")
            if u_info:
                try:
                    import json
                    user_data = json.loads(u_info)
                    if 'encryptUser' in user_data:
                        self.user_id = user_data['encryptUser']
                        logger.info(f"成功提取用户标识: {self.user_id[:20]}...")
                    if 'phone' in user_data:
                        self.phone = user_data['phone']
                        logger.info(f"成功提取手机号: {self.phone}")
                except:
                    logger.warning("解析用户信息失败")
            else:
                logger.warning("localStorage中没有找到用户信息")
            
            # 如果localStorage中没有，尝试从cookies中提取
            if not self.pcuss_token:
                for cookie in self.driver.get_cookies():
                    if 'r_tk' in cookie['name'].lower() or 'token' in cookie['name'].lower():
                        self.pcuss_token = cookie['value']
                        logger.info("从cookies中提取token")
                        break
            
        except Exception as e:
            logger.warning(f"提取认证token时出错: {e}")
    
    def search_bond_info(self, bond_short_name: str, use_selenium: bool = True) -> Optional[Dict]:
        """
        搜索债券信息，获取债券代码
        参数: 
            bond_short_name - 债券简称
            use_selenium - 是否使用Selenium进行搜索（True: 使用浏览器搜索, False: 使用API搜索）
        返回: 搜索结果数据或错误信息，包含债券代码
        """
        if not self.is_logged_in:
            logger.error("尚未登录，请先执行登录操作")
            return {
                'success': False,
                'data': None,
                'error': "尚未登录",
                'need_switch_account': False,
                'error_type': 'not_logged_in'
            }
        
        if use_selenium:
            result = self._search_with_selenium(bond_short_name)
            if result:
                return {
                    'success': True,
                    'data': result,
                    'error': None,
                    'need_switch_account': False,
                    'error_type': None
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'error': "Selenium搜索失败",
                    'need_switch_account': False,
                    'error_type': 'selenium_error'
                }
        else:
            return self._search_with_api(bond_short_name)
    
    def _search_with_selenium(self, bond_short_name: str) -> Optional[Dict]:
        """
        使用Selenium在浏览器中搜索
        1. 在搜索框中输入关键字
        2. 点击搜索按钮
        3. 拦截并解析API响应
        4. 返回结构化搜索结果数据
        """
        try:
            logger.info(f"使用Selenium搜索债券: {bond_short_name}")
            
            # 确保在首页
            if "qyyjt.cn" not in self.driver.current_url:
                logger.info("访问首页...")
                self.driver.get("https://www.qyyjt.cn/")
                time.sleep(3)
            
            # 等待搜索框出现
            try:
                wait = WebDriverWait(self.driver, 10)
                search_input = wait.until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR, 
                        "#home_page_wrapper > div.FYThQdt > div.styles__HomeContainer-hbxzqU.cZvXgU.X4IS3Qp > div.lezgoOa > div:nth-child(1) > div.searchBar__InputWrapper-ecaRqy.hHduRT > div.searchBar__InputBox-hpbGgw.hsNiov > div > div > span > span > span.ant-input-affix-wrapper > input"
                    ))
                )
                logger.info("找到搜索框")
            except Exception as e:
                logger.error(f"未找到搜索框: {e}")
                return None
            
            # 清空搜索框并输入关键字
            search_input.clear()
            search_input.send_keys(bond_short_name)
            logger.info(f"已输入搜索关键字: {bond_short_name}")
            
            # 点击搜索按钮
            try:
                search_button = wait.until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR, 
                        "#home_page_wrapper > div.FYThQdt > div.styles__HomeContainer-hbxzqU.cZvXgU.X4IS3Qp > div.lezgoOa > div:nth-child(1) > div.searchBar__InputWrapper-ecaRqy.hHduRT > div.searchBar__InputBox-hpbGgw.hsNiov > div > div > span > span > span.ant-input-group-addon > button"
                    ))
                )
                search_button.click()
                logger.info("已点击搜索按钮")
            except Exception as e:
                logger.error(f"点击搜索按钮失败: {e}")
                return None
            
            # 等待搜索结果加载
            time.sleep(3)
            
            # 拦截并解析API响应
            api_response = self._intercept_search_api_response()
            if api_response:
                logger.info(f"成功拦截API响应，找到 {len(api_response.get('data', {}).get('list', []))} 条结果")
                return api_response
            else:
                logger.warning("未能拦截到API响应，尝试从页面解析结果")
                return self._parse_search_results_from_page()
                
        except Exception as e:
            error_info = format_error_info(e, f"Selenium搜索债券: {bond_short_name}")
            logger.error(error_info)
            return None
    
    def _intercept_search_api_response(self) -> Optional[Dict]:
        """
        拦截搜索API响应
        """
        try:
            # 获取浏览器日志
            logs = self.driver.get_log('performance')
            
            for log in logs:
                message = json.loads(log['message'])
                
                # 查找网络请求
                if message['message']['method'] == 'Network.responseReceived':
                    response = message['message']['params']['response']
                    url = response.get('url', '')
                    
                    # 检查是否是搜索API请求
                    if 'search' in url.lower() and 'api' in url.lower():
                        logger.info(f"找到搜索API请求: {url}")
                        
                        # 获取响应内容
                        request_id = message['message']['params']['requestId']
                        try:
                            response_body = self.driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                            response_text = response_body.get('body', '')
                            
                            if response_text:
                                # 解析JSON响应
                                api_data = json.loads(response_text)
                                if api_data.get('returncode') == 0:
                                    logger.info("成功解析API响应")
                                    return api_data
                        except Exception as e:
                            logger.warning(f"解析API响应失败: {e}")
                            continue
            
            logger.warning("未找到搜索API响应")
            return None
            
        except Exception as e:
            error_info = format_error_info(e, "拦截API响应")
            logger.error(error_info)
            return None
    
    def extract_bond_codes_from_search(self, search_result: Dict) -> List[Dict]:
        """
        从搜索结果中提取债券代码列表
        
        Args:
            search_result: 搜索结果数据
            
        Returns:
            List[Dict]: 包含债券代码和名称的列表
        """
        bond_codes = []
        
        try:
            if not search_result or 'data' not in search_result:
                logger.warning("搜索结果为空或格式不正确")
                return bond_codes
            
            data = search_result['data']
            
            # 如果是API响应格式
            if isinstance(data, dict) and 'list' in data:
                bond_list = data['list']
                logger.info(f"从搜索结果中提取债券代码，共 {len(bond_list)} 个结果")
                
                for item in bond_list:
                    try:
                        # 提取债券信息
                        bond_code = item.get('code', '')
                        bond_name = item.get('name', '')
                        bond_short_name = item.get('shortName', '')
                        
                        if bond_code:
                            bond_info = {
                                'code': bond_code,
                                'name': bond_name,
                                'short_name': bond_short_name,
                                'url': item.get('url', ''),
                                'type': item.get('type', 'co')
                            }
                            bond_codes.append(bond_info)
                            logger.info(f"提取债券代码: {bond_short_name} -> {bond_code}")
                        else:
                            logger.warning(f"债券 {bond_name} 没有代码")
                            
                    except Exception as e:
                        logger.warning(f"解析单个债券信息失败: {e}")
                        continue
            
            # 如果是页面解析格式
            elif isinstance(data, list):
                logger.info(f"从页面解析结果中提取债券代码，共 {len(data)} 个结果")
                
                for item in data:
                    try:
                        # 从URL中提取债券代码
                        url = item.get('url', '')
                        if url and 'code=' in url:
                            # 从URL中提取code参数
                            import urllib.parse
                            parsed_url = urllib.parse.urlparse(url)
                            query_params = urllib.parse.parse_qs(parsed_url.query)
                            bond_code = query_params.get('code', [None])[0]
                            
                            if bond_code:
                                bond_info = {
                                    'code': bond_code,
                                    'name': item.get('name', ''),
                                    'short_name': item.get('name', ''),
                                    'url': url,
                                    'type': 'co'  # 默认类型
                                }
                                bond_codes.append(bond_info)
                                logger.info(f"从URL提取债券代码: {item.get('name', '')} -> {bond_code}")
                        
                    except Exception as e:
                        logger.warning(f"从URL解析债券代码失败: {e}")
                        continue
            
            logger.info(f"成功提取 {len(bond_codes)} 个债券代码")
            return bond_codes
            
        except Exception as e:
            logger.error(f"提取债券代码失败: {e}")
            return bond_codes

    def _parse_search_results_from_page(self) -> Optional[Dict]:
        """
        从页面解析搜索结果（备用方案）
        """
        try:
            # 等待搜索结果容器出现
            wait = WebDriverWait(self.driver, 10)
            results_container = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#basicSearchScrollWrapper > div > div > div.flex-left"))
            )
            logger.info("找到搜索结果容器")
            
            # 首先获取搜索结果数量
            actual_count = None
            try:
                count_element = self.driver.find_element(By.CSS_SELECTOR, "#basicSearchScrollWrapper > div > div > div.flex-left > div > div > div.countInfo__Wrapper-kLvdrO.bWGXdY")
                count_text = count_element.text.strip()
                logger.info(f"搜索结果数量信息: {count_text}")
                
                # 从文本中提取数字
                import re
                match = re.search(r'共\s*(\d+)\s*条', count_text)
                if match:
                    actual_count = int(match.group(1))
                    logger.info(f"解析到实际结果数量: {actual_count}")
            except Exception as e:
                logger.warning(f"无法获取搜索结果数量: {e}")
            
            # 查找搜索结果项
            result_items = self.driver.find_elements(By.CSS_SELECTOR, "#basicSearchScrollWrapper > div > div > div.flex-left > div > div > div.infinite-scroll-component__outerdiv > div > div")
            
            # 根据实际数量限制解析，如果没有获取到数量则限制为10个
            max_items = actual_count if actual_count is not None else 10
            logger.info(f"将解析前 {max_items} 个结果项")
            
            results = []
            for i, item in enumerate(result_items[:max_items]):
                try:
                    # 尝试获取标题和链接
                    title_element = item.find_element(By.CSS_SELECTOR, "div > div > div > div.title-wapper > div > div.line-1 > div:nth-child(1) > div.b7qnw8k.copyBoxWrap > a")
                    
                    result_data = {
                        "index": i + 1,
                        "name": title_element.text.strip(),
                        "url": title_element.get_attribute("href"),
                        "element": title_element
                    }
                    results.append(result_data)
                    logger.info(f"解析结果 {i+1}: {result_data['name']}")
                    
                except Exception as e:
                    logger.warning(f"解析第 {i+1} 个结果时出错: {e}")
                    continue
            
            logger.info(f"从页面解析到 {len(results)} 条结果")
            return {"data": results, "method": "selenium_page_parse"}
            
        except Exception as e:
            error_info = format_error_info(e, "从页面解析搜索结果")
            logger.error(error_info)
            return None
    
    def _search_with_api(self, bond_short_name: str) -> Optional[Dict]:
        """
        使用API搜索，带智能重试机制和账号池支持
        返回: Dict 包含搜索结果或错误信息，格式为:
        {
            'success': bool,
            'data': dict,  # 成功时的数据
            'error': str,  # 错误信息
            'need_switch_account': bool,  # 是否需要切换账号
            'error_type': str  # 错误类型
        }
        """
        for attempt in range(MAX_RETRIES):
            try:
                # 如果使用账号池，确保有可用账号
                if self.use_account_pool:
                    if not self.current_account or not self.current_account.is_logged_in:
                        available_account = self.get_available_account()
                        if not available_account:
                            logger.error("没有可用的登录账号")
                            return {
                                'success': False,
                                'data': None,
                                'error': "没有可用的登录账号",
                                'need_switch_account': False,
                                'error_type': 'no_available_account'
                            }
                        self.switch_to_account(available_account)
                
                logger.info(f"使用API搜索债券: {bond_short_name} (尝试 {attempt + 1}/{MAX_RETRIES})")
                if self.current_account:
                    logger.info(f"当前使用账号: {self.current_account.phone}")
                
                # 添加请求延迟，避免频率过高
                if attempt > 0:  # 重试时才延迟
                    delay = REQUEST_DELAY + random.uniform(RANDOM_DELAY_MIN, RANDOM_DELAY_MAX)
                    logger.info(f"等待 {delay:.1f} 秒后发送请求...")
                    time.sleep(delay)
                elif hasattr(self, '_last_api_request_time'):
                    # 即使是第一次请求，也要确保与上次请求有足够间隔
                    time_since_last = time.time() - self._last_api_request_time
                    if time_since_last < REQUEST_DELAY:
                        delay = REQUEST_DELAY - time_since_last + random.uniform(0, 1)
                        logger.info(f"距离上次请求仅 {time_since_last:.1f} 秒，等待 {delay:.1f} 秒...")
                        time.sleep(delay)
                
                # 记录本次请求时间
                self._last_api_request_time = time.time()
                
                # 构造搜索参数
                search_params = SEARCH_API_PARAMS.copy()
                search_params["text"] = bond_short_name
                
                # 构造请求头
                headers = DEFAULT_HEADERS.copy()
                
                # 添加认证信息
                if self.pcuss_token:
                    headers["pcuss"] = self.pcuss_token
                    logger.info(f"使用pcuss token: {self.pcuss_token[:20]}...")
                else:
                    logger.warning("pcuss token为空")
                
                if self.user_id:
                    headers["user"] = self.user_id
                    logger.info(f"使用user标识: {self.user_id}")
                else:
                    logger.warning("user标识为空")
                
                # 生成请求ID和URL
                request_id = str(uuid.uuid4()).replace('-', '').upper()
                request_url = urllib.parse.quote(f"/s?tab=securities&k={bond_short_name}")
                
                headers.update({
                    "x-request-id": request_id,
                    "x-request-url": request_url,
                    "referer": f"{BASE_URL}/s?tab=securities&k={urllib.parse.quote(bond_short_name)}"
                })
                
                # 发送搜索请求
                response = self.session.get(
                    SEARCH_API_URL,
                    params=search_params,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("returncode") == 0:
                        data = result.get("data", {})
                        list_data = data.get("list", [])
                        logger.info(f"API搜索成功，找到 {len(list_data)} 条结果")
                        return {
                            'success': True,
                            'data': {"data": list_data},
                            'error': None,
                            'need_switch_account': False,
                            'error_type': None
                        }
                    else:
                        error_info = result.get('info', '未知错误')
                        logger.error(f"API返回错误: {error_info}")
                        
                        # 检查是否是限流错误
                        if "请求过多" in error_info or "请稍后再试" in error_info:
                            if attempt < MAX_RETRIES - 1:
                                # 如果使用账号池，尝试切换账号
                                if self.use_account_pool and self.switch_to_available_account():
                                    logger.info("已切换到其他账号，继续重试")
                                    continue
                                
                                wait_time = RATE_LIMIT_DELAY * (attempt + 1)  # 递增等待时间
                                logger.warning(f"⚠️ 遇到限流，等待 {wait_time} 秒后重试...")
                                time.sleep(wait_time)
                                continue
                            else:
                                logger.error(f"❌ 达到最大重试次数，跳过债券: {bond_short_name}")
                                return {
                                    'success': False,
                                    'data': None,
                                    'error': f"限流错误: {error_info}",
                                    'need_switch_account': True,
                                    'error_type': 'rate_limit'
                                }
                        # 检查是否是token过期错误
                        elif "token过时" in error_info or "token过期" in error_info or "token无效" in error_info:
                            logger.warning(f"⚠️ 检测到token过期错误: {error_info}")
                            if self.use_account_pool and attempt < MAX_RETRIES - 1:
                                if self.switch_to_available_account():
                                    logger.info("已切换到其他账号，继续重试")
                                    continue
                            else:
                                logger.error(f"❌ token过期且无法切换账号，跳过债券: {bond_short_name}")
                                return {
                                    'success': False,
                                    'data': None,
                                    'error': f"Token过期: {error_info}",
                                    'need_switch_account': True,
                                    'error_type': 'token_expired'
                                }
                        else:
                            # 其他错误，如果使用账号池则尝试切换账号
                            if self.use_account_pool and attempt < MAX_RETRIES - 1:
                                if self.switch_to_available_account():
                                    logger.info("已切换到其他账号，继续重试")
                                    continue
                            return {
                                'success': False,
                                'data': None,
                                'error': f"API错误: {error_info}",
                                'need_switch_account': True,
                                'error_type': 'api_error'
                            }
                else:
                    logger.error(f"API搜索请求失败，状态码: {response.status_code}")
                    logger.error(f"响应内容: {response.text}")
                    
                    # 如果是5xx错误，尝试重试
                    if 500 <= response.status_code < 600 and attempt < MAX_RETRIES - 1:
                        wait_time = RETRY_DELAY * (attempt + 1)
                        logger.warning(f"⚠️ 服务器错误，等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return {
                            'success': False,
                            'data': None,
                            'error': f"HTTP错误: {response.status_code}",
                            'need_switch_account': False,
                            'error_type': 'http_error'
                        }
                        
            except Exception as e:
                error_info = format_error_info(e, f"API搜索债券: {bond_short_name} (尝试 {attempt + 1}/{MAX_RETRIES})")
                logger.error(error_info)
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (attempt + 1)
                    logger.warning(f"⚠️ 发生异常，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    return {
                        'success': False,
                        'data': None,
                        'error': f"异常错误: {str(e)}",
                        'need_switch_account': False,
                        'error_type': 'exception'
                    }
        
        return {
            'success': False,
            'data': None,
            'error': "达到最大重试次数",
            'need_switch_account': False,
            'error_type': 'max_retries'
        }
    
    def click_first_search_result(self, search_result: Dict) -> bool:
        """
        点击第一个搜索结果跳转到详情页面
        参数: search_result - 搜索结果数据
        返回: 是否成功跳转
        """
        try:
            if not search_result or 'data' not in search_result:
                logger.error("搜索结果为空")
                return False
            
            data = search_result['data']
            
            # 如果是API响应格式
            if isinstance(data, dict) and 'list' in data:
                bond_list = data['list']
                if not bond_list:
                    logger.warning("搜索结果为空")
                    return False
                
                first_bond = bond_list[0]
                bond_url = first_bond.get('url', '')
                bond_name = first_bond.get('name', '')
                
                if bond_url:
                    logger.info(f"准备跳转到第一个结果: {bond_name}")
                    logger.info(f"详情页URL: {bond_url}")
                    
                    # 直接访问详情页URL
                    self.driver.get(bond_url)
                    time.sleep(3)
                    
                    logger.info("成功跳转到详情页面")
                    return True
                else:
                    logger.error("第一个结果没有URL")
                    return False
            
            # 如果是页面解析格式
            elif isinstance(data, list) and len(data) > 0:
                first_result = data[0]
                if 'element' in first_result:
                    # 点击第一个结果的链接
                    first_result['element'].click()
                    time.sleep(3)
                    logger.info("成功点击第一个搜索结果")
                    return True
                elif 'url' in first_result:
                    # 直接访问URL
                    self.driver.get(first_result['url'])
                    time.sleep(3)
                    logger.info("成功跳转到详情页面")
                    return True
                else:
                    logger.error("第一个结果没有可点击的元素或URL")
                    return False
            
            else:
                logger.error("搜索结果格式不正确")
                return False
                
        except Exception as e:
            error_info = format_error_info(e, "点击第一个搜索结果")
            logger.error(error_info)
            return False
    
    def parse_prospectus_links(self, data_list: List[Dict]) -> List[Dict]:
        """
        从API数据列表中解析文档信息（使用统一解析器）
        参数: data_list - API返回的数据列表
        返回: 解析出的文档信息列表
        """
        return self._parse_api_items_to_documents(data_list)
    
    def _classify_document_type(self, title: str) -> str:
        """根据标题分类文档类型"""
        for keyword in SEARCH_KEYWORDS:
            if keyword in title:
                return keyword
        return "其他"
    
    def _parse_api_items_to_documents(self, data_list: List[Dict], bond_code: str = '', bond_short_name: str = '') -> List[Dict]:
        """
        统一的API数据解析函数，将API返回的数据列表转换为文档格式
        
        Args:
            data_list: API返回的数据列表
            bond_code: 债券代码（可选，如果API数据中没有）
            bond_short_name: 债券简称（可选，如果API数据中没有）
            
        Returns:
            List[Dict]: 转换后的文档列表
        """
        documents = []
        
        if not data_list:
            return documents
            
        logger.info(f"开始解析 {len(data_list)} 条API数据")
        
        # 调试：检查数据类型
        if data_list:
            logger.info(f"第一个数据项类型: {type(data_list[0])}")
            logger.info(f"第一个数据项内容: {data_list[0]}")
        
        for item in data_list:
            try:
                # 检查数据类型
                if not isinstance(item, dict):
                    logger.warning(f"跳过非字典类型的数据项: {type(item)} - {item}")
                    continue
                
                # 从file数组获取文件信息
                files = item.get('file', [])
                if not files:
                    logger.warning(f"公告没有文件: {item.get('title', 'Unknown')}")
                    continue
                
                # 从related数组获取债券信息（如果API数据中有）
                related_info = item.get('related', [{}])[0]
                api_bond_short_name = related_info.get('shortCompanyName', '')
                api_bond_code = related_info.get('code', '')
                
                # 使用API数据中的债券信息，如果没有则使用传入的参数
                final_bond_short_name = api_bond_short_name or bond_short_name
                final_bond_code = api_bond_code or bond_code
                
                # 处理每个文件
                for file_info in files:
                    file_url = file_info.get('fileUrl', '')
                    file_name = file_info.get('fileName', '')
                    file_size = file_info.get('fileSize', '')
                    
                    if not file_url:
                        logger.warning(f"文件无下载链接: {file_name}")
                        continue
                    
                    # 优先使用label字段作为文档类型
                    labels = item.get('label', [])
                    document_type = labels[0].get('lastLevelName', '未知') if labels else '未知'
                    
                    # 如果label里没有，再用标题关键词猜测
                    if document_type == '未知':
                        document_type = self._classify_document_type(item.get('title', ''))
                    
                    # 处理发布日期
                    date_str = item.get('date', '')
                    if date_str and len(date_str) >= 8:
                        try:
                            # 从 YYYYMMDDHHMMSS 格式转换为 YYYY-MM-DD
                            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                        except:
                            formatted_date = date_str[:8] if len(date_str) >= 8 else date_str
                    else:
                        formatted_date = ''
                    
                    # 构造文档信息
                    document = {
                        'bond_code': final_bond_code,
                        'bond_short_name': final_bond_short_name,
                        'bond_full_name': related_info.get('companyName', final_bond_short_name),
                        'document_title': item.get('title', ''),
                        'document_type': document_type,
                        'download_url': file_url,
                        'file_name': file_name,
                        'file_size': file_size,
                        'publication_date': formatted_date,
                        'source': item.get('source', ''),
                        'info_id': item.get('infoId', ''),
                        'pc_content_link': item.get('pcContentLink', ''),
                        'risk_level': item.get('risk', ''),
                        'importance': str(item.get('importance', '')),
                        'negative': str(item.get('negative', '')),
                        'collection': item.get('collection', 0),
                        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    documents.append(document)
                    logger.debug(f"解析文档: {file_name} - {document_type}")
            
            except Exception as e:
                logger.warning(f"解析单个文档失败: {e}")
                continue
        
        logger.info(f"解析完成，共找到 {len(documents)} 个文档")
        return documents

    def _convert_api_data_to_documents(self, api_data: Dict, bond_code: str, bond_short_name: str) -> List[Dict]:
        """
        将API返回的数据转换为文档格式（兼容旧接口）
        
        Args:
            api_data: API返回的数据
            bond_code: 债券代码
            bond_short_name: 债券简称
            
        Returns:
            List[Dict]: 转换后的文档列表
        """
        if not api_data or 'data' not in api_data:
            return []
        
        return self._parse_api_items_to_documents(api_data['data'], bond_code, bond_short_name)

    def get_bond_notices_by_code(self, bond_code: str, bond_type: str = "co", skip: int = 0, size: int = 50) -> Optional[Dict]:
        """
        【已废弃】此函数直接调用API，逻辑不正确，已被 get_bond_documents_complete 替代。
        
        Args:
            bond_code: 债券代码
            bond_type: 债券类型，默认为"co"
            skip: 跳过的记录数
            size: 每页记录数
        
        Returns:
            Dict: 公告列表数据，如果失败返回None
        """
        logger.warning("函数 'get_bond_notices_by_code' 已被废弃，请使用 'get_bond_documents_complete'。")
        return None

    def get_bond_notices(self, bond_code: str, bond_type: str = "co", skip: int = 0, size: int = 15) -> Optional[Dict]:
        """
        【已废弃】此函数直接调用API，逻辑不正确，已被 get_bond_documents_complete 替代。
        
        Args:
            bond_code: 债券代码
            bond_type: 债券类型，默认为"co"
            skip: 跳过的记录数
            size: 每页记录数
        
        Returns:
            Dict: 公告列表数据，如果失败返回None
        """
        logger.warning("函数 'get_bond_notices' 已被废弃，请使用 'get_bond_documents_complete'。")
        return None
            
    def _generate_request_id(self) -> str:
        """生成请求ID"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=15))
    
    def get_bond_documents_complete(self, bond_short_name: str) -> List[Dict]:
        """
        【已重构】完整的债券文档获取流程（UI驱动）:
        1. 搜索债券简称（通过UI）
        2. 点击第一个搜索结果，跳转到详情页
        3. 在详情页，点击左侧菜单触发公告API请求
        4. 拦截该API请求的响应数据
        5. 解析数据，提取文档信息
        
        Args:
            bond_short_name: 债券简称
            
        Returns:
            List[Dict]: 所有文档信息列表
        """
        logger.info(f"【新流程】开始获取债券文档: {bond_short_name}")
        try:
            # 第一步：搜索债券 (必须使用Selenium来驱动UI)
            logger.info("第一步：通过UI搜索债券简称...")
            search_result = self.search_bond_info(bond_short_name, use_selenium=True)
            
            if not search_result or not search_result.get('success', False):
                error_msg = search_result.get('error', '搜索失败') if search_result else '搜索失败'
                logger.error(f"UI搜索失败: {error_msg}")
                return []
            
            # 第二步：点击第一个搜索结果
            logger.info("第二步：点击第一个搜索结果...")
            if not self._click_first_search_result():
                logger.error("点击第一个搜索结果失败，流程终止。")
                return []
            
            # 第三步 & 第四步：在详情页导航并捕获数据
            logger.info("第三步和第四步：导航至公告并拦截API数据...")
            notice_data = self._navigate_and_capture_notice_data()
            if not notice_data:
                logger.error("未能导航或捕获公告数据，流程终止。")
                return []
            
            # 第五步：解析捕获到的数据
            logger.info("第五步：解析已拦截的公告数据...")
            # 复用你已有的解析函数
            documents = self.parse_notice_data(notice_data, bond_short_name)
            
            logger.info(f"完整流程成功，共获取 {len(documents)} 个文档")
            return documents
            
        except Exception as e:
            error_info = format_error_info(e, f"完整流程获取债券文档失败: {bond_short_name}")
            logger.error(error_info)
            return []

    def _click_first_search_result(self) -> bool:
        """
        【新】辅助函数：在搜索结果页，点击第一个结果并等待详情页加载。
        """
        try:
            # 使用更健壮的选择器定位第一个结果的容器
            # 你提供的选择器太具体，这个更通用
            first_result_selector = "div.infinite-scroll-component__outerdiv div.list-item-container"
            wait = WebDriverWait(self.driver, 20)

            logger.info("等待第一个搜索结果出现...")
            first_result_element = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, first_result_selector))
            )

            logger.info("成功定位到第一个搜索结果，准备点击。")
            first_result_element.click()

            # 等待详情页的关键元素（如左侧菜单）加载出来
            logger.info("等待详情页加载...")
            detail_page_menu_selector = "div.sideMenu__AutoSideMenuStyle-ffyIWQ"
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, detail_page_menu_selector))
            )
            logger.info("详情页加载成功。")
            return True
                
        except Exception as e:
            error_info = format_error_info(e, "点击第一个搜索结果时发生错误")
            logger.error(error_info)
            return False

    def _navigate_and_capture_notice_data(self) -> Optional[Dict]:
        """
        【新】辅助函数：在详情页上操作并拦截网络请求。
        1. 点击左侧 "相关公告" 主菜单。
        2. 点击展开后的 "债券公告" 子菜单。
        3. 通过浏览器开发者工具捕获API请求的响应。
        """
        try:
            wait = WebDriverWait(self.driver, 20)
            
            # --- 1. 点击主菜单 "相关公告" ---
            # 使用XPath通过文本内容查找，这比动态ID/class更稳定
            main_menu_xpath = "//li[contains(@class, 'ant-menu-submenu')]//span[contains(text(), '相关公告')]"
            logger.info("查找并点击主菜单 '相关公告'...")
            main_menu_item = wait.until(
                EC.element_to_be_clickable((By.XPATH, main_menu_xpath))
            )
            main_menu_item.click()
            time.sleep(1) # 等待动画效果

            # --- 2. 点击子菜单 "债券公告" ---
            # 同样使用XPath通过文本查找
            sub_menu_xpath = "//li[contains(@class, 'ant-menu-item')]//div[contains(text(), '债券公告')]"
            logger.info("查找并点击子菜单 '债券公告'...")
            sub_menu_item = wait.until(
                EC.element_to_be_clickable((By.XPATH, sub_menu_xpath))
            )
            sub_menu_item.click()

            # --- 3. 等待页面加载并获取数据 ---
            logger.info("等待公告数据加载...")
            time.sleep(3)  # 等待API请求完成
            
            # 通过JavaScript获取网络请求日志
            try:
                # 获取浏览器日志
                logs = self.driver.get_log('performance')
                
                for log in logs:
                    message = json.loads(log['message'])
                    
                    # 查找网络请求
                    if message['message']['method'] == 'Network.responseReceived':
                        response = message['message']['params']['response']
                        url = response.get('url', '')
                        
                        # 检查是否是目标API请求
                        if 'webNotice/getF9NoticeList' in url:
                            logger.info(f"找到目标API请求: {url}")
                            
                            # 获取响应内容
                            request_id = message['message']['params']['requestId']
                            try:
                                response_body = self.driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                                response_text = response_body.get('body', '')
                                
                                if response_text:
                                    # 解析JSON响应
                                    api_data = json.loads(response_text)
                                    if api_data.get('returncode') == 0:
                                        logger.info("成功解析API响应")
                                        return api_data
                            except Exception as e:
                                logger.warning(f"解析API响应失败: {e}")
                                continue
                
                logger.warning("未找到目标API响应，尝试从页面解析数据")
                return self._parse_notice_data_from_page()
                
            except Exception as e:
                logger.warning(f"通过日志拦截失败: {e}，尝试从页面解析数据")
                return self._parse_notice_data_from_page()

        except Exception as e:
            error_info = format_error_info(e, "在详情页导航并捕获数据时发生错误")
            logger.error(error_info)
            return None

    def _parse_notice_data_from_page(self) -> Optional[Dict]:
        """
        从页面解析公告数据（备用方案）
        """
        try:
            # 等待公告列表加载
            wait = WebDriverWait(self.driver, 10)
            
            # 查找公告列表容器
            notice_list_selector = "div.ant-table-tbody"
            notice_list = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, notice_list_selector))
            )
            
            # 解析公告数据
            notices = []
            notice_items = notice_list.find_elements(By.CSS_SELECTOR, "tr")
            
            for item in notice_items:
                try:
                    # 提取公告信息
                    cells = item.find_elements(By.CSS_SELECTOR, "td")
                    if len(cells) >= 3:
                        title_cell = cells[1]  # 标题列
                        date_cell = cells[2]   # 日期列
                        
                        title = title_cell.text.strip()
                        date = date_cell.text.strip()
                        
                        if title:
                            notices.append({
                                'title': title,
                                'date': date,
                                'type': '债券公告'
                            })
                except Exception as e:
                    logger.warning(f"解析单个公告失败: {e}")
                    continue
            
            if notices:
                logger.info(f"从页面解析到 {len(notices)} 条公告")
                return {'data': notices, 'returncode': 0}
            else:
                logger.warning("未找到公告数据")
                return None
                
        except Exception as e:
            logger.error(f"从页面解析公告数据失败: {e}")
            return None

    def parse_notice_data(self, notice_data: Dict, bond_short_name: str) -> List[Dict]:
        """
        解析公告数据，提取文档信息（使用统一解析器）
        
        Args:
            notice_data: 公告列表数据
            bond_short_name: 债券简称
        
        Returns:
            List[Dict]: 解析后的文档信息列表
        """
        data_list = notice_data.get('data', [])
        return self._parse_api_items_to_documents(data_list, bond_short_name=bond_short_name)
    
    def close(self):
        """关闭浏览器驱动和账号池"""
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")
        
        if self.account_pool:
            self.account_pool.close()
            logger.info("账号池已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 使用示例
if __name__ == "__main__":
    scraper = QYYJTScraper()
    
    try:
        # 登录
        if scraper.login_with_verification_code():
            print("登录成功！")
            
            # 测试API搜索
            result = scraper.search_bond_info("25苏通02", use_selenium=False)
            if result and result.get('success'):
                # 从包装器中取出真正的数据
                api_data = result.get('data', {})
                items_list = api_data.get('data', [])
                
                # 把数据列表传给解析函数
                documents = scraper.parse_prospectus_links(items_list)
                print(f"找到 {len(documents)} 个文档")
                for doc in documents:
                    print(f"- {doc['bond_short_name']}: {doc['document_title']} ({doc['document_type']})")
            else:
                print("搜索失败！")
        else:
            print("登录失败！")
    
    finally:
        scraper.close()
