"""
企研通账号池管理模块
支持多账号登录、token管理和轮换使用
"""

import time
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from .config import *


@dataclass
class AccountInfo:
    """账号信息数据类"""
    phone: str
    password: str = ""  # 如果有密码的话
    pcuss_token: str = ""
    r_tk: str = ""
    s_tk: str = ""
    user_id: str = ""
    cookies: Dict = None
    is_logged_in: bool = False
    last_used: float = 0.0
    request_count: int = 0
    error_count: int = 0
    is_available: bool = True
    
    def __post_init__(self):
        if self.cookies is None:
            self.cookies = {}


class AccountPool:
    """账号池管理器"""
    
    def __init__(self, accounts_config: List[Dict] = None):
        """
        初始化账号池
        
        Args:
            accounts_config: 账号配置列表，格式：[{"phone": "手机号", "password": "密码"}]
        """
        self.accounts: List[AccountInfo] = []
        self.current_index = 0
        self.pool_file = Path("data/account_pool.json")
        self.driver = None
        
        # 加载账号配置
        if accounts_config:
            for acc_config in accounts_config:
                account = AccountInfo(
                    phone=acc_config.get("phone", ""),
                    password=acc_config.get("password", "")
                )
                self.accounts.append(account)
        
        # 从文件加载已保存的账号信息
        self.load_from_file()
        
        logger.info(f"账号池初始化完成，共 {len(self.accounts)} 个账号")
    
    def add_account(self, phone: str, password: str = "") -> bool:
        """添加新账号到池中"""
        # 检查是否已存在
        for account in self.accounts:
            if account.phone == phone:
                logger.warning(f"账号 {phone} 已存在于池中")
                return False
        
        account = AccountInfo(phone=phone, password=password)
        self.accounts.append(account)
        self.save_to_file()
        logger.info(f"已添加账号 {phone} 到池中")
        return True
    
    def get_available_account(self) -> Optional[AccountInfo]:
        """获取可用的账号（轮换策略）"""
        if not self.accounts:
            logger.error("账号池为空")
            return None
        
        # 过滤可用账号
        available_accounts = [acc for acc in self.accounts if acc.is_available and acc.is_logged_in]
        
        if not available_accounts:
            logger.warning("没有可用的已登录账号")
            return None
        
        # 轮换策略：选择最久未使用的账号
        available_accounts.sort(key=lambda x: x.last_used)
        selected_account = available_accounts[0]
        
        # 更新使用时间
        selected_account.last_used = time.time()
        selected_account.request_count += 1
        
        logger.info(f"选择账号 {selected_account.phone} (使用次数: {selected_account.request_count})")
        return selected_account
    
    def login_account(self, account: AccountInfo) -> bool:
        """登录指定账号"""
        try:
            logger.info(f"开始登录账号 {account.phone}")
            
            # 设置Chrome选项
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # 初始化浏览器
            if not self.driver:
                try:
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e:
                    logger.error(f"初始化Chrome驱动失败: {e}")
                    return False
            
            # 使用自动登录功能
            if account.password:
                logger.info(f"使用自动登录: {account.phone}")
                return self.auto_login_with_password(account.phone, account.password)
            else:
                # 如果没有密码，回退到手动登录
                logger.info(f"密码未设置，使用手动登录: {account.phone}")
                return self.manual_login(account.phone)
                
        except Exception as e:
            logger.error(f"登录账号 {account.phone} 失败: {e}")
            return False
    
    def auto_login_with_password(self, phone: str, password: str) -> bool:
        """自动登录（使用账号密码）"""
        try:
            from .config import LOGIN_URL, LOGIN_SELECTORS
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            logger.info(f"开始自动登录: {phone}")
            self.driver.get(LOGIN_URL)
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
            time.sleep(5)
            
            # 检查登录状态
            return self._check_login_status()
            
        except Exception as e:
            logger.error(f"自动登录失败: {e}")
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
            self._extract_account_info(AccountInfo(phone="temp"))
            
            # 检查是否有有效的认证信息
            if hasattr(self, 'current_account') and self.current_account:
                if self.current_account.pcuss_token and self.current_account.user_id:
                    self.current_account.is_logged_in = True
                    logger.info("✅ 登录状态检查成功")
                    return True
            
            logger.warning("❌ 认证信息不完整，登录失败")
            return False
                
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    def manual_login(self, phone: str) -> bool:
        """手动登录（当没有密码时）"""
        try:
            # 访问登录页面
            self.driver.get("https://www.qyyjt.cn/user/login")
            time.sleep(3)
            
            # 等待用户手动登录
            print(f"\n{'='*60}")
            print(f"🔐 请登录账号: {phone}")
            print(f"{'='*60}")
            print("📋 请按以下步骤手动操作：")
            print("   1. 手动输入手机号码")
            print("   2. 手动点击获取验证码按钮")
            print("   3. 如果出现图形验证码，请手动输入并点击确定")
            print("   4. 等待手机验证码发送")
            print("   5. 手动输入手机验证码")
            print("   6. 手动点击登录按钮")
            print(f"{'='*60}")
            print("⏰ 请在浏览器中完成所有操作，程序将等待您完成...")
            print("💡 完成后程序会自动检测登录状态")
            print(f"{'='*60}")
            
            # 等待登录完成
            max_wait_time = 300  # 5分钟超时
            check_interval = 5
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                try:
                    current_url = self.driver.current_url
                    
                    # 检查是否已经登录成功
                    if "login" not in current_url.lower() or "dashboard" in current_url.lower() or "home" in current_url.lower():
                        logger.info(f"账号 {account.phone} 登录成功！")
                        
                        # 提取认证信息
                        self._extract_account_info(account)
                        
                        account.is_logged_in = True
                        account.is_available = True
                        account.last_used = time.time()
                        
                        self.save_to_file()
                        print(f"✅ 账号 {account.phone} 登录成功！")
                        return True
                    
                    time.sleep(check_interval)
                    
                except Exception as e:
                    logger.warning(f"检查登录状态时出错: {e}")
                    time.sleep(check_interval)
            
            # 登录超时
            logger.error(f"账号 {account.phone} 登录超时")
            account.is_available = False
            account.error_count += 1
            return False
            
        except Exception as e:
            logger.error(f"登录账号 {account.phone} 时发生错误: {e}")
            account.is_available = False
            account.error_count += 1
            return False
    
    def _extract_account_info(self, account: AccountInfo):
        """提取账号的认证信息"""
        try:
            # 提取Cookies
            cookies = self.driver.get_cookies()
            account.cookies = {cookie['name']: cookie['value'] for cookie in cookies}
            
            # 提取JWT tokens
            r_tk = self.driver.execute_script("return localStorage.getItem('r_tk');")
            if r_tk:
                account.r_tk = r_tk.strip('"')
                logger.info(f"账号 {account.phone} 提取r_tk成功")
            
            s_tk = self.driver.execute_script("return localStorage.getItem('s_tk');")
            if s_tk:
                account.s_tk = s_tk.strip('"')
                account.pcuss_token = s_tk  # s_tk用作pcuss_token
                logger.info(f"账号 {account.phone} 提取s_tk成功")
            
            # 提取用户信息
            u_info = self.driver.execute_script("return localStorage.getItem('u_info');")
            if u_info:
                try:
                    user_data = json.loads(u_info)
                    if 'encryptUser' in user_data:
                        account.user_id = user_data['encryptUser']
                        logger.info(f"账号 {account.phone} 提取用户标识成功")
                except:
                    logger.warning(f"账号 {account.phone} 解析用户信息失败")
            
            logger.info(f"账号 {account.phone} 认证信息提取完成")
            
        except Exception as e:
            logger.error(f"提取账号 {account.phone} 认证信息失败: {e}")
    
    def login_all_accounts(self) -> int:
        """登录所有账号"""
        success_count = 0
        
        for i, account in enumerate(self.accounts, 1):
            if account.is_logged_in:
                logger.info(f"账号 {account.phone} 已登录，跳过")
                success_count += 1
                continue
            
            print(f"\n🔄 登录账号 {i}/{len(self.accounts)}: {account.phone}")
            
            if self.login_account(account):
                success_count += 1
            else:
                logger.error(f"账号 {account.phone} 登录失败")
            
            # 账号间登录间隔
            if i < len(self.accounts):
                wait_time = random.randint(10, 20)
                print(f"⏳ 等待 {wait_time} 秒后登录下一个账号...")
                time.sleep(wait_time)
        
        logger.info(f"账号池登录完成，成功 {success_count}/{len(self.accounts)} 个账号")
        return success_count
    
    def mark_account_error(self, account: AccountInfo, error_msg: str = ""):
        """标记账号出错"""
        account.error_count += 1
        logger.warning(f"账号 {account.phone} 出错: {error_msg} (错误次数: {account.error_count})")
        
        # 如果错误次数过多，暂时禁用账号
        if account.error_count >= 5:
            account.is_available = False
            logger.error(f"账号 {account.phone} 错误次数过多，已禁用")
        
        self.save_to_file()
    
    def reset_account_errors(self, account: AccountInfo):
        """重置账号错误计数"""
        account.error_count = 0
        account.is_available = True
        logger.info(f"账号 {account.phone} 错误计数已重置")
        self.save_to_file()
    
    def get_pool_status(self) -> Dict:
        """获取账号池状态"""
        total = len(self.accounts)
        logged_in = sum(1 for acc in self.accounts if acc.is_logged_in)
        available = sum(1 for acc in self.accounts if acc.is_available and acc.is_logged_in)
        error_accounts = [acc.phone for acc in self.accounts if acc.error_count > 0]
        
        return {
            "total": total,
            "logged_in": logged_in,
            "available": available,
            "error_accounts": error_accounts,
            "accounts": [
                {
                    "phone": acc.phone,
                    "is_logged_in": acc.is_logged_in,
                    "is_available": acc.is_available,
                    "request_count": acc.request_count,
                    "error_count": acc.error_count,
                    "last_used": acc.last_used
                }
                for acc in self.accounts
            ]
        }
    
    def save_to_file(self):
        """保存账号池到文件"""
        try:
            self.pool_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "accounts": [asdict(acc) for acc in self.accounts],
                "current_index": self.current_index,
                "last_updated": time.time()
            }
            
            with open(self.pool_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug("账号池信息已保存到文件")
            
        except Exception as e:
            logger.error(f"保存账号池信息失败: {e}")
    
    def load_from_file(self):
        """从文件加载账号池"""
        try:
            if not self.pool_file.exists():
                logger.info("账号池文件不存在，将创建新的账号池")
                return True  # 文件不存在时也返回True，因为可以继续使用内存中的账号
            
            with open(self.pool_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 恢复账号信息
            if "accounts" in data:
                self.accounts = []
                for acc_data in data["accounts"]:
                    account = AccountInfo(**acc_data)
                    self.accounts.append(account)
            
            if "current_index" in data:
                self.current_index = data["current_index"]
            
            logger.info(f"从文件加载了 {len(self.accounts)} 个账号")
            return True
            
        except Exception as e:
            logger.error(f"加载账号池信息失败: {e}")
            return False
    
    def close(self):
        """关闭浏览器驱动"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.info("浏览器驱动已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器驱动失败: {e}")
    
    def __del__(self):
        """析构函数"""
        self.close()
