- # 企研通城投债公告爬虫 (QYYJT Bond Prospectus Scraper)

  ## 1. 项目概述

  本项目是一个为**企研通 (qyyjt.cn)** 网站定制的自动化爬虫，旨在批量抓取城投债的募集说明书及相关公告。项目采用 Python 编写，并设计了一套健壮的混合爬取架构：

  - **Selenium-wire**: 负责模拟真实用户行为，自动完成复杂的登录流程，并拦截关键网络请求，以安全、可靠地获取动态生成的认证令牌和目标实体 `code`。
  - **Requests**: 在获取认证信息后，接管后续所有数据拉取任务，以高并发、高效率的方式与后端 API 直接交互，实现大规模数据的快速采集。

  项目内置了智能账号池管理、全面的错误处理与重试机制、基于 SQLite 的断点续传，以及灵活的 Excel 数据导出功能，目标是实现无人值守的高效、稳定数据采集。

  ## 2. ⚙️ 技术架构与核心流程

  本爬虫的核心设计思想是将“获取认证”与“数据抓取”两个阶段彻底分离，以兼顾稳定性和效率。

  *(建议您根据此描述绘制一个流程图并替换链接)*

  1. **认证阶段 (Selenium-wire)**:

     - 启动浏览器，加载登录页面。
     - 使用账号池中的一个账号，模拟输入用户名、密码，完成登录。
     - 遍历待爬取债券列表，在页面搜索框中逐一输入关键词并触发搜索。
     - **[核心]** 利用 `selenium-wire` 的请求拦截能力，捕获 `multipleSearch` API 的网络请求。
     - 从该请求的 **Request Headers** 中提取动态认证信息 (`pcuss`, `user`)，并从浏览器中获取会话 Cookies (`HWWAF...`)。
     - 从该请求的 **Response Body** (JSON) 中解析出目标实体的唯一标识符 `code`。
     - 将所有提取到的认证信息和 `code` 列表打包，完成 Selenium 的使命并关闭浏览器。

  2. **数据抓取阶段 (Requests)**:

     - 初始化一个 `requests.Session` 对象。

     - 将上一阶段获取的 `headers` 和 `cookies` 设置到 Session 中，完成身份模拟。

     - 遍历

        

       ```
       code
       ```

        

       列表，针对每一个

        

       ```
       code
       ```

        

       执行以下操作：

       - 构造 `getF9NoticeList` API 的请求体 (Payload)，包含 `code` 和分页参数 `skip`。
       - **[核心]** 动态生成与 `code` 匹配的 `Referer` 请求头。
       - 使用 `while` 循环和递增的 `skip` 参数，实现分页拉取，直到 API 返回空数据列表。
       - 将每一页获取到的公告数据存入 SQLite 数据库。

  ## 3. 🚀 如何开始

  ### 3.1. 环境准备

  ```bash
  # 1. 建议创建并激活 Python 虚拟环境
  python -m venv venv
  # Windows: venv\Scripts\activate | macOS/Linux: source venv/bin/activate
  
  # 2. 安装项目依赖 (待 requirements.txt 创建)
  # 假设您已根据需要安装了 selenium, selenium-wire, requests, pandas, openpyxl
  pip freeze > requirements.txt
  pip install -r requirements.txt
  
  # 3. 下载并配置 WebDriver
  # 确保您已安装 Chrome 浏览器，并下载对应版本的 chromedriver
  # 将 chromedriver.exe 放置在项目根目录或系统 PATH 路径下
  ```

### 3.2. 项目配置

1. **账号配置**: 复制 `accounts_config.json.example` 为 `accounts_config.json`，并填入真实的企研通账号信息。

   ```json
   {
     "accounts": [
       {
         "phone": "your_phone_number",
         "password": "your_password",
         "description": "主账号"
       }
     ],
     "settings": {
       "max_concurrent_accounts": 3,
       "account_switch_interval": 10,
       "error_threshold": 5,
       "auto_switch_on_error": true
     }
   }
   ```

2. **下载配置**: 复制 `download_config.json.example` 为 `download_config.json`，根据需要调整下载参数。

3. **待爬列表**: 将需要爬取的债券简称或全称填入 `bonds_list.xlsx` 文件的第一列。

