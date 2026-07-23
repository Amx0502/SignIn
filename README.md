# 签到管理系统（Vue 3 + Element Plus + FastAPI）

基于 FastAPI 与 Vue 3 的签到管理系统。账户、签到任务和远端项目数据存储在 MySQL 中；系统设置、后台用户和登录会话暂时保留原有 JSON 存储。

## 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 5.7

## 项目结构

```text
backend/
  app/
    main.py          FastAPI 入口与接口
    service.py       签到、调度与通知业务
    database.py      MySQL 连接、建库和会话
    db_models.py     SQLAlchemy 数据表模型
    repository.py    账户、任务和项目 CRUD
    models.py        Pydantic 请求模型
    config.py        本地文件和默认业务配置
frontend/
  src/               Vue 3 前端
```

## MySQL 配置

默认连接地址、数据库和用户分别为 `127.0.0.1:3306`、`xxqd` 和 `root`。数据库密码必须通过环境变量提供，不能写入源码：

```powershell
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
$env:DB_NAME="xxqd"
$env:DB_USER="root"
$env:DB_PASSWORD="<数据库密码>"
```

启动用户需要拥有创建数据库和数据表的权限。`xxqd` 不存在时，应用会自动创建数据库及以下表：

- `accounts`
- `tasks`
- `account_projects`

数据库连接失败时应用会直接停止启动，不会回退到 JSON 文件。

## 旧数据迁移

如果 `accounts` 表为空且存在 `backend/accounts.json`，应用首次启动时会在单个事务中导入账户、任务和项目。导入成功后保留原文件作为备份，但后续账户 CRUD 不再读取或写入该文件。

数据库已有账户时不会重复导入。导入失败会整体回滚并终止启动。

## 登录用户数据库

后台登录用户和会话使用独立的 MySQL 数据库 `User`：

```powershell
$env:AUTH_DB_HOST="127.0.0.1"
$env:AUTH_DB_PORT="3306"
$env:AUTH_DB_NAME="User"
$env:AUTH_DB_USER="root"
$env:AUTH_DB_PASSWORD="<数据库密码>"
```

应用会自动创建 `users` 和 `user_sessions` 表。`users` 表为空时会一次性导入
`backend/users.json`；旧会话不会迁移，升级后需要重新登录。若没有旧用户，则创建
初始管理员 `admin / admin123`，首次登录必须修改密码。

只有管理员可以使用一级菜单“用户管理”。系统禁止删除、禁用或降级最后一个启用中的管理员。

## 后端运行

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
$env:DB_NAME="xxqd"
$env:DB_USER="root"
$env:DB_PASSWORD="<数据库密码>"
$env:AUTH_DB_HOST="127.0.0.1"
$env:AUTH_DB_PORT="3306"
$env:AUTH_DB_NAME="User"
$env:AUTH_DB_USER="root"
$env:AUTH_DB_PASSWORD="<数据库密码>"

python run.py
```

后端默认监听 `http://0.0.0.0:8765`。

## 后端测试

测试会创建名称为 `xxqd_test_<随机值>` 的临时数据库，并在测试结束时仅删除本次创建的临时库，不修改正式数据库 `xxqd`。

```powershell
cd backend
$env:DB_PASSWORD="<数据库密码>"
python -m pytest tests -v
```

## 前端开发与构建

```powershell
cd frontend
npm install
npm run dev
```

生产构建：

```powershell
npm run build
```

开发服务器默认监听 `http://0.0.0.0:5173`，并将 `/api` 代理到后端。

## 主要功能

- 账户新增、编辑、删除、登录和 Token 刷新
- 签到任务新增、编辑、删除和手动执行
- 普通签到与图片签到
- 自动刷新 Token 和定时签到
- 周末跳过、企业微信通知和运行日志
