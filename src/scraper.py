# E:\BaiduSyncdisk\数据库\1-城投公司\QYYJTScraper\src\scraper.py

import requests
import json
import time   # [新增]
import random # [新增]
from urllib.parse import quote
from . import config

# [新增] 自定义异常，用于通知主程序账号已被限制
class RateLimitException(Exception):
    pass

# [新增] 自定义异常，用于通知主程序 Token 已过期
class TokenExpiredException(Exception):
    pass

class Scraper:
    def __init__(self, auth_session: dict):
        # ... (构造函数不变)
        required_keys = ['token_name', 'token_value', 'user_id', 'cookies']
        if not all(key in auth_session for key in required_keys):
            raise ValueError("认证 session 信息不完整，请检查登录过程。")
        
        self.token_name = auth_session['token_name']
        self.token_value = auth_session['token_value']
        self.user_id = auth_session['user_id']
        self.cookies = auth_session['cookies']
        
        self.base_headers = {
            'accept': 'application/json, text/plain, */*',
            'client': 'pc-web;pro',
            self.token_name: self.token_value,
            'user': self.user_id,
            'terminal': 'pc-web;pro',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'referer': 'https://www.qyyjt.cn/home'
        }
    
    def _check_response_for_errors(self, response_data: dict):
        """ [修改] 检查API响应是否包含需要特殊处理的错误，如速率限制或Token过期 """
        info = response_data.get('info', '')
        return_code = response_data.get('returncode')

        # 检查 Token 过期
        if return_code == 104 and "token过时" in info:
            raise TokenExpiredException(f"Token 已过期 (Code: 104): {info}")

        # 检查 API 速率限制，使用更可靠的 returncode == 206 进行判断
        # 同时为了保险，也检查 info 文本中是否包含 "请求过多"
        if return_code == 206 and "请求过多" in info:
            raise RateLimitException(f"账号被限制 (Code: 206): {info}")

    def search_bond(self, search_term: str):
        # ... (前半部分不变)
        print(f"\n正在搜索: '{search_term}'...")
        
        params = {
            'pagesize': 10,
            'skip': 0,
            'text': search_term,
            'template': 'list',
            'isRelationSearch': 0
        }
        
        headers = self.base_headers.copy()
        encoded_search_term = quote(search_term)
        headers['referer'] = f'https://www.qyyjt.cn/search?text={encoded_search_term}'

        try:
            response = requests.get(
                config.SEARCH_API_URL, 
                headers=headers, 
                params=params, 
                cookies=self.cookies
            )
            response.raise_for_status()
            data = response.json()

            # [修改] 在处理数据前检查是否被限流或Token过期
            self._check_response_for_errors(data)

            if data.get('returncode') == 0 and data.get('data') and data['data'].get('list'):
                # ... (后续逻辑不变)
                if not data['data']['list']:
                    print(f"搜索 '{search_term}' 成功，但未返回任何结果。")
                    return None
                
                bond_info = data['data']['list'][0]
                bond_code = bond_info.get('code')
                bond_name = bond_info.get('name')
                print(f"搜索成功！找到债券 '{bond_name}'，Code: {bond_code}")
                return {"code": bond_code, "name": bond_name}
            else:
                error_msg = data.get('info', data.get('message', '未知错误'))
                print(f"搜索API返回成功，但未找到结果或有业务错误。Return Code: {data.get('returncode')}, Info: {error_msg}")
                print(f"搜索API原始响应: {response.text}")
                return None
        except requests.RequestException as e:
            print(f"搜索请求失败: {e}")
            return None

    def get_announcements(self, bond_code: str):
        # ... (前半部分不变)
        print(f"正在为 Code '{bond_code}' 获取所有公告列表...")
        
        all_announcements = []
        page_num = 1
        page_size = 10 
        current_skip = 0

        while True:
            print(f"  - 正在获取第 {page_num} 页数据 (skip={current_skip})...")

            payload = {
                'code': bond_code,
                'type': 'co',
                'skip': current_skip,
                'size': page_size,
                'oneLevelItemCode': '50',
                'f9Below': 'true'
            }
            
            headers = self.base_headers.copy()
            headers['content-type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
            headers['origin'] = 'https://www.qyyjt.cn'
            headers['referer'] = f'https://www.qyyjt.cn/bond/f9?code={bond_code}'

            try:
                # [新增] 每次请求前随机暂停一下
                sleep_time = random.uniform(*config.DELAY_BETWEEN_PAGES)
                # print(f"    (暂停 {sleep_time:.2f} 秒...)") # 如果你想看详细日志可以取消注释
                time.sleep(sleep_time)
                
                response = requests.post(
                    config.NOTICE_API_URL, 
                    headers=headers, 
                    data=payload, 
                    cookies=self.cookies
                )
                response.raise_for_status()
                data = response.json()

                # [修改] 检查是否被限流或Token过期
                self._check_response_for_errors(data)

                if data.get('returncode') == 0:
                    current_page_announcements = data.get('data', [])
                    
                    if not current_page_announcements:
                        print("  - 已获取所有页面，没有更多公告了。")
                        break 

                    all_announcements.extend(current_page_announcements)
                    print(f"  - 成功获取 {len(current_page_announcements)} 条公告，总数: {len(all_announcements)}。")

                    current_skip += page_size
                    page_num += 1

                else:
                    error_info = data.get('info', '没有具体的错误信息。')
                    print(f"获取第 {page_num} 页公告失败。服务器返回码: {data.get('returncode')}, 信息: {error_info}")
                    print(f"原始响应: {response.text}")
                    return None 

            except requests.RequestException as e:
                print(f"获取第 {page_num} 页公告请求失败: {e}")
                return None
            except json.JSONDecodeError:
                print(f"服务器在第 {page_num} 页返回的不是有效的JSON格式。")
                print(f"原始响应内容: {response.text}")
                return None
        
        print(f"\n公告获取完成！共获取 {len(all_announcements)} 条公告信息。")
        return all_announcements
