"""
Requests数据爬取模块
专门负责使用认证包进行高效的数据爬取
按照README要求，Requests接管所有数据拉取任务
"""

import time
import random
import requests
from typing import Dict, List, Optional
from loguru import logger

from .config import *


class RequestsDataScraper:
    """Requests数据爬取器 - 专门负责数据拉取"""
    
    def __init__(self, auth_package: Dict):
        """
        初始化Requests爬取器
        
        Args:
            auth_package: 包含headers和cookies的认证包
        """
        self.auth_package = auth_package
        self.session = requests.Session()
        self._setup_session()
        
    def _setup_session(self):
        """
        设置Session的headers和cookies
        按照README要求精确构造请求
        """
        try:
            logger.info("🔧 开始设置Requests Session")
            
            # 1. 设置认证headers（从Selenium获取）
            if 'headers' in self.auth_package:
                self.session.headers.update(self.auth_package['headers'])
                logger.info("✅ 已设置认证headers")
                logger.debug(f"Headers keys: {list(self.auth_package['headers'].keys())}")
            else:
                logger.warning("⚠️ 认证包中缺少headers")
            
            # 2. 设置认证cookies（从Selenium获取）
            if 'cookies' in self.auth_package:
                self.session.cookies.update(self.auth_package['cookies'])
                logger.info("✅ 已设置认证cookies")
                logger.debug(f"Cookies keys: {list(self.auth_package['cookies'].keys())}")
            else:
                logger.warning("⚠️ 认证包中缺少cookies")
            
            # 3. 设置固定请求头（根据cURL分析）
            fixed_headers = {
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Ch-Ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"macOS"',
                'Priority': 'u=1, i',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            }
            
            self.session.headers.update(fixed_headers)
            logger.info("✅ 已设置固定请求头")
            
            # 4. 验证关键认证信息
            required_auth_keys = ['pcuss', 'user']
            missing_keys = [key for key in required_auth_keys if key not in self.session.headers]
            if missing_keys:
                logger.warning(f"⚠️ 缺少关键认证信息: {missing_keys}")
            else:
                logger.info("✅ 认证信息完整")
            
            logger.info("✅ Session设置完成")
            
        except Exception as e:
            logger.error(f"❌ Session设置失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
    
    def fetch_bond_documents(self, bond_code: str, bond_short_name: str = "") -> List[Dict]:
        """
        获取指定债券的所有文档
        按照README要求精确构造API请求
        
        Args:
            bond_code: 债券代码
            bond_short_name: 债券简称（可选）
            
        Returns:
            List[Dict]: 文档信息列表
        """
        try:
            logger.info(f"🔍 开始获取债券文档: {bond_code}")
            
            # API配置
            api_url = f"{BASE_URL}/finchinaAPP/v1/finchina-search/v1/getF9NoticeList"
            documents = []
            skip = 0
            size = 50
            page = 1
            
            logger.info(f"📡 API URL: {api_url}")
            
            while True:
                logger.debug(f"📄 获取第 {page} 页数据 (skip={skip}, size={size})")
                
                # 1. 动态构造Referer Header（唯一需要在循环中更新的Header）
                dynamic_referer = f"https://www.qyyjt.cn/detail/bond/notice?code={bond_code}&type=co"
                self.session.headers['Referer'] = dynamic_referer
                logger.debug(f"🔗 Referer: {dynamic_referer}")
                
                # 2. 构造请求体Payload（form-data格式）
                payload = self._construct_payload(bond_code, skip, size)
                logger.debug(f"📦 Payload: {payload}")
                
                # 3. 发送POST请求
                try:
                    response = self.session.post(
                        api_url, 
                        data=payload,  # 使用data参数发送form-data
                        timeout=REQUEST_TIMEOUT
                    )
                    
                    logger.debug(f"📊 响应状态码: {response.status_code}")
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f"❌ 网络请求失败: {e}")
                    break
                
                # 4. 检查响应状态
                if response.status_code != 200:
                    logger.error(f"❌ API请求失败: {response.status_code}")
                    logger.error(f"响应内容: {response.text[:200]}...")
                    break
                
                # 5. 解析JSON响应
                try:
                    data = response.json()
                    logger.debug(f"📋 API响应结构: {list(data.keys())}")
                    
                    # 检查API返回码
                    if data.get('returncode') != 0:
                        error_msg = data.get('message', 'Unknown error')
                        logger.warning(f"⚠️ API返回错误: {error_msg}")
                        break
                    
                    # 6. 获取文档列表
                    items = data.get('data', {}).get('data', [])
                    if not items:
                        logger.info(f"📭 第 {page} 页无数据，停止翻页")
                        break
                    
                    logger.info(f"📄 第 {page} 页获取到 {len(items)} 条原始数据")
                    
                    # 7. 解析文档
                    page_documents = self._parse_documents(items, bond_code, bond_short_name)
                    documents.extend(page_documents)
                    
                    logger.info(f"✅ 第 {page} 页解析出 {len(page_documents)} 个文档")
                    
                    # 8. 检查是否到达最后一页
                    if len(items) < size:
                        logger.info("🏁 已到达最后一页（返回数据少于请求数量）")
                        break
                    
                    # 9. 准备下一页
                    skip += size
                    page += 1
                    
                    # 10. 随机延迟，避免请求过快
                    delay = random.uniform(1, 3)
                    logger.debug(f"⏳ 延迟 {delay:.2f} 秒")
                    time.sleep(delay)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON解析失败: {e}")
                    logger.error(f"响应内容: {response.text[:200]}...")
                    break
                except Exception as e:
                    logger.error(f"❌ 解析API响应失败: {e}")
                    break
            
            logger.info(f"🎉 债券 {bond_code} 共获取到 {len(documents)} 个文档")
            return documents
            
        except Exception as e:
            logger.error(f"❌ 获取债券文档失败 {bond_code}: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return []
    
    def _construct_payload(self, bond_code: str, skip: int, size: int) -> Dict:
        """
        构造API请求体Payload
        按照README要求使用form-data格式
        
        Args:
            bond_code: 债券代码
            skip: 分页偏移量
            size: 每页大小
            
        Returns:
            Dict: 请求体数据
        """
        # 动态字段
        dynamic_fields = {
            'code': bond_code,
            'skip': skip
        }
        
        # 固定字段（根据cURL分析）
        fixed_fields = {
            'type': 'co',
            'size': size,
            'tab': 'notice_bond_coRelated'
        }
        
        # 合并字段
        payload = {**fixed_fields, **dynamic_fields}
        
        logger.debug(f"🔧 构造Payload: 动态字段={dynamic_fields}, 固定字段={fixed_fields}")
        
        return payload
    
    def _parse_documents(self, items: List[Dict], bond_code: str, bond_short_name: str) -> List[Dict]:
        """
        解析文档数据
        
        Args:
            items: API返回的文档列表
            bond_code: 债券代码
            bond_short_name: 债券简称
            
        Returns:
            List[Dict]: 解析后的文档列表
        """
        documents = []
        
        for item in items:
            try:
                # 提取基本信息
                title = item.get('title', '')
                if not title:
                    continue
                
                # 提取下载链接
                download_url = self._extract_download_url(item)
                if not download_url:
                    logger.warning(f"文档无下载链接: {title}")
                    continue
                
                # 提取文档类型
                document_type = self._classify_document_type(title)
                
                # 提取发布日期
                publication_date = self._format_date(item.get('date', ''))
                
                # 提取文件大小
                file_size = self._extract_file_size(item)
                
                # 构造文档信息
                document = {
                    'bond_code': bond_code,
                    'bond_short_name': bond_short_name or bond_code,
                    'bond_full_name': item.get('companyName', bond_short_name or bond_code),
                    'document_title': title,
                    'document_type': document_type,
                    'download_url': download_url,
                    'file_size': file_size,
                    'publication_date': publication_date,
                    'province': '',  # 将在main.py中补充
                    'city': ''       # 将在main.py中补充
                }
                
                documents.append(document)
                
            except Exception as e:
                logger.warning(f"解析文档失败: {e}")
                continue
        
        return documents
    
    def _extract_download_url(self, item: Dict) -> Optional[str]:
        """提取下载链接"""
        try:
            # 尝试多种可能的字段
            url_fields = ['downloadUrl', 'url', 'fileUrl', 'link']
            
            for field in url_fields:
                if field in item and item[field]:
                    url = item[field]
                    # 确保是完整的URL
                    if url.startswith('http'):
                        return url
                    elif url.startswith('/'):
                        return f"{BASE_URL}{url}"
            
            return None
            
        except Exception as e:
            logger.warning(f"提取下载链接失败: {e}")
            return None
    
    def _classify_document_type(self, title: str) -> str:
        """根据标题分类文档类型"""
        title_lower = title.lower()
        
        # 定义关键词映射
        keywords = {
            '募集说明书': ['募集说明书', 'prospectus'],
            '发行公告': ['发行公告', 'issue announcement'],
            '评级报告': ['评级报告', 'rating report'],
            '财务报告': ['财务报告', 'financial report', '年报', '半年报', '季报'],
            '审计报告': ['审计报告', 'audit report'],
            '法律意见书': ['法律意见书', 'legal opinion'],
            '担保函': ['担保函', 'guarantee'],
            '其他': []
        }
        
        for doc_type, keywords_list in keywords.items():
            if doc_type == '其他':
                continue
            for keyword in keywords_list:
                if keyword in title_lower:
                    return doc_type
        
        return '其他'
    
    def _format_date(self, date_str: str) -> str:
        """格式化日期"""
        try:
            if not date_str:
                return ''
            
            # 如果是时间戳
            if date_str.isdigit() and len(date_str) >= 8:
                if len(date_str) >= 10:
                    # 毫秒时间戳
                    timestamp = int(date_str[:10])
                else:
                    # 秒时间戳
                    timestamp = int(date_str)
                
                from datetime import datetime
                return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            
            # 如果已经是日期格式
            if len(date_str) >= 8:
                return date_str[:8] if len(date_str) >= 8 else date_str
            
            return date_str
            
        except Exception as e:
            logger.warning(f"格式化日期失败: {e}")
            return date_str
    
    def _extract_file_size(self, item: Dict) -> str:
        """提取文件大小"""
        try:
            size_fields = ['fileSize', 'size', 'file_size']
            
            for field in size_fields:
                if field in item and item[field]:
                    return str(item[field])
            
            return ''
            
        except Exception as e:
            logger.warning(f"提取文件大小失败: {e}")
            return ''
    
    def fetch_multiple_bonds(self, bond_codes: List[str], bond_names: List[str] = None) -> Dict[str, List[Dict]]:
        """
        批量获取多个债券的文档
        按照README要求遍历code列表进行高效爬取
        
        Args:
            bond_codes: 债券代码列表
            bond_names: 债券简称列表（可选）
            
        Returns:
            Dict[str, List[Dict]]: 每个债券的文档列表
        """
        try:
            logger.info(f"🚀 开始批量获取 {len(bond_codes)} 个债券的文档")
            logger.info(f"📋 债券代码列表: {bond_codes}")
            
            results = {}
            success_count = 0
            error_count = 0
            
            for i, bond_code in enumerate(bond_codes):
                bond_name = bond_names[i] if bond_names and i < len(bond_names) else bond_code
                
                logger.info(f"📊 处理第 {i+1}/{len(bond_codes)} 个债券: {bond_name} ({bond_code})")
                
                try:
                    # 验证API请求构造
                    if not self._validate_api_request(bond_code):
                        logger.warning(f"⚠️ API请求验证失败: {bond_code}")
                        results[bond_code] = []
                        error_count += 1
                        continue
                    
                    # 获取文档
                    documents = self.fetch_bond_documents(bond_code, bond_name)
                    results[bond_code] = documents
                    
                    if documents:
                        success_count += 1
                        logger.info(f"✅ {bond_name}: {len(documents)} 个文档")
                    else:
                        logger.warning(f"⚠️ {bond_name}: 未获取到文档")
                        error_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ 处理债券失败 {bond_name}: {e}")
                    results[bond_code] = []
                    error_count += 1
                    continue
                
                # 随机延迟，避免请求过快
                delay = random.uniform(2, 4)
                logger.debug(f"⏳ 延迟 {delay:.2f} 秒")
                time.sleep(delay)
            
            total_documents = sum(len(docs) for docs in results.values())
            logger.info(f"🎉 批量获取完成！")
            logger.info(f"📈 统计: 成功 {success_count} 个，失败 {error_count} 个，共 {total_documents} 个文档")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 批量获取失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return {}
    
    def _validate_api_request(self, bond_code: str) -> bool:
        """
        验证API请求构造是否正确
        
        Args:
            bond_code: 债券代码
            
        Returns:
            bool: 验证是否通过
        """
        try:
            # 检查认证信息
            required_headers = ['pcuss', 'user']
            missing_headers = [h for h in required_headers if h not in self.session.headers]
            if missing_headers:
                logger.warning(f"⚠️ 缺少认证headers: {missing_headers}")
                return False
            
            # 检查cookies
            if not self.session.cookies:
                logger.warning("⚠️ 缺少认证cookies")
                return False
            
            # 检查API URL
            api_url = f"{BASE_URL}/finchinaAPP/v1/finchina-search/v1/getF9NoticeList"
            if not api_url:
                logger.warning("⚠️ API URL未配置")
                return False
            
            # 检查债券代码
            if not bond_code:
                logger.warning("⚠️ 债券代码为空")
                return False
            
            logger.debug(f"✅ API请求验证通过: {bond_code}")
            return True
            
        except Exception as e:
            logger.error(f"❌ API请求验证失败: {e}")
            return False


def test_requests_scraper():
    """测试Requests爬取功能"""
    try:
        # 模拟认证包
        test_auth_package = {
            'headers': {
                'pcuss': 'test_pcuss_token',
                'user': 'test_user_token',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'client': 'pc-web;pro'
            },
            'cookies': {
                'HWWAFSESTIME': 'test_time',
                'HWWAFSESID': 'test_id'
            }
        }
        
        # 创建爬取器
        scraper = RequestsDataScraper(test_auth_package)
        
        # 测试单个债券
        test_codes = ['TEST001', 'TEST002']
        results = scraper.fetch_multiple_bonds(test_codes, ['测试债券1', '测试债券2'])
        
        logger.info(f"测试结果: {len(results)} 个债券")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")


if __name__ == "__main__":
    test_requests_scraper()
