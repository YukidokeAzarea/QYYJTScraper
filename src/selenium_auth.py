"""
Selenium认证和代码获取模块
专门负责登录、搜索、获取认证信息和债券代码
按照README要求，Selenium的唯一任务是获取code列表和auth_package
"""

import time
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger

from .config import *


class SeleniumAuthManager:
    """Selenium认证管理器 - 专门负责获取认证信息和债券代码"""
    
    def __init__(self, headless: bool = False):
        self.driver = None
        self.headless = headless
        self.is_logged_in = False
        self.auth_package = None
        self.codes_to_process = []
        
    def initialize_driver(self) -> bool:
        """初始化Chrome驱动"""
        try:
            logger.info("正在初始化Chrome驱动...")
            
            # Chrome选项配置
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # 基本配置
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")
            
            # 启用性能日志以拦截网络请求
            chrome_options.add_argument("--enable-logging")
            chrome_options.add_argument("--log-level=0")
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            # 创建驱动 - 使用本地Chrome驱动
            chromedriver_path = str(Path(__file__).parent.parent / "chromedriver-mac-x64" / "chromedriver")
            self.driver = webdriver.Chrome(
                service=Service(chromedriver_path),
                options=chrome_options
            )
            
            # 设置超时
            self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            self.driver.implicitly_wait(ELEMENT_TIMEOUT)
            
            logger.info("✅ Chrome驱动初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ Chrome驱动初始化失败: {e}")
            return False
    
    def login_with_password(self, phone: str, password: str) -> bool:
        """
        使用账号密码登录
        
        Args:
            phone: 手机号
            password: 密码
            
        Returns:
            bool: 登录是否成功
        """
        try:
            logger.info(f"开始登录流程，手机号: {phone}")
            
            # 访问登录页面
            self.driver.get(LOGIN_URL)
            time.sleep(3)
            
            # 等待页面加载
            wait = WebDriverWait(self.driver, ELEMENT_TIMEOUT)
            
            # 切换到账号密码登录标签
            try:
                password_tab = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, LOGIN_SELECTORS["password_login_tab"]))
                )
                password_tab.click()
                time.sleep(1)
                logger.info("✅ 已切换到账号密码登录")
            except Exception as e:
                logger.warning(f"切换登录方式失败，继续尝试: {e}")
            
            # 输入手机号
            phone_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, LOGIN_SELECTORS["phone_input"]))
            )
            phone_input.clear()
            phone_input.send_keys(phone)
            time.sleep(1)
            logger.info("✅ 已输入手机号")
            
            # 输入密码
            password_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, LOGIN_SELECTORS["password_input"]))
            )
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(1)
            logger.info("✅ 已输入密码")
            
            # 点击登录按钮
            login_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, LOGIN_SELECTORS["login_button"]))
            )
            login_button.click()
            logger.info("✅ 已点击登录按钮")
            
            # 等待登录完成（检查是否跳转到主页）
            time.sleep(5)
            
            # 检查登录状态
            if self._check_login_status():
                self.is_logged_in = True
                logger.info("✅ 登录成功")
                return True
            else:
                logger.error("❌ 登录失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 登录过程中发生错误: {e}")
            return False
    
    def _check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            # 检查URL是否包含登录相关路径
            current_url = self.driver.current_url
            if "login" in current_url.lower():
                return False
            
            # 检查localStorage中是否有认证信息
            r_tk = self.driver.execute_script("return localStorage.getItem('r_tk');")
            s_tk = self.driver.execute_script("return localStorage.getItem('s_tk');")
            
            if r_tk or s_tk:
                logger.info("✅ 检测到认证信息，登录成功")
                return True
            else:
                logger.warning("⚠️ 未检测到认证信息")
                return False
                
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    def search_and_get_codes(self, bond_names: List[str]) -> List[str]:
        """
        搜索债券并获取代码列表
        
        Args:
            bond_names: 债券名称列表
            
        Returns:
            List[str]: 债券代码列表
        """
        try:
            logger.info(f"开始搜索 {len(bond_names)} 个债券")
            
            all_codes = []
            
            for i, bond_name in enumerate(bond_names):
                logger.info(f"搜索第 {i+1}/{len(bond_names)} 个债券: {bond_name}")
                
                try:
                    # 执行搜索
                    codes = self._search_single_bond(bond_name)
                    if codes:
                        all_codes.extend(codes)
                        logger.info(f"✅ 找到 {len(codes)} 个代码: {bond_name}")
                    else:
                        logger.warning(f"⚠️ 未找到代码: {bond_name}")
                    
                    # 随机延迟，避免请求过快
                    delay = random.uniform(2, 4)
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"❌ 搜索债券失败 {bond_name}: {e}")
                    continue
            
            # 去重
            unique_codes = list(set(all_codes))
            logger.info(f"✅ 搜索完成，共找到 {len(unique_codes)} 个唯一代码")
            
            self.codes_to_process = unique_codes
            return unique_codes
            
        except Exception as e:
            logger.error(f"❌ 搜索过程失败: {e}")
            return []
    
    def _search_single_bond(self, bond_name: str) -> List[str]:
        """
        搜索单个债券并获取代码
        
        Args:
            bond_name: 债券名称
            
        Returns:
            List[str]: 债券代码列表
        """
        try:
            # 访问搜索页面
            search_url = f"{BASE_URL}/search"
            self.driver.get(search_url)
            time.sleep(3)
            
            # 等待搜索框加载
            wait = WebDriverWait(self.driver, ELEMENT_TIMEOUT)
            
            # 查找搜索框（这里需要根据实际页面调整选择器）
            search_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[placeholder*='搜索'], .search-input input"))
            )
            
            # 清空并输入搜索关键词
            search_input.clear()
            search_input.send_keys(bond_name)
            time.sleep(1)
            
            # 按回车或点击搜索按钮
            search_input.send_keys(Keys.RETURN)
            time.sleep(3)
            
            # 拦截网络请求获取代码
            codes = self._intercept_search_response()
            
            return codes if codes else []
            
        except Exception as e:
            logger.error(f"搜索单个债券失败 {bond_name}: {e}")
            return []
    
    def _intercept_search_response(self) -> List[str]:
        """
        拦截搜索API响应并提取债券代码
        
        Returns:
            List[str]: 债券代码列表
        """
        try:
            # 获取性能日志
            logs = self.driver.get_log('performance')
            codes = []
            
            for log in logs:
                try:
                    message = json.loads(log['message'])
                    
                    # 查找网络请求
                    if message['message']['method'] == 'Network.responseReceived':
                        response = message['message']['params']['response']
                        url = response.get('url', '')
                        
                        # 检查是否是multipleSearch API请求
                        if 'multipleSearch' in url:
                            logger.info(f"✅ 找到multipleSearch API请求: {url}")
                            
                            # 获取响应内容
                            request_id = message['message']['params']['requestId']
                            try:
                                response_body = self.driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                                response_text = response_body.get('body', '')
                                
                                if response_text:
                                    # 解析JSON响应
                                    api_data = json.loads(response_text)
                                    if api_data.get('returncode') == 0:
                                        # 提取债券代码
                                        codes = self._extract_codes_from_response(api_data)
                                        logger.info(f"✅ 成功提取 {len(codes)} 个债券代码")
                                        break
                            except Exception as e:
                                logger.warning(f"解析API响应失败: {e}")
                                continue
                                
                except Exception as e:
                    continue
            
            return codes
            
        except Exception as e:
            logger.error(f"拦截搜索响应失败: {e}")
            return []
    
    def _extract_codes_from_response(self, api_data: Dict) -> List[str]:
        """
        从API响应中提取债券代码
        
        Args:
            api_data: API响应数据
            
        Returns:
            List[str]: 债券代码列表
        """
        try:
            codes = []
            data_list = api_data.get('data', {}).get('data', [])
            
            for item in data_list:
                # 提取债券代码（根据实际API响应结构调整）
                code = item.get('code') or item.get('id') or item.get('bondCode')
                if code:
                    codes.append(str(code))
            
            return codes
            
        except Exception as e:
            logger.error(f"提取债券代码失败: {e}")
            return []
    
    def get_auth_package(self) -> Optional[Dict]:
        """
        获取认证包（headers和cookies）
        
        Returns:
            Dict: 包含headers和cookies的认证包
        """
        try:
            if not self.is_logged_in:
                logger.error("尚未登录，无法获取认证包")
                return None
            
            logger.info("开始提取认证包...")
            
            # 获取cookies
            cookies = {}
            for cookie in self.driver.get_cookies():
                cookies[cookie['name']] = cookie['value']
            
            # 获取认证headers
            headers = self._extract_auth_headers()
            
            # 构建认证包
            auth_package = {
                'headers': headers,
                'cookies': cookies
            }
            
            self.auth_package = auth_package
            logger.info("✅ 认证包提取成功")
            logger.debug(f"Headers: {list(headers.keys())}")
            logger.debug(f"Cookies: {list(cookies.keys())}")
            
            return auth_package
            
        except Exception as e:
            logger.error(f"❌ 提取认证包失败: {e}")
            return None
    
    def _extract_auth_headers(self) -> Dict:
        """
        提取认证headers
        
        Returns:
            Dict: 认证headers
        """
        try:
            headers = DEFAULT_HEADERS.copy()
            
            # 从localStorage提取认证信息
            pcuss = self.driver.execute_script("return localStorage.getItem('s_tk');")
            user = self.driver.execute_script("return localStorage.getItem('r_tk');")
            
            if pcuss:
                pcuss = pcuss.strip('"')
                headers['pcuss'] = pcuss
                logger.info(f"✅ 提取pcuss: {pcuss[:20]}...")
            
            if user:
                user = user.strip('"')
                headers['user'] = user
                logger.info(f"✅ 提取user: {user[:20]}...")
            
            # 添加其他必要的headers
            headers.update({
                'client': 'pc-web;pro',
                'system': 'new',
                'terminal': 'pc-web;pro',
                'ver': '20250903'
            })
            
            return headers
            
        except Exception as e:
            logger.error(f"提取认证headers失败: {e}")
            return DEFAULT_HEADERS.copy()
    
    def get_codes_and_auth(self, bond_names: List[str], phone: str, password: str) -> Tuple[List[str], Optional[Dict]]:
        """
        完整流程：登录 -> 搜索 -> 获取代码和认证包
        
        Args:
            bond_names: 债券名称列表
            phone: 手机号
            password: 密码
            
        Returns:
            Tuple[List[str], Optional[Dict]]: (债券代码列表, 认证包)
        """
        try:
            logger.info("开始Selenium认证和代码获取流程...")
            
            # 1. 初始化驱动
            if not self.initialize_driver():
                return [], None
            
            # 2. 登录
            if not self.login_with_password(phone, password):
                return [], None
            
            # 3. 搜索并获取代码
            codes = self.search_and_get_codes(bond_names)
            if not codes:
                logger.warning("未获取到任何债券代码")
                return [], None
            
            # 4. 获取认证包
            auth_package = self.get_auth_package()
            if not auth_package:
                logger.error("获取认证包失败")
                return [], None
            
            logger.info(f"✅ Selenium流程完成，获取到 {len(codes)} 个代码")
            return codes, auth_package
            
        except Exception as e:
            logger.error(f"❌ Selenium流程失败: {e}")
            return [], None
        finally:
            # 关闭浏览器
            self.close()
    
    def close(self):
        """关闭浏览器驱动"""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("✅ 浏览器已关闭")
        except Exception as e:
            logger.warning(f"关闭浏览器时出错: {e}")


def test_selenium_auth():
    """测试Selenium认证功能"""
    try:
        # 测试数据
        test_bonds = ["21北京城投债01", "22上海城投债02"]
        test_phone = "15390314229"  # 请替换为真实手机号
        test_password = ""  # 请设置密码
        
        # 创建认证管理器
        auth_manager = SeleniumAuthManager(headless=False)
        
        # 执行完整流程
        codes, auth_package = auth_manager.get_codes_and_auth(
            test_bonds, test_phone, test_password
        )
        
        if codes and auth_package:
            logger.info(f"✅ 测试成功！获取到 {len(codes)} 个代码")
            logger.info(f"代码列表: {codes}")
            logger.info(f"认证包keys: {list(auth_package.keys())}")
        else:
            logger.error("❌ 测试失败")
            
    except Exception as e:
        logger.error(f"测试失败: {e}")


if __name__ == "__main__":
    test_selenium_auth()
