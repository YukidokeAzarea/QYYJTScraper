# E:\BaiduSyncdisk\数据库\1-城投公司\QYYJTScraper\src\login_handler.py

import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from . import config

# --- [核心改动] ---
# 函数签名改变，接收 phone 和 password 作为参数
def get_authenticated_session(phone: str, password: str, search_term: str):
    """
    [最终版] 模拟登录和搜索，然后正确地从 localStorage 的 'u_info' 中提取用户ID。
    :param phone: 登录用的手机号
    :param password: 登录用的密码
    :param search_term: 需要在页面上模拟搜索的关键词
    :return: 一个包含完整认证信息的字典，失败则返回 None。
    """
    print(f"[{phone}] 开始模拟登录...")
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # 如果需要后台运行，可以取消这行注释
    options.add_argument("--start-maximized")
    
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(config.LOGIN_URL)
        wait = WebDriverWait(driver, 20)

        # 1-4. 登录并模拟搜索
        print(f"[{phone}] 等待'账户密码登录'标签...")
        wait.until(EC.element_to_be_clickable((By.XPATH, config.LOGIN_XPATHS["password_login_tab"]))).click()
        print(f"[{phone}] 已切换到'账户密码登录'。")
        
        # --- [核心改动] ---
        # 使用传入的参数填充账号密码
        wait.until(EC.visibility_of_element_located((By.XPATH, config.LOGIN_XPATHS["phone_input"]))).send_keys(phone)
        driver.find_element(By.XPATH, config.LOGIN_XPATHS["password_input"]).send_keys(password)
        
        print(f"[{phone}] 已输入账号和密码。")
        driver.find_element(By.XPATH, config.LOGIN_XPATHS["login_button"]).click()
        print(f"[{phone}] 已点击登录按钮。")
        print(f"[{phone}] 等待登录跳转至首页...")
        home_search_input = wait.until(EC.visibility_of_element_located((By.XPATH, config.LOGIN_XPATHS["home_search_input"])))
        print(f"[{phone}] 登录成功！已跳转到首页。")
        print(f"[{phone}] 正在模拟搜索: '{search_term}'...")
        home_search_input.send_keys(search_term)
        home_search_input.send_keys(Keys.RETURN)
        print(f"[{phone}] 等待搜索结果页面加载...")
        wait.until(EC.presence_of_element_located((By.XPATH, config.LOGIN_XPATHS["search_result_securities_tab"])))
        print(f"[{phone}] 搜索结果页面加载成功！")
        time.sleep(2)

        # 5. 正确地提取所有认证信息
        print(f"[{phone}] 正在从 localStorage 提取认证信息...")
        
        auth_token = driver.execute_script("return window.localStorage.getItem('s_tk');")
        if not auth_token:
            raise ValueError("在 localStorage 中无法找到 's_tk' token。")

        u_info_str = driver.execute_script("return window.localStorage.getItem('u_info');")
        if not u_info_str:
            raise ValueError("在 localStorage 中无法找到 'u_info' 对象。")
            
        u_info_obj = json.loads(u_info_str)
        user_id = u_info_obj.get('user')

        if not user_id:
            raise ValueError("在 'u_info' 对象中无法找到 'user' 键。")

        auth_token = auth_token.strip('"')
        user_id = user_id.strip('"')

        token_header_name = "pcuss"
        token_value = auth_token

        cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
        print(f"[{phone}] 成功获取认证 Token (s_tk): {token_value[:30]}...")
        print(f"[{phone}] 成功获取用户ID (user): {user_id[:30]}...")
        
        return {
            "token_name": token_header_name, 
            "token_value": token_value, 
            "user_id": user_id,
            "cookies": cookies
        }

    except TimeoutException as e:
        print(f"[{phone}] 操作超时：在等待元素时出错。 {e}")
        driver.save_screenshot("login_error_timeout.png")
        return None
    except Exception as e:
        print(f"[{phone}] 登录或模拟搜索过程中发生错误: {e}")
        driver.save_screenshot("login_error_final.png")
        return None
    finally:
        driver.quit()
        print(f"[{phone}] 浏览器已关闭。")