⚠️ **重要**: 请勿将包含真实账号密码的配置文件上传到GitHub！

  ### 3.3. 运行项目

  1. 执行主程序

     :

     ```bash
     python main.py
     ```

  2. 导出数据

     : 爬取任务完成后，运行导出脚本。

     ```bash
     python db_to_excel.py
     ```

     结果将保存在

      

     ```
     output
     ```

      

     文件夹下的 Excel 文件中。

  ## 4. ⚠️ 当前状态与行动计划

  **当前状态**: 项目核心框架已搭建，但在端到端测试中发现**数据未能成功写入数据库**的核心阻塞问题。

  **首要目标**: **打通从登录到数据入库的完整链路，确保单次流程的正确性。**

  ------

  ### **下一步开发行动计划 (技术细节版)**

  #### **阶段一：核心流程修复与技术细节验证 (P0 - 最高优先级)**

  ##### **步骤 1.1 (前置): 调试数据保存逻辑**

  - **定位问题:** 在 `scraper.py` 或 `database.py` 中，找到调用数据库插入功能的代码。

  - 行动:

    1. 使用 `try...except Exception as e:` 块包裹数据库写入操作，并务必打印详细的错误日志 `print(f"Database write error: {e}")`。

    2. 检查点

       :

       - **数据匹配**: 确认待插入的数据元组/字典的字段数量、顺序和类型，与 `CREATE TABLE` 语句中定义的表结构**严格一致**。
       - **事务提交**: 确认在执行 `INSERT` 或 `UPDATE` 后，调用了 `connection.commit()`。
       - **参数化查询**: 确保使用了 `(?, ?, ...)` 的参数化查询方式，防止因数据中包含特殊字符（如单引号）导致 SQL 语法错误。

  ##### **步骤 1.2: 精确定义 Selenium 的职责与产出**

  - **Selenium 的唯一任务:** **获取 `code` 列表和 `auth_package`**。它不参与任何 `getF9NoticeList` 的数据爬取。

  - 技术实现细节

    :

    1. **登录与搜索 (`search_and_get_codes`):** 登录后，循环遍历关键词列表，在页面上执行搜索。

    2. **捕获与解析:** 使用 `driver.wait_for_request(r'.*multipleSearch.*', timeout=10)` 精确捕获搜索 API 的响应。从响应体 (JSON) 中解析出 `code`。

    3. 提取认证信息 (`get_auth_package`):

        

       在

       首次

       成功捕获

        

       ```
       multipleSearch
       ```

        

       请求后，立即执行此操作：

       - **Headers**: 从该请求的 `request.headers` 字典中直接提取 `pcuss` 和 `user` 的值。这是最可靠的方法。
       - **Cookies**: 调用 `driver.get_cookies()`，并将其转换为 `requests` 库所需的 `{name: value}` 字典格式。

    4. **关闭浏览器:** 调用 `driver.quit()`，结束 Selenium 的所有工作。

  - 最终产出:

    - 一个 `codes_to_process` 列表: `['9380A...', '7B079...', ...]`

    - 一个

       

      ```
      auth_package
      ```

       

      字典，结构如下：

      ```python
      auth_package = {
          'headers': {
              'pcuss': 'eyJhbGciOiJI...',
              'user': '92E11A5F5D0A...',
              'User-Agent': 'Mozilla/5.0 ...',
              'client': 'pc-web;pro',
              # ... 其他从 cURL 分析中复制的固定请求头
          },
          'cookies': {
              'HWWAFSESTIME': '175...',
              'HWWAFSESID': '1fe...'
          }
      }
      ```

  ##### **步骤 1.3: 精确定义 Requests API 的请求构造**

  - **任务:** 使用上一步的产出，通过 `requests` 高效、准确地爬取数据。

  - 技术实现细节 (`fetch_notices`):

    1. 初始化 Session:

       ```python
       session = requests.Session()
       session.headers.update(auth_package['headers'])
       session.cookies.update(auth_package['cookies'])
       ```

    2. 遍历 `code` 列表:

        

       对于每一个

        

       ```
       code
       ```

       ：

       - 构造请求体 (Payload):

         - 这是一个 **form-data** (`application/x-www-form-urlencoded`)。
         - **动态字段:** `code` (当前 `code`), `skip` (用于翻页)。
         - **固定字段 (根据 cURL 分析):** `type='co'`, `size=50`, 等。

         ```python
         payload = {
             'code': current_code,
             'type': 'co',
             'size': 50,
             'skip': 0, # 初始偏移量
             'tab': 'notice_bond_coRelated'
             # ... 其他必要的固定参数
         }
         ```

       - 动态构造 `Referer` Header:

          

         这是唯一需要在循环中更新的 Header。

         ```python
         dynamic_referer = f"https://www.qyyjt.cn/detail/bond/notice?code={current_code}&type=co"
         session.headers['Referer'] = dynamic_referer
         ```

       - 执行分页爬取 (`while True`):

         - 发起 POST 请求: `response = session.post(API_URL, data=payload)`
         - 检查响应 `response.status_code`。
         - 解析 JSON `results = response.json()['data']['list']`。
         - 如果 `not results` (列表为空)，`break` 循环。
         - **调用数据库模块，将 `results` 写入数据库。**
         - 更新分页参数: `payload['skip'] += 50`。

  ##### **步骤 1.4: 端到端小批量验证**

  - 行动:
    1. 配置程序仅处理 `bonds_list.xlsx` 中的前 5 个债券。
    2. 完整运行 `main.py`。
    3. 验证:
       - 观察日志输出是否符合预期流程（Selenium 启动->登录->搜索->提取认证->关闭；Requests 开始循环->翻页->处理完毕）。
       - **最终检查 `database.db` 文件，确认这 5 个债券的所有公告数据已成功、完整地写入。**

  #### **阶段二：健壮性与可用性增强 (P1 - 中等优先级)**

  - **2.1 生成 `requirements.txt`**: 固化项目依赖。
  - **2.2 配置文件 (`config.py` / `.ini`)**: 将所有硬编码的 URL、API 端点、Selectors 和固定参数提取到配置文件中，方便维护。
  - **2.3 完善日志**: 增加更详细的日志级别（INFO, WARNING, ERROR），记录关键步骤和错误信息。

  #### **阶段三：生产部署与批量执行 (P2 - 低等优先级)**

  - **3.1 重置进度**: 在所有核心问题修复后，清空数据库和进度文件。
  - **3.2 执行批量爬取**: 在生产模式下运行主程序，处理全部债券列表。
  - **3.3 监控与分析**: 定期检查日志，关注账号切换频率和错误报告。
  - **3.4 数据验证**: 爬取完成后，抽样检查导出数据，确保其准确性和完整性。

