"""
混合爬取控制器
整合Selenium认证和Requests数据爬取
按照README要求实现完整的混合爬取架构
"""

import time
from typing import Dict, List, Optional, Tuple
from loguru import logger

from .selenium_auth import SeleniumAuthManager
from .requests_scraper import RequestsDataScraper
from .database import DatabaseManager


class HybridScraper:
    """混合爬取控制器 - 整合Selenium和Requests"""
    
    def __init__(self, db_path: str = "data/prospectuses.db"):
        self.db = DatabaseManager(db_path)
        self.selenium_auth = None
        self.requests_scraper = None
        self.auth_package = None
        self.codes_to_process = []
        
    def initialize(self) -> bool:
        """初始化爬取器"""
        try:
            # 连接数据库
            self.db.connect()
            self.db.create_table()
            logger.info("✅ 数据库初始化完成")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            return False
    
    def get_codes_and_auth(self, bond_names: List[str], phone: str, password: str) -> Tuple[List[str], Optional[Dict]]:
        """
        阶段1：使用Selenium获取债券代码和认证包
        
        Args:
            bond_names: 债券名称列表
            phone: 手机号
            password: 密码
            
        Returns:
            Tuple[List[str], Optional[Dict]]: (债券代码列表, 认证包)
        """
        try:
            logger.info("=" * 60)
            logger.info("阶段1：Selenium认证和代码获取")
            logger.info("=" * 60)
            
            # 创建Selenium认证管理器
            self.selenium_auth = SeleniumAuthManager(headless=False)
            
            # 执行完整流程
            codes, auth_package = self.selenium_auth.get_codes_and_auth(
                bond_names, phone, password
            )
            
            if codes and auth_package:
                self.codes_to_process = codes
                self.auth_package = auth_package
                logger.info(f"✅ 阶段1完成：获取到 {len(codes)} 个债券代码")
                return codes, auth_package
            else:
                logger.error("❌ 阶段1失败：未获取到代码或认证包")
                return [], None
                
        except Exception as e:
            logger.error(f"❌ 阶段1失败: {e}")
            return [], None
    
    def fetch_and_save_documents(self, bond_names: List[str] = None) -> bool:
        """
        阶段2：使用Requests爬取数据并保存到数据库
        
        Args:
            bond_names: 债券名称列表（可选，用于补充信息）
            
        Returns:
            bool: 是否成功
        """
        try:
            if not self.codes_to_process or not self.auth_package:
                logger.error("❌ 缺少债券代码或认证包，请先执行阶段1")
                return False
            
            logger.info("=" * 60)
            logger.info("阶段2：Requests数据爬取和保存")
            logger.info("=" * 60)
            
            # 创建Requests爬取器
            self.requests_scraper = RequestsDataScraper(self.auth_package)
            
            # 批量获取文档
            results = self.requests_scraper.fetch_multiple_bonds(
                self.codes_to_process, 
                bond_names
            )
            
            # 保存到数据库
            total_saved = 0
            for bond_code, documents in results.items():
                if not documents:
                    continue
                
                logger.info(f"保存债券 {bond_code} 的 {len(documents)} 个文档")
                
                for doc in documents:
                    try:
                        success = self.db.insert_document(doc)
                        if success:
                            total_saved += 1
                    except Exception as e:
                        logger.error(f"保存文档失败: {e}")
                        continue
            
            logger.info(f"✅ 阶段2完成：共保存 {total_saved} 个文档")
            return total_saved > 0
            
        except Exception as e:
            logger.error(f"❌ 阶段2失败: {e}")
            return False
    
    def process_bonds_complete(self, bond_names: List[str], phone: str, password: str) -> bool:
        """
        完整流程：获取代码和认证 -> 爬取数据 -> 保存到数据库
        
        Args:
            bond_names: 债券名称列表
            phone: 手机号
            password: 密码
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("🚀 开始完整混合爬取流程")
            
            # 阶段1：Selenium获取代码和认证
            codes, auth_package = self.get_codes_and_auth(bond_names, phone, password)
            if not codes or not auth_package:
                logger.error("❌ 阶段1失败，无法继续")
                return False
            
            # 阶段2：Requests爬取数据
            success = self.fetch_and_save_documents(bond_names)
            if not success:
                logger.error("❌ 阶段2失败")
                return False
            
            logger.info("🎉 完整流程执行成功！")
            return True
            
        except Exception as e:
            logger.error(f"❌ 完整流程失败: {e}")
            return False
        finally:
            self.cleanup()
    
    def get_database_stats(self) -> Dict:
        """获取数据库统计信息"""
        try:
            return self.db.get_statistics()
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.selenium_auth:
                self.selenium_auth.close()
            if self.db:
                self.db.close()
            logger.info("✅ 资源清理完成")
        except Exception as e:
            logger.warning(f"资源清理失败: {e}")


def test_hybrid_scraper():
    """测试混合爬取器"""
    try:
        # 测试数据
        test_bonds = ["21北京城投债01", "22上海城投债02"]
        test_phone = "15390314229"  # 请替换为真实手机号
        test_password = ""  # 请设置密码
        
        # 创建混合爬取器
        scraper = HybridScraper()
        
        # 初始化
        if not scraper.initialize():
            logger.error("初始化失败")
            return
        
        # 执行完整流程
        success = scraper.process_bonds_complete(test_bonds, test_phone, test_password)
        
        if success:
            # 显示统计信息
            stats = scraper.get_database_stats()
            logger.info(f"数据库统计: {stats}")
        else:
            logger.error("测试失败")
            
    except Exception as e:
        logger.error(f"测试失败: {e}")


if __name__ == "__main__":
    test_hybrid_scraper()
