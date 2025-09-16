# 文件名: query_announcements.py

import sqlite3
import argparse
import json

def search_database(db_path, table_name, keyword, output_file):
    """
    在SQLite数据库中搜索公告，并将匹配的记录（URL、标题、日期）写入一个JSON文件。
    """
    conn = None
    tasks_to_export = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 我们需要 title 和 publish_date 来构建文件名，所以一并查询出来
        query = f"SELECT announcement_title, file_url, publish_date FROM {table_name} WHERE announcement_title LIKE ?"
        
        print(f"数据库: {db_path}, 数据表: {table_name}")
        print(f"正在查询标题包含 '{keyword}' 的公告...")

        cursor.execute(query, (f'%{keyword}%',))
        results = cursor.fetchall()

        if not results:
            print("查询完毕，没有找到匹配的记录。")
            return

        print(f"\n查询到 {len(results)} 条匹配记录:")
        for row in results:
            title, url, pub_date = row
            # 将每条记录打包成一个字典对象
            task_item = {
                "announcement_title": title,
                "file_url": url,
                "publish_date": pub_date
            }
            tasks_to_export.append(task_item)
            print(f"  - 待导出: {title}")
        
        # 将包含所有任务的列表写入JSON文件
        with open(output_file, 'w', encoding='utf-8') as f:
            # indent=4 让JSON文件格式更美观，易于阅读
            json.dump(tasks_to_export, f, ensure_ascii=False, indent=4)
        
        print(f"\n成功将 {len(tasks_to_export)} 个下载任务导出到文件: {output_file}")

    except sqlite3.Error as e:
        print(f"数据库操作失败: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="从SQLite数据库查询公告信息并导出为JSON任务文件。")
    parser.add_argument("keyword", type=str, help="要搜索的公告标题关键字, 例如 '年度报告'。")
    parser.add_argument("--db", type=str, default="qyyjt_data.db", help="SQLite数据库文件路径。")
    parser.add_argument("--table", type=str, default="announcements", help="数据表名称。")
    # 输出文件名默认为 .json 后缀
    parser.add_argument("--output", type=str, default="output/download_tasks.json", help="输出JSON任务文件的文件名。")
    
    args = parser.parse_args()

    search_database(args.db, args.table, args.keyword, args.output)
