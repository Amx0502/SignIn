# 签到管理系统（Vue3 + ElementPlus + FastAPI）

基于原有 Python 签到逻辑，使用 **FastAPI** 重写后端、**Vue3 + ElementPlus** 重写前端的管理系统。

## 项目结构

```
SignIn-Vue/
├── backend/          FastAPI 后端
│   ├── app/
│   │   ├── main.py       FastAPI 入口与接口
│   │   ├── service.py    签到业务逻辑/调度/数据持久化
│   │   ├── models.py     Pydantic 模型
│   │   └── config.py     配置（默认读取 SignIn/accounts1.json）
│   ├── requirements.txt
│   └── run.py
└── frontend/         Vue3 + ElementPlus 前端
    ├── src/
    │   ├── views/         系统概览 / 账号管理 / 任务管理 / 运行日志
    │   ├── api/           后端接口封装
    │   ├── composables/   全局状态与轮询
    │   └── router/        路由
    ├── package.json
    └── vite.config.js
```

## 环境要求

- Python 3.10+
- Node.js 18+

## 后端运行

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
./venv/Scripts/python.exe run.py
```

后端默认运行在 `http://0.0.0.0:8765`，会自动读取原项目 `C:\Users\ASUS\Desktop\SignIn\accounts1.json`。

## 前端开发

```powershell
cd frontend
npm install
npm run dev
```

开发服务器默认 `http://0.0.0.0:5173`，通过 `vite.config.js` 代理 `/api` 到后端。

## 前端构建

```powershell
cd frontend
npm run build
```

构建产物输出到 `frontend/dist`，FastAPI 启动时会自动托管该目录作为静态资源，直接访问 `http://0.0.0.0:8765/` 即可。

## 主要功能

- 账号新增 / 编辑 / 删除 / 登录获取 Token / 刷新 Token
- 任务新增 / 编辑 / 删除，支持普通签到与图片签到
- 获取签到项目列表并自动填充序号
- 手动执行单个任务、单个账号全部任务、全部启用任务
- 自动调度：定时刷新 Token、按任务时间自动签到、支持周末跳过
- 实时日志轮询展示

## 数据说明

后端默认沿用原项目 `accounts1.json` 路径，首次启动会自动读取已有账号和任务数据。
