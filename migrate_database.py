#!/usr/bin/env python3
"""
数据库迁移脚本
用于更新现有数据库的表结构，添加新字段
"""

import sqlite3
import os
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.append(str(Path(__file__).parent / "src"))

from src.database import DatabaseManager
from loguru import logger

def migrate_database():
    """迁移数据库表结构"""
    db_path = "data/prospectuses.db"
    
    if not os.path.exists(db_path):
        logger.info("数据库文件不存在，将创建新数据库")
        db = DatabaseManager(db_path)
        db.connect()
        db.create_table()
        db.close()
        logger.info("✅ 新数据库创建完成")
        return True
    
    try:
        # 连接现有数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查表结构
        cursor.execute("PRAGMA table_info(bond_documents)")
        columns = cursor.fetchall()
        existing_columns = [col[1] for col in columns]
        
        logger.info(f"现有表字段: {existing_columns}")
        
        # 需要添加的新字段
        new_columns = {
            'bond_code': 'TEXT',
            'bond_full_name': 'TEXT', 
            'province': 'TEXT',
            'city': 'TEXT'
        }
        
        # 添加缺失的字段
        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                try:
                    alter_sql = f"ALTER TABLE bond_documents ADD COLUMN {column_name} {column_type}"
                    cursor.execute(alter_sql)
                    logger.info(f"✅ 添加字段: {column_name}")
                except sqlite3.Error as e:
                    logger.warning(f"添加字段 {column_name} 失败: {e}")
        
        conn.commit()
        
        # 验证表结构
        cursor.execute("PRAGMA table_info(bond_documents)")
        columns = cursor.fetchall()
        updated_columns = [col[1] for col in columns]
        
        logger.info(f"更新后的表字段: {updated_columns}")
        
        # 检查数据
        cursor.execute("SELECT COUNT(*) FROM bond_documents")
        count = cursor.fetchone()[0]
        logger.info(f"数据库中现有记录数: {count}")
        
        conn.close()
        logger.info("✅ 数据库迁移完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        return False

def test_database_operations():
    """测试数据库操作"""
    try:
        db = DatabaseManager("data/prospectuses.db")
        db.connect()
        db.create_table()  # 确保表结构正确
        
        # 测试插入
        test_doc = {
            'bond_code': 'TEST001',
            'bond_short_name': '测试债券',
            'bond_full_name': '测试债券全称',
            'document_title': '测试文档标题',
            'document_type': '募集说明书',
            'download_url': 'http://test.com/doc.pdf',
            'file_size': '1MB',
            'publication_date': '2024-01-01',
            'province': '北京市',
            'city': '北京市'
        }
        
        success = db.insert_document(test_doc)
        if success:
            logger.info("✅ 测试插入成功")
            
            # 测试查询
            docs = db.get_documents_by_bond('测试债券')
            logger.info(f"✅ 测试查询成功，找到 {len(docs)} 个文档")
            
            # 清理测试数据
            cursor = db.connection.cursor()
            cursor.execute("DELETE FROM bond_documents WHERE bond_short_name = '测试债券'")
            db.connection.commit()
            logger.info("✅ 测试数据已清理")
        else:
            logger.error("❌ 测试插入失败")
            
        db.close()
        return success
        
    except Exception as e:
        logger.error(f"❌ 数据库测试失败: {e}")
        return False

if __name__ == "__main__":
    logger.info("开始数据库迁移...")
    
    # 执行迁移
    if migrate_database():
        logger.info("开始数据库操作测试...")
        if test_database_operations():
            logger.info("🎉 数据库迁移和测试完成！")
        else:
            logger.error("❌ 数据库测试失败")
    else:
        logger.error("❌ 数据库迁移失败")
