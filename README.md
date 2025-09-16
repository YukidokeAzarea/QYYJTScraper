# QYYJTScraper - 企业预警通债券公告爬虫

这是一个针对 **企业预警通 (qyyjt.cn)** 网站的 Python 爬虫项目，旨在自动化地抓取指定债券列表的所有相关公告信息，并将结果持久化存储到 SQLite 数据库中。

该爬虫通过模拟登录获取认证凭据，然后直接与后端 API 交互，实现了高效、稳定的数据采集。同时，还内置了多账号轮换、速率限制处理、断点续传等高级功能，非常适合进行批量数据采集任务。项目还附带了一套强大的数据处理工具，可以方便地将数据库导出为 Excel、查询特定公告并批量下载文件。

## 目录

- [主要功能](#主要功能)
- [项目结构](#项目结构)
- [环境准备与依赖安装](#环境准备与依赖安装)
- [配置指南](#配置指南)
  - [1. 配置账号池 (accounts.json)](#1-配置账号池-accountsjson)
  - [2. 配置待爬取列表 (bonds_list.xlsx)](#2-配置待爬取列表-bonds_listxlsx)
  - [3. (可选) 调整核心配置 (config.py)](#3-可选-调整核心配置-configpy)
- [如何运行爬虫](#如何运行爬虫)
- [数据分析与下载工具](#数据分析与下载工具)
  - [1. 导出数据库到 Excel (`db_to_excel.py`)](#1-导出数据库到-excel-db_to_excelpy)
  - [2. 查询公告并生成下载任务 (`query_db.py`)](#2-查询公告并生成下载任务-query_dbpy)
  - [3. 下载文件 (`download_files.py`)](#3-下载文件-download_filespy)
- [工作流程详解](#工作流程详解)
- [输出结果](#输出结果)
- [注意事项](#注意事项)

## 主要功能

- **自动化模拟登录**: 使用 Selenium 自动完成登录过程，获取必要的 API 访问令牌和 Cookie。
- **多账号池轮换**: 支持配置多个账号，当一个账号达到请求上限或被临时封禁时，程序会自动切换到下一个可用账号。
- **智能速率限制处理**: 能自动识别 API 返回的“请求过于频繁”错误，并将触发该错误的账号暂时移出任务池。
- **断点续传**: 在启动时会检查数据库，自动跳过已经爬取过的债券，避免重复工作。
- **分页数据抓取**: 自动处理公告列表的分页，抓取目标债券的全部历史公告。
- **数据持久化**: 将抓取到的公告信息存入本地 SQLite 数据库，方便后续分析。
- **便捷的数据导出与下载**:
  - 一键将数据库导出为 Excel 文件，便于数据预览和分享。
  - 支持按关键字查询公告，并批量下载相关文件。
  - 下载时自动根据年份和标题生成结构化文件名，便于整理归档。
- **高度可配置**: 核心参数（如请求延时、文件路径等）均可通过 `config.py` 文件进行调整。

## 项目结构

```
QYYJTScraper/
│
├── data/                     # 数据与配置文件目录
│   ├── accounts.json         # 【需手动创建】用于存放登录账号和密码
│   └── bonds_list.xlsx       # 【需手动创建】待爬取的债券简称列表
│
├── output/                   # 【Git忽略】所有生成的输出文件
│   ├── downloaded_reports/   # 示例：下载的文件存放地
│   ├── download_tasks.json   # 示例：查询生成的JSON任务
│   └── qyyjt_data_export.xlsx# 示例：导出的Excel文件
│
├── src/                      # 爬虫核心源代码目录
│   ├── __init__.py
│   ├── main.py               # 爬虫主程序入口
│   ├── config.py             # 核心配置文件
│   ├── login_handler.py      # 负责模拟登录与获取会话
│   ├── scraper.py            # 负责API请求和数据解析
│   └── database.py           # 负责数据库的初始化与操作
│
├── tools/                    # 辅助工具脚本目录
│   ├── db_to_excel.py        # 数据库转Excel工具
│   ├── query_db.py# 公告查询工具
│   └── download_files.py     # 文件下载工具
│
├── .gitignore                # Git忽略配置文件
└── README.md                 # 项目说明文档
```

## 环境准备与依赖安装

1.  **安装 Python**: 建议使用 Python 3.8 或更高版本。
2.  **安装 Chrome 浏览器**: 本项目使用 Selenium 驱动 Chrome 浏览器进行模拟登录。
3.  **安装依赖库**: 在项目根目录下，通过 pip 安装所有必要的库。

    ```bash
    pip install pandas openpyxl requests selenium webdriver-manager wakepy
    ```

## 配置指南

在运行爬虫之前，你需要进行以下三个步骤的配置。

### 1. 配置账号池 (accounts.json)

在 `data/` 目录下，手动创建一个名为 `accounts.json` 的文件。该文件用于存储一个或多个企业预警通的登录账号。

文件内容应遵循以下 JSON 格式：
```json
// 文件路径: QYYJTScraper/data/accounts.json
{
  "accounts": [
    {
      "phone": "你的手机号1",
      "password": "你的密码1"
    },
    {
      "phone": "你的手机号2",
      "password": "你的密码2"
    }
  ]
}
```
**提示**: 账号越多，爬虫的抗封禁能力越强。

### 2. 配置待爬取列表 (bonds_list.xlsx)

在 `data/` 目录下，手动创建一个名为 `bonds_list.xlsx` 的 Excel 文件。

-   文件中必须包含一个名为 **`债券简称`** 的列。
-   在该列下方，逐行填入你想要爬取的债券的简称。

| 债券简称         |
| ---------------- |
| 21沪世业MTN001   |
| 23蓉城建工SCP001 |
| 20大连德泰MTN001 |
| ...              |

爬虫会读取此列中的所有内容，并去除重复项和空值。

### 3. (可选) 调整核心配置 (config.py)

`src/config.py` 文件包含了爬虫的所有核心配置项，你可以根据需要进行修改。**大部分情况下，你只需要检查文件路径是否正确。**

```python
# src/config.py

# --- 基础配置 (通常需要检查) ---
# 数据库文件名 (会生成在项目根目录)
DATABASE_NAME = 'qyyjt_data.db' 
# 账号池文件路径
ACCOUNTS_FILE_PATH = 'data/accounts.json'
# 待爬取债券列表文件路径
BONDS_LIST_PATH = 'data/bonds_list.xlsx'
# Excel中包含债券名称的列名
BONDS_LIST_COLUMN_NAME = '债券简称'

# --- 性能与反爬配置 (可根据网络情况和风险承受能力调整) ---
REQUESTS_PER_ACCOUNT = 20
DELAY_BETWEEN_BONDS = (2, 5)
DELAY_BETWEEN_PAGES = (0.5, 1.5)

# --- 测试模式 ---
TEST_MODE = True
TEST_MODE_BOND_COUNT = 3
```

## 如何运行爬虫

1.  确保你已经完成了上述所有配置步骤。
2.  打开终端或命令行，切换到项目根目录 `QYYJTScraper/`。
3.  运行主程序 `main.py`。推荐使用模块化方式运行：

    ```bash
    python -m src.main
    ```

4.  程序启动后，你将看到日志输出：加载配置、初始化数据库、自动登录、爬取进度等。

## 数据分析与下载工具

本项目提供了一系列位于 `tools/` 目录下的辅助脚本，用于分析已爬取的数据和下载相关文件。所有工具的输出默认都会存放在 `output/` 目录下。

### 1. 导出数据库到 Excel (`db_to_excel.py`)

此工具可将整个 SQLite 数据库导出为一个 Excel 文件，每个数据表对应一个工作表，方便进行数据预览和分析。

**使用方法:**
```bash
# 将 qyyjt_data.db 导出为 output/qyyjt_data_export.xlsx
python tools/db_to_excel.py qyyjt_data.db
```

### 2. 查询公告并生成下载任务 (`query_db.py`)

根据关键字查询数据库中的公告，并将结果（包含URL、标题、日期等信息）保存为一个 `JSON` 任务文件。

**使用方法:**
```bash
# 查询所有“年度报告”并生成任务文件 output/download_tasks.json
python tools/query_db.py "年度报告" --db qyyjt_data.db
```

### 3. 下载文件 (`download_files.py`)

读取上一步生成的 `JSON` 任务文件，批量下载公告，并根据年份和标题自动生成结构化的文件名。

**使用方法:**
```bash
# 从任务文件下载，并保存到 output/年度报告 文件夹
python tools/download_files.py output/download_tasks.json --save_dir output/年度报告
```

## 工作流程详解

1.  **初始化**: `main.py` 启动，加载 `data/` 目录下的配置文件，并初始化数据库。
2.  **断点检查**: 查询数据库，获取已爬取过的债券简称，实现断点续传。
3.  **获取会话**: 调用 `login_handler.py`，通过 Selenium 模拟登录获取认证信息。
4.  **创建 Scraper 实例**: 使用认证信息创建 `scraper.Scraper` 实例，用于后续 API 请求。
5.  **循环处理任务**: 遍历待爬取列表，调用 `scraper` 搜索债券 `code` 并获取所有公告。
    -   **异常处理**: 捕获 `RateLimitException`，自动切换账号重试。
    -   **数据存储**: 调用 `database.save_announcements()` 将数据存入 SQLite。
6.  **账号轮换**: 根据 `REQUESTS_PER_ACCOUNT` 配置，主动轮换账号以降低风险。
7.  **任务结束**: 所有任务完成或所有账号失效后，程序结束。

## 输出结果

-   **数据库**: 所有爬取到的原始数据都存储在项目根目录下的 `qyyjt_data.db` 文件中。你可以使用任何 SQLite 客户端工具（如 DB Browser for SQLite）打开查看。
-   **分析与下载**: 使用 `tools/` 目录下的脚本所生成的 Excel 文件、JSON 任务文件和下载的 PDF 文件，默认都会存放在 `output/` 目录中。

数据库中 `announcements` 表的结构如下：

| 字段名               | 类型      | 描述                               |
| -------------------- | --------- | ---------------------------------- |
| `id`                 | INTEGER   | 主键，自增                         |
| `search_term`        | TEXT      | 爬取时使用的原始搜索词（债券简称） |
| `bond_name`          | TEXT      | API 返回的规范债券名称             |
| `bond_code`          | TEXT      | 债券在网站内部的唯一代码           |
| `announcement_title` | TEXT      | 公告的完整标题                     |
| `file_url`           | TEXT      | 公告PDF文件的下载链接（唯一）      |
| `file_size`          | TEXT      | 文件大小 (如 "2.13MB")             |
| `publish_date`       | TEXT      | 公告发布日期 (如 "20231026110255") |
| `scraped_at`         | TIMESTAMP | 该条记录的爬取时间                 |

## 注意事项

-   **遵守网站规则**: 请合理使用本爬虫，尊重目标网站的 `robots.txt` 协议和服务条款。过于频繁的请求可能导致你的账号或 IP 地址被封禁。
-   **代码维护**: 网站的前端或后端 API 随时可能发生变化，导致爬虫失效。如果遇到问题，可能需要根据新的网络请求更新 `config.py` 中的 URL 和 `scraper.py` 中的解析逻辑。
-   **法律与道德风险**: 本项目仅供学习和技术研究使用。请勿用于任何非法或商业用途。因使用本代码而产生的任何法律后果，由使用者自行承担。