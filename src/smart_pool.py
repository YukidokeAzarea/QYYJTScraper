"""
智能多号池管理器
实现主账号优先，API限制时自动切换的策略
"""

import time
import random
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from loguru import logger

from .scraper import QYYJTScraper
from .account_pool import AccountPool, AccountInfo
from .config import *


class SmartAccountPool:
    """智能多号池管理器"""
    
    def __init__(self):
        # 从配置文件加载账号
        accounts_config = self._load_accounts_config()
        self.account_pool = AccountPool(accounts_config)
        self.current_scraper = None
        self.current_account = None
        self.account_usage_stats = {}  # 账号使用统计
        self.api_limit_detected = False
        self.max_requests_per_account = 50  # 每个账号最大请求数
        self.request_count = 0
        
        # 轮询机制相关
        self.current_round = 1
        self.accounts_used_this_round = set()  # 当前轮次已使用的账号
        self.all_accounts_exhausted = False  # 所有账号是否都已用完
    
    def _load_accounts_config(self) -> List[Dict]:
        """从配置文件加载账号配置"""
        try:
            config_file = Path("accounts_config.json")
            if not config_file.exists():
                logger.error("❌ 账号配置文件不存在: accounts_config.json")
                return []
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            accounts = config.get("accounts", [])
            logger.info(f"📋 从配置文件加载了 {len(accounts)} 个账号")
            return accounts
            
        except Exception as e:
            logger.error(f"❌ 加载账号配置失败: {e}")
            return []
        
    def initialize(self) -> bool:
        """初始化智能多号池"""
        try:
            # 加载账号池
            if not self.account_pool.load_from_file():
                logger.error("❌ 无法加载账号池")
                return False
            
            # 获取可用账号
            available_accounts = [acc for acc in self.account_pool.accounts if acc.is_available]
            if not available_accounts:
                logger.error("❌ 没有可用的账号")
                return False
            
            logger.info(f"📊 智能多号池初始化成功，可用账号: {len(available_accounts)}")
            for i, acc in enumerate(available_accounts, 1):
                logger.info(f"  {i}. {acc.phone} ({'已登录' if acc.is_logged_in else '未登录'})")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 初始化智能多号池失败: {e}")
            return False
    
    def is_api_limit_error(self, error_message: str) -> bool:
        """检测是否为API限制错误"""
        limit_keywords = [
            "请求过多",
            "请稍后再试", 
            "频率限制",
            "rate limit",
            "too many requests",
            "429",
            "限流",
            "请稍后",
            "频繁"
        ]
        
        error_lower = error_message.lower()
        for keyword in limit_keywords:
            if keyword in error_lower:
                return True
        return False
    
    def get_next_available_account(self) -> Optional[AccountInfo]:
        """获取下一个可用的账号（轮询机制）"""
        try:
            # 按优先级排序：已登录的账号优先，排除当前轮次已使用的
            available_accounts = [
                acc for acc in self.account_pool.accounts 
                if acc.is_available and acc.phone not in self.accounts_used_this_round
            ]
            
            logger.debug(f"🔍 可用账号检查: 总账号数={len(self.account_pool.accounts)}, 可用账号数={len([acc for acc in self.account_pool.accounts if acc.is_available])}, 当前轮次已使用={len(self.accounts_used_this_round)}")
            logger.debug(f"🔍 当前轮次已使用的账号: {list(self.accounts_used_this_round)}")
            
            if not available_accounts:
                # 当前轮次没有可用账号，检查是否可以开始新一轮
                if self._can_start_new_round():
                    logger.info("🔄 开始新一轮，重置账号状态")
                    self._start_new_round()
                    # 重新获取可用账号
                    available_accounts = [
                        acc for acc in self.account_pool.accounts 
                        if acc.is_available and acc.phone not in self.accounts_used_this_round
                    ]
                    logger.debug(f"🔍 新一轮后可用账号数: {len(available_accounts)}")
                else:
                    # 检查是否所有账号都已用完
                    total_available = len([acc for acc in self.account_pool.accounts if acc.is_available])
                    if len(self.accounts_used_this_round) >= total_available:
                        self.all_accounts_exhausted = True
                        logger.warning("⚠️ 当前轮次所有账号都已用完")
                    else:
                        logger.warning("⚠️ 当前轮次没有可用账号")
                    return None
            
            # 按登录状态和错误次数排序
            available_accounts.sort(key=lambda x: (not x.is_logged_in, x.error_count))
            
            if available_accounts:
                selected_account = available_accounts[0]
                # 标记为当前轮次已使用
                self.accounts_used_this_round.add(selected_account.phone)
                logger.info(f"🔄 轮次 {self.current_round}: 选择账号 {selected_account.phone}")
                return selected_account
            else:
                logger.warning("⚠️ 没有可用的账号")
                return None
                
        except Exception as e:
            logger.error(f"❌ 获取可用账号失败: {e}")
            return None
    
    def _can_start_new_round(self) -> bool:
        """检查是否可以开始新一轮"""
        # 检查是否有账号在冷却期后可以重新使用
        current_time = time.time()
        for account in self.account_pool.accounts:
            # 检查账号是否在冷却期
            if account.phone in self.account_usage_stats:
                last_used = self.account_usage_stats[account.phone].get('last_used', 0)
                # 如果距离上次使用超过5分钟，可以重新使用（基于请求次数的切换）
                if current_time - last_used > 300:  # 5分钟
                    return True
            else:
                # 没有使用记录的账号可以直接使用
                return True
        return False
    
    def _start_new_round(self):
        """开始新一轮"""
        self.current_round += 1
        self.accounts_used_this_round.clear()
        self.all_accounts_exhausted = False
        
        # 重置所有账号的可用状态（除了那些真正遇到API限制的）
        current_time = time.time()
        for account in self.account_pool.accounts:
            if account.phone in self.account_usage_stats:
                last_used = self.account_usage_stats[account.phone].get('last_used', 0)
                # 如果距离上次使用超过5分钟，重新标记为可用（基于请求次数的切换）
                if current_time - last_used > 300:  # 5分钟
                    account.is_available = True
                    account.error_count = 0  # 重置错误计数
            else:
                # 没有使用记录的账号保持可用
                account.is_available = True
        
        logger.info(f"🔄 开始第 {self.current_round} 轮账号轮询")
    
    def create_new_scraper(self) -> Optional[QYYJTScraper]:
        """创建新的爬虫实例"""
        try:
            # 关闭当前爬虫
            if self.current_scraper:
                self.current_scraper.close()
            
            # 创建新爬虫
            scraper = QYYJTScraper(use_account_pool=False)
            logger.info("🔄 创建新的爬虫实例")
            return scraper
            
        except Exception as e:
            logger.error(f"❌ 创建爬虫实例失败: {e}")
            return None
    
    def switch_to_account(self, account: AccountInfo) -> bool:
        """切换到指定账号"""
        try:
            logger.info(f"🔄 切换到账号: {account.phone}")
            
            # 创建新的爬虫实例
            scraper = self.create_new_scraper()
            if not scraper:
                return False
            
            # 登录账号
            if not scraper.auto_login_with_password(account.phone, account.password):
                logger.error(f"❌ 账号 {account.phone} 登录失败")
                return False
            
            # 更新当前状态
            self.current_scraper = scraper
            self.current_account = account
            self.request_count = 0  # 重置请求计数
            self.api_limit_detected = False
            
            # 更新账号统计
            if account.phone not in self.account_usage_stats:
                self.account_usage_stats[account.phone] = {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'api_limit_hits': 0,
                    'last_used': time.time()
                }
            
            logger.info(f"✅ 成功切换到账号: {account.phone}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 切换账号失败: {e}")
            return False
    
    def get_initial_account(self) -> bool:
        """获取初始账号"""
        try:
            # 获取下一个可用账号
            account = self.get_next_available_account()
            if not account:
                logger.error("❌ 没有可用的账号")
                return False
            
            # 切换到该账号
            return self.switch_to_account(account)
            
        except Exception as e:
            logger.error(f"❌ 获取初始账号失败: {e}")
            return False
    
    def handle_api_limit(self) -> bool:
        """处理API限制，切换到下一个账号"""
        try:
            logger.warning("⚠️ 检测到API限制，准备切换账号")
            
            # 标记当前账号遇到API限制
            if self.current_account:
                self.current_account.is_available = False
                self.current_account.error_count += 1
                if self.current_account.phone in self.account_usage_stats:
                    self.account_usage_stats[self.current_account.phone]['api_limit_hits'] += 1
            
            # 获取下一个可用账号
            next_account = self.get_next_available_account()
            if not next_account:
                # 如果所有账号都已用完，尝试开始新一轮
                if self.all_accounts_exhausted:
                    if self._can_start_new_round():
                        self._start_new_round()
                        next_account = self.get_next_available_account()
                        if not next_account:
                            logger.error("❌ 无法开始新一轮，所有账号都已用完")
                            return False
                    else:
                        logger.error("❌ 所有账号都已用完，无法继续")
                        return False
                else:
                    logger.error("❌ 没有更多可用账号")
                    return False
            
            # 切换到下一个账号
            return self.switch_to_account(next_account)
            
        except Exception as e:
            logger.error(f"❌ 处理API限制失败: {e}")
            return False
    
    def force_switch_account(self) -> bool:
        """强制切换到下一个账号（基于请求次数）"""
        try:
            logger.info(f"🔄 强制切换账号 (当前请求数: {self.request_count}/{self.max_requests_per_account})")
            
            # 重置请求计数
            self.request_count = 0
            
            # 标记当前账号为已使用（但不标记为不可用）
            if self.current_account:
                self.accounts_used_this_round.add(self.current_account.phone)
                # 更新使用统计
                if self.current_account.phone in self.account_usage_stats:
                    self.account_usage_stats[self.current_account.phone]['last_used'] = time.time()
                    self.account_usage_stats[self.current_account.phone]['requests_this_round'] = 0
            
            # 获取下一个可用账号
            next_account = self.get_next_available_account()
            if not next_account:
                # 如果所有账号都已用完，尝试开始新一轮
                if self.all_accounts_exhausted:
                    if self._can_start_new_round():
                        self._start_new_round()
                        next_account = self.get_next_available_account()
                        if not next_account:
                            logger.error("❌ 无法开始新一轮，所有账号都已用完")
                            return False
                    else:
                        logger.error("❌ 所有账号都已用完，无法继续")
                        return False
                else:
                    logger.error("❌ 没有更多可用账号")
                    return False
            
            # 切换到下一个账号
            return self.switch_to_account(next_account)
            
        except Exception as e:
            logger.error(f"❌ 强制切换账号失败: {e}")
            return False
    
    def process_bond_with_retry(self, bond_name: str) -> Tuple[bool, Dict]:
        """处理单个债券，带智能重试和账号切换"""
        result = {
            'bond_name': bond_name,
            'success': False,
            'documents_found': 0,
            'account_used': None,
            'error_message': None,
            'api_limit_hit': False
        }
        
        max_attempts = 3  # 最大尝试次数
        
        for attempt in range(max_attempts):
            try:
                # 确保有可用的爬虫实例
                if not self.current_scraper or not self.current_account:
                    if not self.get_initial_account():
                        result['error_message'] = '无法获取可用账号'
                        return False, result
                
                # 检查是否需要基于请求次数切换账号
                if self.request_count >= self.max_requests_per_account:
                    logger.info(f"🔄 账号 {self.current_account.phone} 已达到最大请求数 {self.max_requests_per_account}，准备切换")
                    if self.force_switch_account():
                        logger.info("✅ 已切换到新账号")
                        continue
                    else:
                        logger.error("❌ 无法切换到新账号")
                        result['error_message'] = '无法切换到新账号'
                        return False, result
                
                logger.info(f"🔍 处理债券: {bond_name} (尝试 {attempt + 1}/{max_attempts}, 账号: {self.current_account.phone})")
                
                # 添加请求延迟，避免频率过高
                if attempt > 0:  # 重试时才延迟
                    delay = 5 + random.uniform(2, 4)  # 5-9秒延迟
                    logger.info(f"等待 {delay:.1f} 秒后发送请求...")
                    time.sleep(delay)
                else:
                    # 第一次请求也要延迟
                    if hasattr(self, '_last_request_time'):
                        time_since_last = time.time() - self._last_request_time
                        if time_since_last < 5:
                            delay = 5 - time_since_last + random.uniform(1, 2)
                            logger.info(f"距离上次请求仅 {time_since_last:.1f} 秒，等待 {delay:.1f} 秒...")
                            time.sleep(delay)
                    else:
                        # 第一次请求，延迟3-5秒
                        delay = 3 + random.uniform(1, 2)
                        logger.info(f"首次请求，等待 {delay:.1f} 秒...")
                        time.sleep(delay)
                
                # 记录本次请求时间
                self._last_request_time = time.time()
                
                # 使用新的完整流程获取债券文档
                documents = self.current_scraper.get_bond_documents_complete(bond_name)
                if not documents:
                    result['error_message'] = '未找到相关文档'
                    
                    # 如果不是需要切换账号的错误，直接重试
                    if attempt < max_attempts - 1:
                        logger.warning(f"⚠️ 未找到文档，等待后重试...")
                        time.sleep(2)  # 等待2秒后重试
                        continue
                    else:
                        logger.error(f"❌ 达到最大重试次数，跳过债券: {bond_name}")
                        return False, result
                
                # 成功处理
                result['success'] = True
                result['documents'] = documents  # 添加documents字段
                result['documents_found'] = len(documents)
                result['account_used'] = self.current_account.phone
                
                # 更新统计
                self.request_count += 1
                if self.current_account.phone in self.account_usage_stats:
                    self.account_usage_stats[self.current_account.phone]['total_requests'] += 1
                    self.account_usage_stats[self.current_account.phone]['successful_requests'] += 1
                    self.account_usage_stats[self.current_account.phone]['last_used'] = time.time()
                
                logger.info(f"✅ 成功处理 {bond_name}: 找到 {len(documents)} 个文档 (账号: {self.current_account.phone})")
                return True, result
                
            except Exception as e:
                error_msg = str(e)
                result['error_message'] = error_msg
                
                # 检查是否为API限制错误
                if self.is_api_limit_error(error_msg):
                    result['api_limit_hit'] = True
                    logger.warning(f"⚠️ 检测到API限制: {error_msg}")
                    
                    # 尝试切换到下一个账号
                    if self.handle_api_limit():
                        logger.info("🔄 已切换到新账号，继续重试")
                        continue
                    else:
                        logger.error("❌ 无法切换到新账号")
                        return False, result
                else:
                    logger.error(f"❌ 处理债券 {bond_name} 时发生错误: {error_msg}")
                    if attempt < max_attempts - 1:
                        logger.info("🔄 等待后重试...")
                        time.sleep(random.uniform(2, 4))
                        continue
                    else:
                        return False, result
        
        return False, result
    
    def get_usage_stats(self) -> Dict:
        """获取使用统计"""
        return {
            'account_stats': self.account_usage_stats,
            'current_account': self.current_account.phone if self.current_account else None,
            'request_count': self.request_count,
            'api_limit_detected': self.api_limit_detected,
            'current_round': self.current_round,
            'accounts_used_this_round': list(self.accounts_used_this_round),
            'all_accounts_exhausted': self.all_accounts_exhausted
        }
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.current_scraper:
                self.current_scraper.close()
            logger.info("🧹 智能多号池资源清理完成")
        except Exception as e:
            logger.warning(f"⚠️ 清理资源时发生错误: {e}")
    
    def print_stats(self):
        """打印使用统计"""
        logger.info("\n📊 智能多号池使用统计:")
        logger.info("=" * 50)
        
        for account_phone, stats in self.account_usage_stats.items():
            success_rate = stats['successful_requests'] / stats['total_requests'] * 100 if stats['total_requests'] > 0 else 0
            logger.info(f"账号 {account_phone}:")
            logger.info(f"  总请求: {stats['total_requests']}")
            logger.info(f"  成功请求: {stats['successful_requests']} ({success_rate:.1f}%)")
            logger.info(f"  API限制: {stats['api_limit_hits']}")
            logger.info(f"  最后使用: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stats['last_used']))}")
        
        logger.info(f"\n轮询状态:")
        logger.info(f"  当前轮次: {self.current_round}")
        logger.info(f"  当前轮次已使用账号: {len(self.accounts_used_this_round)}")
        logger.info(f"  所有账号是否已用完: {'是' if self.all_accounts_exhausted else '否'}")
        logger.info(f"当前账号: {self.current_account.phone if self.current_account else 'None'}")
        logger.info(f"当前请求数: {self.request_count}")
        logger.info(f"API限制检测: {'是' if self.api_limit_detected else '否'}")
