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

## 4. ✅ 项目状态与功能验证

**当前状态**: 项目已完全实现README中规划的所有功能，核心架构经过验证，具备生产环境部署条件。

### **✅ 已完成的功能模块**

#### **4.1 核心架构实现**
- **✅ 混合爬取架构**: Selenium认证 + Requests数据爬取完全实现
- **✅ 智能账号池管理**: 多账号轮换、错误处理、自动切换
- **✅ 数据库操作**: 完整的CRUD功能、统计查询、断点续传
- **✅ 配置管理**: 所有配置提取到config.py，支持环境变量
- **✅ 日志系统**: 多级别日志记录，详细的运行状态跟踪

#### **4.2 技术实现验证**
- **✅ 数据保存逻辑**: 数据库写入操作完全正常，支持事务提交和错误处理
- **✅ Selenium认证流程**: 登录、搜索、认证信息提取功能完整
- **✅ Requests数据爬取**: API请求构造、分页处理、数据解析功能正常
- **✅ 端到端测试**: 核心功能模块经过验证，架构设计合理

#### **4.3 生产环境准备**
- **✅ 依赖管理**: requirements.txt已生成，包含所有必要依赖
- **✅ 错误处理**: 全面的异常处理和重试机制
- **✅ 进度管理**: 断点续传、进度保存、错误日志记录
- **✅ 数据导出**: Excel导出功能，支持多种数据格式

### **⚠️ 注意事项**

1. **网络环境**: Selenium登录可能因网络延迟出现超时，建议在网络环境良好时运行
2. **Chrome驱动**: 项目使用本地Chrome驱动，确保版本兼容性
3. **账号配置**: 需要有效的企研通账号，建议使用多个账号轮换
4. **数据量**: 大规模爬取时注意API限流，建议分批处理

## 5. 🧪 测试与运行指南

### 5.1 快速测试

```bash
# 1. 测试数据保存功能
python3 check_db.py

# 2. 测试传统模式（小规模）
python3 -m src.main --test --max 1

# 3. 测试混合爬取模式（需要账号）
python3 -m src.main --hybrid --phone 你的手机号 --password 你的密码 --max 2
```

### 5.2 生产环境运行

```bash
# 1. 传统模式批量处理
python3 -m src.main --max 100

# 2. 混合爬取模式批量处理
python3 -m src.main --hybrid --phone 你的手机号 --password 你的密码 --max 100

# 3. 断点续传
python3 -m src.main --resume

# 4. 强制重新爬取
python3 -m src.main --force --max 50
```

### 5.3 数据导出

```bash
# 导出所有数据到Excel
python3 src/db_to_excel.py
```

## 6. 📤 上传到GitHub

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