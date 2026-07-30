# 班级魔方立即执行与魔方日志实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 BJMF-main 的远端接口契约修复班级魔方任务执行，提供同步立即执行结果，并新增独立持久化魔方日志页面。

**Architecture:** `ClassCubeClient` 负责会话预热和正确远端 URL；`ClassCubeService.execute_task()` 统一自动与手动执行并返回结构化汇总；仓储保存签到项级和任务级运行记录；独立 logger 同时写文件和内存；Vue 将运行记录与日志拆分为两个页面。

**Tech Stack:** Python、FastAPI、SQLAlchemy、MySQL 5.7、requests、Vue 3、Element Plus、Axios、Node test、Vite。

## Global Constraints

- 远端接口用法以 `D:\下载\BJMF-main` 为依据。
- 保留当前主机白名单、严格结果判定、多签到类型和 MySQL 存储。
- 班级魔方日志只使用 `/api/class-cube/logs` 和 `backend/logs/class_cube.log`。
- 日志不得包含 Cookie、密码、Webhook 或完整远端响应。
- 保留用户对 `frontend/src/App.vue` 的现有修改。
- 只提交本地 Git，不推送 GitHub。

---

### Task 1: 修正 BJMF 会话与远端 URL

**Files:**
- Modify: `backend/app/class_cube_client.py`
- Modify: `backend/test_class_cube_client.py`

**Interfaces:**
- Produces: `ClassCubeClient._warm_student_session(session) -> None`
- Produces: `COURSES_URL = "https://bjmf.k8n.cn/student"`
- Produces: `CHECKIN_LIST_URLS[module] = "https://bjmf.k8n.cn/student/course/{course_id}/{module}"`

- [ ] **Step 1: 写失败测试**

```python
def test_fetch_items_warms_session_then_uses_bjmf_list_url(self):
    session = FakeSession([
        FakeResponse(url="https://bjmf.k8n.cn/student/my"),
        FakeResponse(text='<div id="punchcard_9"></div>'),
    ])
    client = ClassCubeClient(session_factory=lambda: session)
    client.fetch_items(COOKIE, "123", "punchs")
    assert [call[1] for call in session.calls[:2]] == [
        "https://bjmf.k8n.cn/student/my",
        "https://bjmf.k8n.cn/student/course/123/punchs",
    ]

def test_fetch_courses_warms_session_then_reads_student_page(self):
    session = FakeSession([FakeResponse(), FakeResponse(text=COURSE_HTML)])
    ClassCubeClient(session_factory=lambda: session).fetch_courses(COOKIE)
    assert session.calls[1][1] == "https://bjmf.k8n.cn/student"
```

- [ ] **Step 2: 运行测试并确认 URL 断言失败**

Run: `python -m unittest test_class_cube_client`
Expected: FAIL，实际列表 URL 为旧的 `/student/punchs/course/123` 或缺少预热请求。

- [ ] **Step 3: 实现 BJMF-main 请求顺序**

```python
COURSES_URL = "https://bjmf.k8n.cn/student"
CHECKIN_LIST_URLS = {
    module: f"https://bjmf.k8n.cn/student/course/{{course_id}}/{module}"
    for module in ("punchs", "daka")
}

def _warm_student_session(self, session):
    response = self._get_with_retries(session, STUDENT_PROFILE_URL)
    self._raise_if_cookie_expired(response)
```

`fetch_courses()` 和 `fetch_items()` 在目标请求前调用预热；详情和提交 URL 保持 `/student/{punch_type}/course/{course_id}/{item_id}`。

- [ ] **Step 4: 运行测试并提交**

Run: `python -m unittest test_class_cube_client test_class_cube_parser`
Expected: PASS。

```bash
git add backend/app/class_cube_client.py backend/test_class_cube_client.py
git commit -m "修正班级魔方远端接口用法"
```

### Task 2: 统一任务执行与可见结果

**Files:**
- Modify: `backend/app/class_cube_db_models.py`
- Modify: `backend/app/class_cube_database.py`
- Modify: `backend/app/class_cube_repository.py`
- Modify: `backend/app/class_cube_service.py`
- Modify: `backend/app/class_cube_scheduler.py`
- Modify: `backend/app/class_cube_router.py`
- Test: `backend/test_class_cube_scheduler.py`
- Test: `backend/test_class_cube_repository_service.py`
- Test: `backend/test_class_cube_checkin.py`

**Interfaces:**
- Produces: `ClassCubeService.execute_task(task_id: int, trigger: str) -> dict`
- Produces: `ClassCubeRepository.record_task_run(task_id, status, message, summary, started_at) -> dict`
- Produces: `POST /api/class-cube/tasks/{task_id}/run` 返回执行汇总

- [ ] **Step 1: 写无签到和禁用任务失败测试**

