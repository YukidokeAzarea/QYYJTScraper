# 文件名: download_files.py

import requests
import os
import argparse
import json
import re

def sanitize_filename(filename):
    """移除文件名中的非法字符，并将多个空格替换为单个，使其更整洁"""
    # 移除Windows和Linux文件名中的非法字符
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", filename)
    # 将多个空格替换为单个
    sanitized = re.sub(r'\s+', ' ', sanitized)
    return sanitized.strip()

def download_from_task_file(task_file, save_dir):
    """
    从一个JSON任务文件中读取任务列表，并下载文件，同时生成结构化的文件名。
    """
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        print(f"创建目录: {save_dir}")

    if not os.path.exists(task_file):
        print(f"错误: 任务文件 '{task_file}' 不存在。请先运行查询脚本。")
        return

    with open(task_file, 'r', encoding='utf-8') as f:
        tasks = json.load(f)

    if not tasks:
        print(f"任务文件 '{task_file}' 为空，无需下载。")
        return

    print(f"准备从 '{task_file}' 下载 {len(tasks)} 个文件到 '{save_dir}' 目录...")

    for i, task in enumerate(tasks, 1):
        try:
            url = task['file_url']
            title = task['announcement_title']
            date_str = task['publish_date']
            
            # --- 核心逻辑：创建结构化文件名 ---
            # 1. 提取年份
            year = date_str[:4]
            
            # 2. 清理标题，并构建最终文件名
            # 格式: [年份]-[清理后的公告标题].pdf
            clean_title = sanitize_filename(title)
            new_filename = f"{year}-{clean_title}.pdf"
            
            save_path = os.path.join(save_dir, new_filename)

            if os.path.exists(save_path):
                print(f"({i}/{len(tasks)}) 文件已存在，跳过: {new_filename}")
                continue
            
            print(f"({i}/{len(tasks)}) 正在下载: {title}")
            print(f"    保存为: {new_filename}")

            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            with open(save_path, 'wb') as f_out:
                for chunk in response.iter_content(chunk_size=8192):
                    f_out.write(chunk)
            
            print(f"    成功保存到: {save_path}\n")

        except requests.exceptions.RequestException as e:
            print(f"    下载失败: {task.get('announcement_title', '未知任务')}, 错误: {e}\n")
        except Exception as e:
            print(f"    发生未知错误: {e}\n")
            
    print("所有下载任务完成。")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="根据JSON任务文件下载文件，并生成结构化文件名。")
    parser.add_argument("task_file", type=str, help="包含下载任务的JSON文件路径, 例如 'download_tasks.json'。")
    parser.add_argument("--save_dir", type=str, default="output/downloaded_reports", help="保存下载文件的目录。")

    args = parser.parse_args()

    download_from_task_file(args.task_file, args.save_dir)
