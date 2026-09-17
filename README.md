## 后端运行

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

Copy-Item database_config.example.json database_config.json
# 编辑 database_config.json，填写业务库和认证库连接参数

python run.py
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