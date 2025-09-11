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
from pathlib import Path
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


class QYYJTScraper:
    """企研通爬虫主类"""
    
    def __init__(self):
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
        """设置并返回Chrome浏览器驱动"""
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
            
            # 优先使用本地缓存的ChromeDriver
            chromedriver_path = self._get_chromedriver_path()
            if chromedriver_path and os.path.exists(chromedriver_path):
                logger.info(f"使用本地缓存的ChromeDriver: {chromedriver_path}")
                service = Service(chromedriver_path)
                self.chromedriver_path = chromedriver_path
            else:
                logger.info("本地ChromeDriver不可用，使用webdriver-manager下载...")
                service = Service(ChromeDriverManager().install())
            
            # 创建驱动实例
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # 设置超时时间（增加页面加载超时）
            driver.set_page_load_timeout(60)  # 增加到60秒
            driver.implicitly_wait(ELEMENT_TIMEOUT)
            
            # 设置脚本超时
            driver.set_script_timeout(30)
            
            logger.info("Chrome浏览器驱动初始化成功")
            return driver
            
        except Exception as e:
            logger.error(f"浏览器驱动初始化失败: {e}")
            raise
    
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
        搜索债券信息
        参数: 
            bond_short_name - 债券简称
            use_selenium - 是否使用Selenium进行搜索（True: 使用浏览器搜索, False: 使用API搜索）
        返回: 搜索结果数据
        """
        if not self.is_logged_in:
            logger.error("尚未登录，请先执行登录操作")
            return None
        
        if use_selenium:
            return self._search_with_selenium(bond_short_name)
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
            logger.error(f"Selenium搜索失败: {e}")
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
            logger.error(f"拦截API响应失败: {e}")
            return None
    
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
            
            # 查找搜索结果项
            result_items = self.driver.find_elements(By.CSS_SELECTOR, "#basicSearchScrollWrapper > div > div > div.flex-left > div > div > div.infinite-scroll-component__outerdiv > div > div")
            
            results = []
            for i, item in enumerate(result_items[:10]):  # 限制前10个结果
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
            logger.error(f"从页面解析搜索结果失败: {e}")
            return None
    
    def _search_with_api(self, bond_short_name: str) -> Optional[Dict]:
        """
        使用API搜索
        """
        try:
            logger.info(f"使用API搜索债券: {bond_short_name}")
            
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
                    return {"data": list_data}
                else:
                    logger.error(f"API返回错误: {result.get('info', '未知错误')}")
                    return None
            else:
                logger.error(f"API搜索请求失败，状态码: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"API搜索过程中发生错误: {e}")
            return None
    
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
            logger.error(f"点击第一个搜索结果失败: {e}")
            return False
    
    def parse_prospectus_links(self, search_result: Dict) -> List[Dict]:
        """
        从搜索结果中解析募集说明书链接
        参数: search_result - 搜索结果JSON数据
        返回: 解析出的文档信息列表
        """
        try:
            documents = []
            data_list = search_result.get('data', [])
            
            logger.info(f"开始解析 {len(data_list)} 条搜索结果")
            
            for item in data_list:
                # 从API响应中提取信息
                name = item.get('name', '')
                code = item.get('code', '')
                date = item.get('date', '')
                details = item.get('details', [])
                
                # 查找发行人信息
                issuer = ""
                for detail in details:
                    if detail.get('key') == 'holder':
                        issuer = detail.get('value', '')
                        break
                
                # 构造文档信息
                document = {
                    'bond_short_name': name,
                    'bond_code': code,
                    'issuer': issuer,
                    'publication_date': date,
                    'document_type': '债券信息',
                    'download_url': item.get('url', ''),
                    'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                documents.append(document)
                logger.info(f"解析债券信息: {name}")
            
            logger.info(f"解析完成，共找到 {len(documents)} 个债券信息")
            return documents
            
        except Exception as e:
            logger.error(f"解析文档链接时发生错误: {e}")
            return []
    
    def _classify_document_type(self, title: str) -> str:
        """根据标题分类文档类型"""
        for keyword in SEARCH_KEYWORDS:
            if keyword in title:
                return keyword
        return "其他"
    
    def close(self):
        """关闭浏览器驱动"""
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")
    
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
            if result:
                documents = scraper.parse_prospectus_links(result)
                print(f"找到 {len(documents)} 个债券信息")
                for doc in documents:
                    print(f"- {doc['bond_short_name']}: {doc['issuer']}")
            else:
                print("搜索失败！")
        else:
            print("登录失败！")
    
    finally:
        scraper.close()
