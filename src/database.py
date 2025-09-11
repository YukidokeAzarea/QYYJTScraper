"""
数据库操作模块
负责创建表、插入数据、查询数据等数据库操作
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "data/prospectuses.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.connection = None
    
    def connect(self):
        """连接到数据库"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # 使结果可以通过列名访问
            logger.info(f"成功连接到数据库: {self.db_path}")
        except Exception as e:
            logger.error(f"连接数据库失败: {e}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")
    
    def create_table(self):
        """
        创建债券文档表
        
        表结构:
        - id: 唯一ID (主键，自增)
        - bond_short_name: 债券简称
        - document_title: 文档标题
        - document_type: 文档类型
        - download_url: 下载链接 (唯一)
        - file_size: 文件大小
        - publication_date: 发布日期
        - scraped_at: 抓取时间
        """
        try:
            cursor = self.connection.cursor()
            
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS bond_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bond_short_name TEXT NOT NULL,
                document_title TEXT NOT NULL,
                document_type TEXT,
                download_url TEXT UNIQUE,
                file_size TEXT,
                publication_date TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            
            cursor.execute(create_table_sql)
            self.connection.commit()
            
            # 创建索引以提高查询性能
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bond_short_name ON bond_documents(bond_short_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_type ON bond_documents(document_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_publication_date ON bond_documents(publication_date)")
            
            logger.info("数据库表创建成功")
            
        except Exception as e:
            logger.error(f"创建数据库表失败: {e}")
            raise
    
    def insert_document(self, document_info: Dict) -> bool:
        """
        插入文档信息到数据库
        
        Args:
            document_info: 包含文档信息的字典，应包含以下键：
                - bond_short_name: 债券简称
                - document_title: 文档标题
                - document_type: 文档类型
                - download_url: 下载链接
                - file_size: 文件大小
                - publication_date: 发布日期
        
        Returns:
            bool: 插入是否成功
        """
        try:
            cursor = self.connection.cursor()
            
            # 检查是否已存在相同的下载链接
            cursor.execute(
                "SELECT id FROM bond_documents WHERE download_url = ?",
                (document_info.get('download_url'),)
            )
            
            if cursor.fetchone():
                logger.warning(f"文档已存在，跳过插入: {document_info.get('download_url')}")
                return False
            
            # 插入新记录
            insert_sql = """
            INSERT INTO bond_documents 
            (bond_short_name, document_title, document_type, download_url, file_size, publication_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            
            cursor.execute(insert_sql, (
                document_info.get('bond_short_name'),
                document_info.get('document_title'),
                document_info.get('document_type'),
                document_info.get('download_url'),
                document_info.get('file_size'),
                document_info.get('publication_date')
            ))
            
            self.connection.commit()
            logger.info(f"成功插入文档: {document_info.get('document_title')}")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.warning(f"文档已存在，跳过插入: {e}")
            return False
        except Exception as e:
            logger.error(f"插入文档失败: {e}")
            return False
    
    def insert_documents_batch(self, documents: List[Dict]) -> int:
        """
        批量插入文档信息
        
        Args:
            documents: 文档信息列表
        
        Returns:
            int: 成功插入的文档数量
        """
        success_count = 0
        
        for document in documents:
            if self.insert_document(document):
                success_count += 1
        
        logger.info(f"批量插入完成，成功插入 {success_count}/{len(documents)} 个文档")
        return success_count
    
    def get_documents_by_bond(self, bond_short_name: str) -> List[Dict]:
        """
        根据债券简称查询文档
        
        Args:
            bond_short_name: 债券简称
        
        Returns:
            List[Dict]: 文档信息列表
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT * FROM bond_documents WHERE bond_short_name = ? ORDER BY publication_date DESC",
                (bond_short_name,)
            )
            
            rows = cursor.fetchall()
            documents = []
            
            for row in rows:
                documents.append({
                    'id': row['id'],
                    'bond_short_name': row['bond_short_name'],
                    'document_title': row['document_title'],
                    'document_type': row['document_type'],
                    'download_url': row['download_url'],
                    'file_size': row['file_size'],
                    'publication_date': row['publication_date'],
                    'scraped_at': row['scraped_at']
                })
            
            logger.info(f"查询到 {len(documents)} 个文档: {bond_short_name}")
            return documents
            
        except Exception as e:
            logger.error(f"查询文档失败: {e}")
            return []
    
    def get_all_documents(self) -> List[Dict]:
        """
        获取所有文档
        
        Returns:
            List[Dict]: 所有文档信息列表
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM bond_documents ORDER BY scraped_at DESC")
            
            rows = cursor.fetchall()
            documents = []
            
            for row in rows:
                documents.append({
                    'id': row['id'],
                    'bond_short_name': row['bond_short_name'],
                    'document_title': row['document_title'],
                    'document_type': row['document_type'],
                    'download_url': row['download_url'],
                    'file_size': row['file_size'],
                    'publication_date': row['publication_date'],
                    'scraped_at': row['scraped_at']
                })
            
            logger.info(f"查询到 {len(documents)} 个文档")
            return documents
            
        except Exception as e:
            logger.error(f"查询所有文档失败: {e}")
            return []
    
    def get_documents_by_type(self, document_type: str) -> List[Dict]:
        """
        根据文档类型查询文档
        
        Args:
            document_type: 文档类型
            
        Returns:
            List[Dict]: 文档信息列表
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM bond_documents 
                WHERE document_type = ? 
                ORDER BY scraped_at DESC
            """, (document_type,))
            
            rows = cursor.fetchall()
            documents = []
            
            for row in rows:
                documents.append(dict(row))
            
            logger.info(f"按类型 '{document_type}' 查询到 {len(documents)} 个文档")
            return documents
            
        except Exception as e:
            logger.error(f"按类型查询文档失败: {e}")
            return []
    
    def get_documents_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """
        根据日期范围查询文档
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            List[Dict]: 文档信息列表
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM bond_documents 
                WHERE publication_date BETWEEN ? AND ? 
                ORDER BY publication_date DESC
            """, (start_date, end_date))
            
            rows = cursor.fetchall()
            documents = []
            
            for row in rows:
                documents.append(dict(row))
            
            logger.info(f"按日期范围 '{start_date}' 到 '{end_date}' 查询到 {len(documents)} 个文档")
            return documents
            
        except Exception as e:
            logger.error(f"按日期范围查询文档失败: {e}")
            return []
    
    def get_existing_bonds(self) -> set:
        """
        获取数据库中已存在的债券简称集合
        
        Returns:
            set: 已存在的债券简称集合
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT DISTINCT bond_short_name FROM bond_documents")
            
            rows = cursor.fetchall()
            existing_bonds = {row['bond_short_name'] for row in rows}
            
            logger.info(f"数据库中已存在 {len(existing_bonds)} 个债券的数据")
            return existing_bonds
            
        except Exception as e:
            logger.error(f"查询已存在债券失败: {e}")
            return set()
    
    def get_existing_bond_short_names(self) -> set:
        """
        获取数据库中已存在的债券简称（提取简称部分）
        
        Returns:
            set: 已存在的债券简称集合
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT DISTINCT bond_short_name FROM bond_documents")
            
            rows = cursor.fetchall()
            existing_bonds = set()
            
            for row in rows:
                bond_name = row['bond_short_name']
                # 提取简称部分（去掉括号和代码）
                if '(' in bond_name:
                    short_name = bond_name.split('(')[0].strip()
                else:
                    short_name = bond_name.strip()
                existing_bonds.add(short_name)
            
            logger.info(f"数据库中已存在 {len(existing_bonds)} 个债券的简称")
            return existing_bonds
            
        except Exception as e:
            logger.error(f"查询已存在债券简称失败: {e}")
            return set()
    
    def get_bond_document_count(self, bond_short_name: str) -> int:
        """
        获取指定债券的文档数量
        
        Args:
            bond_short_name: 债券简称
            
        Returns:
            int: 文档数量
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) as count FROM bond_documents WHERE bond_short_name = ?",
                (bond_short_name,)
            )
            
            result = cursor.fetchone()
            count = result['count'] if result else 0
            
            return count
            
        except Exception as e:
            logger.error(f"查询债券文档数量失败: {e}")
            return 0
    
    def delete_documents_by_bond(self, bond_code: str) -> bool:
        """
        根据债券代码删除文档
        
        Args:
            bond_code: 债券代码
            
        Returns:
            bool: 删除是否成功
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM bond_documents WHERE bond_code = ?", (bond_code,))
            deleted_count = cursor.rowcount
            self.connection.commit()
            
            logger.info(f"删除债券 '{bond_code}' 的 {deleted_count} 个文档")
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"删除债券文档失败: {e}")
            return False

    def get_statistics(self) -> Dict:
        """
        获取数据库统计信息
        
        Returns:
            Dict: 统计信息
        """
        try:
            cursor = self.connection.cursor()
            
            # 总文档数
            cursor.execute("SELECT COUNT(*) as total FROM bond_documents")
            total_documents = cursor.fetchone()['total']
            
            # 总债券数
            cursor.execute("SELECT COUNT(DISTINCT bond_short_name) as total FROM bond_documents")
            total_bonds = cursor.fetchone()['total']
            
            # 按债券简称分组统计
            cursor.execute("""
                SELECT bond_short_name, COUNT(*) as count 
                FROM bond_documents 
                GROUP BY bond_short_name 
                ORDER BY count DESC
            """)
            bond_stats = cursor.fetchall()
            
            # 按文档类型分组统计
            cursor.execute("""
                SELECT document_type, COUNT(*) as count 
                FROM bond_documents 
                GROUP BY document_type 
                ORDER BY count DESC
            """)
            type_stats = cursor.fetchall()
            
            # 日期范围
            cursor.execute("""
                SELECT MIN(publication_date) as min_date, MAX(publication_date) as max_date 
                FROM bond_documents 
                WHERE publication_date IS NOT NULL AND publication_date != ''
            """)
            date_range = cursor.fetchone()
            
            return {
                'total_documents': total_documents,
                'total_bonds': total_bonds,
                'bond_statistics': [dict(row) for row in bond_stats],
                'document_types': {row['document_type']: row['count'] for row in type_stats},
                'date_range': {
                    'start': date_range['min_date'] if date_range['min_date'] else 'N/A',
                    'end': date_range['max_date'] if date_range['max_date'] else 'N/A'
                }
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