## 5. 📤 上传到GitHub

### 5.1. 准备工作

1. **确保敏感信息已保护**:
   - 检查 `.gitignore` 文件已正确配置
   - 确认 `accounts_config.json` 和 `download_config.json` 不会被上传
   - 验证 `data/` 目录和 `downloads/` 目录被忽略

2. **创建GitHub仓库**:
   - 登录 [GitHub](https://github.com)
   - 点击右上角的 "+" 号，选择 "New repository"
   - 填写仓库名称（建议：`qyyjt-scraper`）
   - 选择 "Public" 或 "Private"（建议选择 Private 保护敏感信息）
   - 不要勾选 "Initialize this repository with a README"（因为我们已经有了）

### 5.2. 本地Git初始化

在项目根目录下执行以下命令：

```bash
# 1. 初始化Git仓库
git init

# 2. 添加所有文件到暂存区
git add .

# 3. 检查暂存区文件（确保敏感文件未被添加）
git status

# 4. 提交文件
git commit -m "Initial commit: 企研通城投债公告爬虫项目"

# 5. 添加远程仓库（替换为你的GitHub仓库地址）
git remote add origin https://github.com/你的用户名/qyyjt-scraper.git

# 6. 推送到GitHub
git push -u origin main
```

### 5.3. 后续维护

```bash
# 查看文件状态
git status

# 添加修改的文件
git add .

# 提交更改
git commit -m "描述你的更改"

# 推送到GitHub
git push
```

### 5.4. 注意事项

- **永远不要**将包含真实账号密码的配置文件上传到GitHub
- 定期检查 `.gitignore` 文件，确保敏感信息被正确忽略
- 如果意外上传了敏感信息，立即删除仓库并重新创建
- 建议使用环境变量或配置文件模板来管理敏感配置