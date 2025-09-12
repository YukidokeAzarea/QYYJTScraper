# E:\BaiduSyncdisk\数据库\1-城投公司\QYYJTScraper\src\main.py

import json
import time
import random
import pandas as pd
from wakepy import keep # [新增] 导入防休眠库
from . import login_handler, scraper, database, config

def load_accounts():
    """从JSON文件中加载账号池。"""
    try:
        # [改动] 使用 config.ACCOUNTS_FILE_PATH 来保持一致性
        with open(config.ACCOUNTS_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            accounts = data.get('accounts', [])
            if not accounts:
                print(f"错误: 在 {config.ACCOUNTS_FILE_PATH} 中未找到任何账号。")
                return None
            print(f"成功加载 {len(accounts)} 个账号。")
            return accounts
    except FileNotFoundError:
        print(f"错误: 账号文件未找到 -> {config.ACCOUNTS_FILE_PATH}")
        return None
    except json.JSONDecodeError:
        print(f"错误: 账号文件 {config.ACCOUNTS_FILE_PATH} 格式不正确。")
        return None

def load_bonds_list():
    """从Excel文件中加载待爬取的债券列表。"""
    try:
        # [改动] 使用 config.BONDS_LIST_PATH 来保持一致性
        df = pd.read_excel(config.BONDS_LIST_PATH, engine='openpyxl')
        if config.BONDS_LIST_COLUMN_NAME not in df.columns:
            print(f"错误: Excel文件中找不到名为 '{config.BONDS_LIST_COLUMN_NAME}' 的列。")
            return None
        
        bonds = df[config.BONDS_LIST_COLUMN_NAME].dropna().unique().tolist()
        print(f"成功从Excel加载 {len(bonds)} 个唯一的债券简称。")
        return bonds
    except FileNotFoundError:
        print(f"错误: 债券列表文件未找到 -> {config.BONDS_LIST_PATH}")
        return None
    except Exception as e:
        print(f"读取Excel文件时发生错误: {e}")
        return None

def run_scraper_with_account_pool():
    """
    [优化版] 使用账号池执行爬虫，实现会话复用、防系统休眠。
    """
    # [新增] 使用 with 语句块来包裹整个爬虫流程，确保在运行时系统不会休眠
    # keep_screen_awake=False 表示只阻止系统睡眠，不阻止屏幕关闭，更节能。
    with keep.awake(keep_screen_awake=False):
        print("\n" + "*"*25)
        print("--- [系统] 防休眠模式已激活 ---")
        print("爬虫运行期间，计算机将不会进入睡眠状态。")
        print("*"*25 + "\n")
        
        database.init_db()

        accounts = load_accounts()
        all_bonds_from_excel = load_bonds_list()

        if not accounts or not all_bonds_from_excel:
            print("缺少账号或债券列表，程序终止。")
            return

        scraped_bonds_set = database.get_scraped_bonds()
        if scraped_bonds_set:
            original_count = len(all_bonds_from_excel)
            bonds_to_scrape = [b for b in all_bonds_from_excel if b not in scraped_bonds_set]
            skipped_count = original_count - len(bonds_to_scrape)
            print(f"\n[断点续传] 已跳过 {skipped_count} 个已爬取过的债券。")
        else:
            bonds_to_scrape = all_bonds_from_excel

        if config.TEST_MODE:
            print("\n" + "*"*25)
            print("!!!  警告: 测试模式已开启  !!!")
            print(f"!!!  仅处理前 {config.TEST_MODE_BOND_COUNT} 个任务  !!!")
            print("*"*25 + "\n")
            bonds_to_scrape = bonds_to_scrape[:config.TEST_MODE_BOND_COUNT]

        if not bonds_to_scrape:
            print("所有在列表中的债券均已爬取完毕。程序结束。")
            return

        # --- 状态管理变量 ---
        active_accounts = list(accounts)
        bond_index = 0
        account_index = 0
        requests_this_account = 0
        total_bonds = len(bonds_to_scrape)
        current_scraper = None

        # 主循环
        while bond_index < total_bonds and active_accounts:
            try:
                # --- 检查并获取有效会话 ---
                if current_scraper is None:
                    current_account = active_accounts[account_index]
                    print("\n" + "~"*50)
                    print(f"当前无有效会话。正在使用账号 {current_account['phone']} ({account_index + 1}/{len(active_accounts)}) 登录...")
                    
                    auth_session = login_handler.get_authenticated_session(
                        phone=current_account['phone'],
                        password=current_account['password'],
                        search_term=bonds_to_scrape[bond_index] 
                    )

                    if auth_session:
                        current_scraper = scraper.Scraper(auth_session)
                        requests_this_account = 0
                        print("登录成功，已创建新的 Scraper 实例。")
                        print("~"*50 + "\n")
                    else:
                        print(f"账号 {current_account['phone']} 登录失败，将从池中移除。")
                        active_accounts.pop(account_index)
                        if active_accounts:
                            account_index %= len(active_accounts)
                        continue

                # --- 使用已有的会话进行爬取 ---
                current_bond = bonds_to_scrape[bond_index]
                print("\n" + "="*50)
                print(f"进度: [{bond_index + 1}/{total_bonds}] | 账号: {active_accounts[account_index]['phone']} | 此账号请求数: {requests_this_account}")
                print(f"目标: '{current_bond}'")
                print("="*50)

                bond_details = current_scraper.search_bond(current_bond)
                if not bond_details:
                    print(f"未能通过API找到 '{current_bond}' 的信息，跳过此债券。")
                    bond_index += 1
                    continue
                
                announcements = current_scraper.get_announcements(bond_details["code"])
                if announcements is None:
                    print(f"获取 '{current_bond}' 的公告失败，跳过此债券。")
                    bond_index += 1
                    continue

                database.save_announcements(current_bond, bond_details["code"], bond_details["name"], announcements)

                # --- 任务成功后的处理 ---
                bond_index += 1
                requests_this_account += 1

                if requests_this_account >= config.REQUESTS_PER_ACCOUNT:
                    print(f"\n--- 账号 {active_accounts[account_index]['phone']} 已达到 {config.REQUESTS_PER_ACCOUNT} 次请求上限，准备切换。 ---")
                    current_scraper = None
                    account_index = (account_index + 1) % len(active_accounts)
                    time.sleep(5)
                else:
                    sleep_duration = random.uniform(*config.DELAY_BETWEEN_BONDS)
                    print(f"任务完成，暂停 {sleep_duration:.2f} 秒...")
                    time.sleep(sleep_duration)

            except scraper.RateLimitException as e:
                print(f"\n!!!!!!!!!! 警告 !!!!!!!!!!")
                print(f"账号 {active_accounts[account_index]['phone']} 已被服务器限制: {e}")
                print(f"将此账号从当前任务池中移除。")
                print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
                
                current_scraper = None
                active_accounts.pop(account_index)
                
                if active_accounts:
                    account_index %= len(active_accounts)
                    print(f"剩余 {len(active_accounts)} 个可用账号。将用下一个账号重试 '{bonds_to_scrape[bond_index]}'")
                else:
                    print("所有账号均已失效！")
                
                time.sleep(10)

            except Exception as e:
                print(f"\n处理 '{bonds_to_scrape[bond_index]}' 时发生未知严重错误: {e}")
                print("为防止卡死，将跳过此债券并继续。")
                current_scraper = None
                bond_index += 1
                time.sleep(5)

        print("\n\n" + "#"*60)
        print("爬取任务结束。")
        if bond_index == total_bonds:
            print("恭喜！所有待处理债券已成功处理完毕。")
        else:
            print(f"任务中断。已处理 {bond_index} / {total_bonds} 个债券。")
            if not active_accounts:
                print("原因：所有账号均已耗尽或被限制。")
        print("#"*60)

    # [新增] with 语句块结束，程序会自动恢复系统的正常休眠策略
    print("\n--- [系统] 防休眠模式已解除 ---")


if __name__ == '__main__':
    run_scraper_with_account_pool()
