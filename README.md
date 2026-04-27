# AutoTasker

基于课程文档实现的 AutoTasker Web MVP，当前后端已经迁移到：

- `FastAPI`
- `SQLAlchemy 2.0`
- `JWT`
- `LangChain`
- `MySQL-ready` 数据库配置

前端仍保留当前单页演示界面，覆盖：

- 用户注册 / 登录
- 目标输入
- AI 任务草案生成
- 草案确认后进入看板
- 番茄钟执行记录
- 统计概览与 AI 复盘建议

## 目录结构

```text
app/
  api.py                # FastAPI 路由
  config.py             # 环境配置
  database.py           # SQLAlchemy 引擎与会话
  deps.py               # 当前用户依赖
  main.py               # FastAPI 应用入口
  models.py             # ORM 模型
  schemas.py            # Pydantic schema
  security.py           # 密码哈希与 JWT
  services/
    ai.py               # LangChain 多厂商 AI 接入
    metrics.py          # 统计与复盘基础逻辑
static/
  index.html            # 页面
  app.js                # 前端逻辑
  styles.css            # 样式
server.py               # 本地启动入口
requirements.txt
```

## 安装依赖

```bash
pip3 install -r requirements.txt
```

如果还没装 Alembic：

```bash
pip3 install alembic
```

## 启动方式

开发启动：

```bash
python3 server.py
```

或直接使用 uvicorn：

```bash
python3 -m uvicorn app.main:app --reload
```

默认地址：

[http://127.0.0.1:8000](http://127.0.0.1:8000)

## Alembic 迁移

初始化或升级数据库：

```bash
python3 -m alembic upgrade head
```

查看当前版本：

```bash
python3 -m alembic current
```

如果你本地已经有一份旧版原型数据库，它不是 Alembic 接管的，直接 `upgrade head` 可能会因为表已存在而失败。这种情况下，先把旧库标记到初始版本，再继续升级：

```bash
python3 -m alembic stamp 20260419_01
python3 -m alembic upgrade head
```

当前迁移版本：

- `20260419_01`：初始化核心表
- `20260419_02`：清理旧原型遗留的 `sessions` 表

## 数据库配置

当前代码优先支持课程文档要求的 MySQL，但为了本地零门槛演示，默认会回退到 SQLite。

### 方式 1：直接用 MySQL

在 `.env` 中配置：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=autotasker
SECRET_KEY=replace-with-a-long-random-secret-key
```

代码会自动拼出：

```text
mysql+pymysql://user:password@host:3306/autotasker?charset=utf8mb4
```

这是按 SQLAlchemy 官方 MySQL + PyMySQL URL 格式接的。
参考：[SQLAlchemy Engine Configuration](https://docs.sqlalchemy.org/20/core/engines.html)

### 方式 2：本地演示先用 SQLite

如果没有配置 MySQL 环境变量，系统默认使用：

```text
sqlite:///data/autotasker.db
```

这让你可以先演示完整流程，再切到 MySQL。

## AI 配置方式

登录后，在左侧“多厂商模型配置”填写：

- 供应商
- 模型名称
- Base URL
- API Key

当前支持：

- `OpenAI`
- `Azure OpenAI`
- `DeepSeek`
- `GLM / 智谱`
- `Gemini`
- `自定义 OpenAI 兼容接口`

如果你不想在页面里填 Key，也可以直接放在 `.env`：

- `OPENAI_API_KEY`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_VERSION`
- `DEEPSEEK_API_KEY`
- `ZHIPU_API_KEY`
- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`

## LangChain 接入说明

这一版已经不是手写 HTTP 拼 JSON 的模式了，而是：

1. 根据供应商构造 LangChain chat model
2. 使用结构化输出能力生成任务草案或复盘结果
3. 用 Pydantic schema 做字段级校验
4. 失败时最多重试 3 次

当前策略：

- `OpenAI / DeepSeek / GLM / 自定义兼容接口`：`ChatOpenAI`
- `Azure OpenAI`：`AzureChatOpenAI`
- `Gemini`：`ChatGoogleGenerativeAI`

结构化输出参考：

- [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [ChatOpenAI.with_structured_output](https://reference.langchain.com/python/langchain-openai/chat_models/base/ChatOpenAI/with_structured_output)
- [ChatGoogleGenerativeAI](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai/)

## 已对齐的课程文档点

- Web 单页应用 + 后端服务 + 数据库 + 大模型服务
- 用户登录 / 注册
- 目标输入与 AI 拆解
- 暂存区 + 用户确认
- 正式任务看板
- 番茄钟执行记录
- 统计与复盘
- JWT 鉴权
- SQLAlchemy ORM 持久化

## 当前接口

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/bootstrap`
- `GET /api/integrations/status`
- `PUT /api/preferences`
- `POST /api/goals/analyze`
- `POST /api/goals/confirm`
- `POST /api/review/generate`
- `PATCH /api/tasks/{id}/status`
- `PATCH /api/tasks/{id}`
- `POST /api/tasks/postpone`
- `POST /api/pomodoro/start`
- `POST /api/pomodoro/finish`
- `GET /api/health`

## 说明与当前边界

已经完成：

- FastAPI 路由化迁移
- SQLAlchemy ORM 建模
- JWT 登录态
- LangChain 多厂商模型适配
- 前端与新后端接口联通

还没有完全做完的地方：

- 没有在当前环境里连真实 MySQL 实例做端到端验证
- 没有在当前环境里完成可调用的 Azure OpenAI deployment 验证
- 还没有拆出更细的 router/service/repository 测试文件

## 本地自测结论

我已经在当前环境完成了这些验证：

- `static/app.js` 语法检查通过
- `FastAPI TestClient` 跑通注册、登录、bootstrap、目标分析、确认草案、AI 复盘流程
- LangChain provider 构造验证通过：
  - `ChatOpenAI`
  - `ChatGoogleGenerativeAI`
- Alembic 在全新数据库文件上 `upgrade head` 验证通过
- `/api/integrations/status` 可返回数据库连通状态和环境 key 状态

## 建议的下一步

如果你要继续把它推进到更像课程答辩成品，我建议按这个顺序继续：

1. 接一套真实 MySQL 并补初始化 SQL 或 Alembic。
2. 增加 LangChain prompt 模板和更细的任务拆解约束。
3. 给看板拖拽、番茄恢复、AI 失败重试补自动化测试。
4. 加 README 里的部署脚本和 `.env` 校验。
