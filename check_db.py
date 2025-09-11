#!/usr/bin/env python3
"""
数据库检查脚本
检查数据库中的数据和统计信息
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.append(str(Path(__file__).parent / "src"))

from src.database import DatabaseManager
from loguru import logger

def check_database():
    """检查数据库状态"""
    try:
        # 连接数据库
        db = DatabaseManager("data/prospectuses.db")
        db.connect()
        
        # 获取统计信息
        stats = db.get_statistics()
        
        print("=" * 60)
        print("📊 数据库统计信息")
        print("=" * 60)
        print(f"总文档数: {stats.get('total_documents', 0)}")
        print(f"总债券数: {stats.get('total_bonds', 0)}")
        
        # 显示债券统计
        bond_stats = stats.get('bond_statistics', [])
        if bond_stats:
            print("\n📈 债券文档统计 (前10个):")
            for i, bond in enumerate(bond_stats[:10]):
                print(f"  {i+1}. {bond['bond_short_name']}: {bond['count']} 个文档")
        
        # 显示文档类型统计
        doc_types = stats.get('document_types', {})
        if doc_types:
            print("\n📋 文档类型统计:")
            for doc_type, count in doc_types.items():
                print(f"  - {doc_type}: {count} 个")
        
        # 显示日期范围
        date_range = stats.get('date_range', {})
        if date_range:
            print(f"\n📅 日期范围: {date_range.get('start', 'N/A')} 到 {date_range.get('end', 'N/A')}")
        
        # 获取所有文档
        all_docs = db.get_all_documents()
        if all_docs:
            print(f"\n📄 最近5个文档:")
            for i, doc in enumerate(all_docs[:5]):
                print(f"  {i+1}. {doc['document_title']} ({doc['bond_short_name']})")
        
        db.close()
        
        if stats.get('total_documents', 0) > 0:
            print("\n✅ 数据库中有数据！")
            return True
        else:
            print("\n⚠️ 数据库中暂无数据")
            return False
            
    except Exception as e:
        print(f"❌ 检查数据库失败: {e}")
        return False

if __name__ == "__main__":
    check_database()