```python
def test_manual_execution_returns_no_items_and_records_run(service, repository):
    service.sync_items = lambda course_id, actor: []
    result = service.execute_task(TASK_ID, trigger="manual")
    assert result["status"] == "no_sign_in"
    assert result["scanned"] == 0
    assert repository.list_runs(0, True)[0]["status"] == "no_sign_in"

def test_manual_execution_allows_disabled_task(service):
    disable_task(TASK_ID)
    assert service.execute_task(TASK_ID, trigger="manual")["status"] != "disabled"
```

- [ ] **Step 2: 运行测试并确认当前无任务级记录**

Run: `python -m unittest test_class_cube_repository_service test_class_cube_checkin`
Expected: FAIL，缺少 `execute_task` 或运行记录为空。

- [ ] **Step 3: 允许任务级运行记录**

将 `class_cube_task_runs.checkin_item_id` 改为可空，MySQL 启动迁移执行：

```sql
ALTER TABLE class_cube_task_runs
MODIFY COLUMN checkin_item_id BIGINT NULL
```

任务级记录使用 `checkin_item_id=NULL`、`remote_item_id=''`、`mode='task'`。`record_task_run()` 保存消息、汇总、开始和结束时间。

- [ ] **Step 4: 提取统一执行方法**

```python
def execute_task(self, task_id, trigger):
    started_at = datetime.now()
    task = self.repository.get_task(task_id, 0, True)
    # manual 绕过 enabled；scheduled 保持 enabled 检查
    # 同步项目、逐项声明和提交、汇总状态
    # 没有可执行项目时 record_task_run(..., "no_sign_in", ...)
    return {
        "task_id": task_id,
        "task_name": task["name"],
        "status": overall_status,
        "scanned": len(active_items),
        "success": success_count,
        "already_signed": already_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "unknown": unknown_count,
        "details": details,
    }
```

`run_scheduled_task()` 调用 `execute_task(task_id, "scheduled")`。任务级锁防止同一任务自动和手动并发；重复执行抛出 `ClassCubeValidationError("该任务正在执行")`。

- [ ] **Step 5: 改为同步立即执行接口**

路由校验任务权限后调用 `service.execute_task(task_id, "manual")`，不再调用 `scheduler.submit()`。远端错误映射为现有统一错误响应。

- [ ] **Step 6: 运行测试并提交**

Run: `python -m unittest test_class_cube_scheduler test_class_cube_repository_service test_class_cube_checkin`
Expected: PASS。

```bash
git add backend/app/class_cube_db_models.py backend/app/class_cube_database.py backend/app/class_cube_repository.py backend/app/class_cube_service.py backend/app/class_cube_scheduler.py backend/app/class_cube_router.py backend/test_class_cube_scheduler.py backend/test_class_cube_repository_service.py backend/test_class_cube_checkin.py
git commit -m "修复班级魔方立即执行反馈"
```

### Task 3: 持久化班级魔方日志

**Files:**
- Modify: `backend/app/class_cube_logging.py`
- Modify: `backend/app/class_cube_service.py`
- Modify: `backend/app/class_cube_client.py`
- Modify: `backend/app/main.py`
- Test: `backend/test_class_cube_isolation.py`
- Create: `backend/test_class_cube_logging.py`

**Interfaces:**
- Produces: `create_class_cube_logger(store, log_path=config.LOG_DIR / "class_cube.log")`
- Produces: `ClassCubeLogStore.load_tail(path, limit) -> None`

- [ ] **Step 1: 写持久化格式失败测试**

```python
def test_logger_writes_timestamped_file_and_memory(tmp_path):
    store = ClassCubeLogStore()
    logger = create_class_cube_logger(store, tmp_path / "class_cube.log")
    logger.info("任务开始")
    line = store.snapshot(1)[0]
    assert re.match(r"\d{4}-\d{2}-\d{2} .* \[INFO\] 任务开始", line)
    assert "任务开始" in (tmp_path / "class_cube.log").read_text("utf-8")

def test_logger_redacts_sensitive_values(tmp_path):
    logger.info("cookie=secret password=123 webhook=https://qyapi...")
    content = log_path.read_text("utf-8")
    assert "secret" not in content
```

- [ ] **Step 2: 运行测试并确认当前没有文件输出**

Run: `python -m unittest test_class_cube_logging`
Expected: FAIL，文件不存在或格式无时间与级别。

- [ ] **Step 3: 实现双写、轮转和脱敏**

使用 `TimedRotatingFileHandler(when="midnight", backupCount=7, encoding="utf-8")` 和内存 handler，共用：

```python
logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
```

在 handler 写入前过滤 `cookie=...`、`password=...`、企业微信 Webhook 和 `remember_student_*` 值。启动时从文件尾部加载最多 500 条到内存。

