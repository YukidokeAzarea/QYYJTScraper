import sqlite3
import datetime
from . import config

def init_db():
    """初始化数据库，创建表（如果表不存在）。"""
    with sqlite3.connect(config.DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_term TEXT NOT NULL,
                bond_name TEXT,
                bond_code TEXT,
                announcement_title TEXT NOT NULL,
                file_url TEXT NOT NULL UNIQUE,
                file_size TEXT,
                publish_date TEXT,
                scraped_at TIMESTAMP NOT NULL
            )
        ''')
        print("数据库初始化完成。")

def get_scraped_bonds() -> set:
    """
    从数据库中获取所有已经爬取过的债券简称 (search_term)。
    :return: 一个包含所有已爬取债券简称的集合 (set)，用于快速查找。
    """
    scraped_bonds = set()
    try:
        with sqlite3.connect(config.DATABASE_NAME) as conn:
            cursor = conn.cursor()
            # 查询所有不重复的 search_term
            cursor.execute('SELECT DISTINCT search_term FROM announcements')
            results = cursor.fetchall()
            # 将结果 (元组) 转换为集合中的字符串
            scraped_bonds = {row[0] for row in results}
            if scraped_bonds:
                print(f"数据库中已存在 {len(scraped_bonds)} 个债券的数据。")
    except sqlite3.OperationalError:
        # 如果表还不存在，会报错，这时返回空集合即可
        print("数据库或表不存在，将从头开始爬取。")
    return scraped_bonds


def save_announcements(search_term: str, bond_code: str, bond_name: str, announcements_data: list):
    """
    将公告数据列表存入数据库。
    :param search_term: 搜索时使用的关键词
    :param bond_code: 债券的唯一代码
    :param bond_name: 债券名称
    :param announcements_data: 从API获取的公告数据列表
    """
    saved_count = 0
    with sqlite3.connect(config.DATABASE_NAME) as conn:
        cursor = conn.cursor()
        for item in announcements_data:
            title = item.get('title')
            publish_date = item.get('date')
            files = item.get('file', [])
            
            if not files:
                continue

            for file_info in files:
                file_url = file_info.get('fileUrl')
                file_size = file_info.get('fileSize')
                
                if not file_url:
                    continue
                
                try:
                    cursor.execute('''
                        INSERT INTO announcements (search_term, bond_name, bond_code, announcement_title, file_url, file_size, publish_date, scraped_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (search_term, bond_name, bond_code, title, file_url, file_size, publish_date, datetime.datetime.now()))
                    saved_count += 1
                except sqlite3.IntegrityError:
                    # 如果 file_url 已经存在 (因为设置了 UNIQUE)，则忽略
                    # print(f"文件链接已存在，跳过: {file_url}") # 在批量模式下，这个日志太频繁，可以注释掉
                    pass

        conn.commit()

    if saved_count > 0:
        print(f"成功保存 {saved_count} 条新的公告信息到数据库。")
    else:
        print("没有新的公告信息被保存（可能所有公告都已存在）。")
