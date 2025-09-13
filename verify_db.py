# E:\BaiduSyncdisk\数据库\1-城投公司\QYYJTScraper\verify_db.py

import sqlite3
import os

# --- 配置 ---
# 数据库文件名，必须与 src/config.py 中的 DATABASE_NAME 一致
DATABASE_NAME = "qyyjt_data.db"
# 要查询的表名
TABLE_NAME = "announcements"
# 要显示的行数
ROW_LIMIT = 20


def check_database():
    """连接到数据库并打印表中的前几行数据，用于快速验证。"""
    
    # 1. 检查数据库文件是否存在
    if not os.path.exists(DATABASE_NAME):
        print(f"错误: 数据库文件 '{DATABASE_NAME}' 不存在。")
        print("请先运行主爬虫程序 (python -m src.main) 来创建和填充数据库。")
        return

    print(f"--- 正在查询数据库: {DATABASE_NAME}, 表: {TABLE_NAME} ---")

    try:
        # 2. 连接到数据库 (使用 with 语句确保自动关闭)
        with sqlite3.connect(DATABASE_NAME) as conn:
            # 创建一个可以按列名访问数据的 row factory
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 3. 构造并执行查询
            query = f"SELECT * FROM {TABLE_NAME} LIMIT {ROW_LIMIT}"
            print(f"执行查询: {query}\n")
            cursor.execute(query)
            
            rows = cursor.fetchall()

            # 4. 打印结果
            if not rows:
                print(f"表 '{TABLE_NAME}' 中没有数据。")
            else:
                print(f"成功找到 {len(rows)} 条记录。显示如下：\n")
                
                # 打印每一行的数据
                for i, row in enumerate(rows):
                    print(f"----- 记录 {i+1} -----")
                    # 通过列名访问，更清晰
                    print(f"  id: {row['id']}")
                    print(f"  search_term: {row['search_term']}")
                    print(f"  bond_name: {row['bond_name']}")
                    print(f"  bond_code: {row['bond_code']}")
                    print(f"  announcement_title: {row['announcement_title']}")
                    print(f"  publish_date: {row['publish_date']}")
                    print(f"  file_size: {row['file_size']}")
                    print(f"  file_url: {row['file_url']}")
                    print(f"  scraped_at: {row['scraped_at']}")
                    print("-" * 20 + "\n")
        
        print(f"--- 查询完毕 ---")

    except sqlite3.Error as e:
        # 捕获可能的数据库错误
        print(f"访问数据库时发生错误: {e}")

if __name__ == "__main__":
    check_database()
