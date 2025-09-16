# 文件名: db_to_excel.py

import sqlite3
import pandas as pd
import argparse
import os

def export_db_to_excel(db_path, output_excel_path):
    """
    读取一个SQLite数据库，并将其所有表导出到一个Excel文件的不同工作表中。

    :param db_path: SQLite数据库文件路径。
    :param output_excel_path: 输出的Excel文件名。
    """
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件 '{db_path}' 未找到。")
        return

    print(f"正在连接数据库: {db_path}")
    conn = None
    try:
        # 1. 连接到SQLite数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 2. 获取数据库中所有表的名称
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        table_names = [table[0] for table in cursor.fetchall()]

        if not table_names:
            print("数据库中没有找到任何数据表。")
            return

        print(f"在数据库中找到以下数据表: {', '.join(table_names)}")

        # 3. 创建一个Excel写入器
        with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
            print(f"准备将数据写入到: {output_excel_path}")
            
            # 4. 遍历每个表，读取数据并写入到Excel的不同工作表
            for table_name in table_names:
                print(f"  - 正在导出表 '{table_name}'...")
                # 构建查询语句以选择表中的所有数据
                query = f"SELECT * FROM {table_name}"
                
                # 使用pandas直接从SQL查询结果创建DataFrame
                df = pd.read_sql_query(query, conn)
                
                # 将DataFrame写入到Excel的一个工作表（sheet）中
                # sheet_name被设置为表名
                # index=False表示不将pandas的行索引写入Excel文件
                df.to_excel(writer, sheet_name=table_name, index=False)
                print(f"    '{table_name}' 表成功导出，包含 {len(df)} 行数据。")

        print(f"\n操作完成！所有数据已成功导出到: {output_excel_path}")

    except sqlite3.Error as e:
        print(f"数据库操作失败: {e}")
    except Exception as e:
        print(f"发生未知错误: {e}")
    finally:
        if conn:
            conn.close()
            # print("数据库连接已关闭。")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="将SQLite数据库中的所有表导出到一个Excel文件中。")
    
    # 必填参数：数据库文件路径
    parser.add_argument("db_path", type=str, help="要转换的SQLite数据库文件路径。例如: qyyjt_data.db")
    
    # 可选参数：输出的Excel文件名
    parser.add_argument("-o", "--output", type=str, help="输出的Excel文件名。如果未提供，将自动根据数据库名生成。")
    
    args = parser.parse_args()
    
    # 如果用户没有指定输出文件名，我们就自动生成一个
    if args.output:
        output_file = args.output
    else:
        # 获取数据库文件名（不含扩展名），并添加 .xlsx 后缀
        base_name = os.path.splitext(os.path.basename(args.db_path))[0]
        output_file = f"output/{base_name}_export.xlsx"
        
    export_db_to_excel(args.db_path, output_file)