- [ ] **Step 4: 添加执行阶段业务日志**

记录任务开始、触发来源、账号和课程显示名、两个模块识别数量、每项最终状态、无签到项、异常类型、通知结果、任务汇总和耗时；客户端不得记录 Cookie 或完整 HTML。

- [ ] **Step 5: 运行测试并提交**

Run: `python -m unittest test_class_cube_logging test_class_cube_isolation`
Expected: PASS。

```bash
git add backend/app/class_cube_logging.py backend/app/class_cube_service.py backend/app/class_cube_client.py backend/app/main.py backend/test_class_cube_logging.py backend/test_class_cube_isolation.py
git commit -m "添加持久化班级魔方日志"
```

### Task 4: 独立魔方日志页面

**Files:**
- Create: `frontend/src/views/ClassCubeLogs.vue`
- Modify: `frontend/src/views/ClassCubeRuns.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/api/classCube.js`
- Modify: `frontend/src/components/class-cube/AutoTaskPanel.vue`
- Test: `frontend/src/utils/classCubeUi.test.js`
- Test: `frontend/src/utils/classCube.test.js`

**Interfaces:**
- Consumes: `GET /api/class-cube/logs`
- Consumes: 同步 `runTask(taskId)` 执行汇总
- Produces: 路由 `/class-cube/logs`

- [ ] **Step 1: 写页面和菜单失败测试**

```javascript
test('class cube logs are a separate fifth page', async () => {
  const router = await source('../router/index.js')
  assert.match(router, /path:\s*['"]\/class-cube\/logs['"]/)
  const runs = await source('../views/ClassCubeRuns.vue')
  assert.doesNotMatch(runs, /loadLogs|cube-logs|setInterval/)
  const logs = await source('../views/ClassCubeLogs.vue')
  assert.match(logs, /classCubeApi\.listLogs/)
  assert.doesNotMatch(logs, /xxqd/)
})
```

- [ ] **Step 2: 运行测试并确认缺少新页面**

Run: `node --test src/utils/classCubeUi.test.js`
Expected: FAIL，找不到 `ClassCubeLogs.vue` 或路由。

- [ ] **Step 3: 拆分运行记录和日志**

`ClassCubeRuns.vue` 仅保留 `RunHistoryPanel`。`ClassCubeLogs.vue` 复用 `Logs.vue` 的日志解析、级别筛选、条数、刷新、滚动到底部、深色面板和响应式样式，但数据源固定为 `classCubeApi.listLogs()`。

- [ ] **Step 4: 增加路由与菜单**

在班级魔方子菜单“运行记录”后添加“魔方日志”；导入 `ClassCubeLogs` 并注册 `/class-cube/logs`。只增量修改 `App.vue`，保留用户已有内容。

- [ ] **Step 5: 改造立即执行反馈**

`classCubeApi.runTask` 使用 60 秒超时。`AutoTaskPanel` 维护 `runningTaskId`，执行时显示加载；根据 `status` 显示“签到成功/已签到/当前无签到/执行失败”，完成后刷新任务和运行记录。

- [ ] **Step 6: 运行测试和构建并提交**

Run: `node --test src/utils/*.test.js`
Expected: PASS。

Run: `npm.cmd run build`
Expected: Vite build success。

```bash
git add frontend/src/views/ClassCubeLogs.vue frontend/src/views/ClassCubeRuns.vue frontend/src/router/index.js frontend/src/App.vue frontend/src/api/classCube.js frontend/src/components/class-cube/AutoTaskPanel.vue frontend/src/utils/classCubeUi.test.js frontend/src/utils/classCube.test.js
git commit -m "新增班级魔方独立日志页面"
```

### Task 5: 全量验证与交付

**Files:**
- Modify only files listed above if verification reveals a regression.

**Interfaces:**
- Verifies all previous interfaces together.

- [ ] **Step 1: 运行后端全量测试**

Run: `python -m unittest discover -s . -p "test_*.py"`
Expected: 全部 PASS，依赖未配置 MySQL 的测试允许明确 SKIP。

- [ ] **Step 2: 运行前端全量测试**

Run: `node --test src/utils/*.test.js`
Expected: 全部 PASS。

- [ ] **Step 3: 运行生产构建**

Run: `npm.cmd run build`
Expected: 输出 `✓ built`。

- [ ] **Step 4: 检查隔离和敏感数据**

Run: `rg -n "xxqd/logs" frontend/src/views/ClassCubeLogs.vue backend/app/class_cube_*`
Expected: 无匹配。

Run: `git diff --check`
Expected: 无输出。

- [ ] **Step 5: 提交最终修正**

```bash
git add backend frontend
git commit -m "完成班级魔方执行与日志修复"
```

