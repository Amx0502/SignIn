# 班级魔方任务填写与企业微信通知实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将班级魔方自动任务改为 BJMF-main 风格的坐标、多个执行时间和日期范围填写方式，并使用独立企业微信机器人发送执行汇总通知。

**Architecture:** `settings.json` 由独立班级魔方设置模块安全读写；MySQL 任务表持久化调度字段，仓储以条件更新原子认领时间点；调度器只负责发现到期任务，服务层负责同步签到项和执行；企业微信客户端作为独立依赖注入服务层。前端系统概览管理全局 Webhook，任务编辑器只管理执行计划和通知开关。

**Tech Stack:** Python 3、FastAPI、Pydantic、SQLAlchemy、MySQL 5.7、requests、Vue 3、Element Plus、Axios、Node test、Vite。

## Global Constraints

- `backend/settings.json` 使用 `class_cube_webhook_url`，不得复用小小签到的 `webhook_url`。
- 企业微信地址必须为 HTTPS，主机必须为 `qyapi.weixin.qq.com`。
- 坐标拾取固定在新标签页打开 `https://www.lddgo.net/convert/position`。
- 旧任务没有执行时间时不得自动执行。
- 班级魔方日志继续使用 `/api/class-cube/logs`，不得写入小小签到日志。
- 所有实现遵循测试先行；只提交本地 Git，不推送 GitHub。

---

### Task 1: 独立设置与企业微信客户端

**Files:**
- Create: `backend/app/class_cube_settings.py`
- Create: `backend/app/class_cube_notifier.py`
- Modify: `backend/app/class_cube_router.py`
- Modify: `backend/app/class_cube_models.py`
- Test: `backend/test_class_cube_settings.py`
- Test: `backend/test_class_cube_notifier.py`

**Interfaces:**
- Produces: `load_class_cube_settings() -> dict[str, str]`
- Produces: `save_class_cube_settings(webhook_url: str) -> dict[str, str]`
- Produces: `validate_wecom_webhook(url: str) -> str`
- Produces: `ClassCubeNotifier.send_summary(webhook_url: str, summary: dict) -> None`

- [ ] **Step 1: 写设置失败测试**

```python
def test_class_cube_setting_preserves_xxqd_fields(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"webhook_url":"xxqd","auto_enabled":true}', encoding="utf-8")
    save_class_cube_settings(
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
        path=path,
    )
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["webhook_url"] == "xxqd"
    assert saved["class_cube_webhook_url"].endswith("key=abc")

def test_rejects_non_wecom_webhook():
    with pytest.raises(ClassCubeSettingsError):
        validate_wecom_webhook("https://example.com/hook")
```

- [ ] **Step 2: 运行设置测试并确认因模块不存在而失败**

Run: `python -m unittest test_class_cube_settings`
Expected: FAIL，提示无法导入 `app.class_cube_settings`。

- [ ] **Step 3: 实现原子设置读写和严格 URL 校验**

```python
def validate_wecom_webhook(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "qyapi.weixin.qq.com":
        raise ClassCubeSettingsError("企业微信机器人地址无效")
    if parsed.path != "/cgi-bin/webhook/send" or not parse_qs(parsed.query).get("key"):
        raise ClassCubeSettingsError("企业微信机器人地址无效")
    return value
```

保存时读取现有 JSON、只覆盖 `class_cube_webhook_url`，使用同目录临时文件和 `Path.replace()` 原子替换。

- [ ] **Step 4: 写企业微信客户端失败测试**

```python
def test_notifier_posts_markdown_and_checks_remote_code():
    client = FakeHttp({"errcode": 0})
    ClassCubeNotifier(client).send_summary(WEBHOOK, {
        "task_name": "高数",
        "account_name": "张三",
        "course_name": "高等数学",
        "success": 1,
        "failed": 0,
        "details": ["签到成功"],
    })
    assert client.posts[0]["json"]["msgtype"] == "markdown"

def test_notifier_raises_when_wecom_rejects_message():
    with pytest.raises(ClassCubeNotificationError):
        ClassCubeNotifier(FakeHttp({"errcode": 93000})).send_summary(WEBHOOK, SUMMARY)
```

- [ ] **Step 5: 实现通知客户端及管理员设置接口**

`ClassCubeNotifier` 使用 `POST`、JSON Markdown 消息和 10 秒超时，并同时检查 HTTP 状态与 `errcode == 0`。在路由新增 `GET/PUT /api/class-cube/settings`；管理员可获得和修改完整地址，普通用户只返回 `webhook_configured`。

- [ ] **Step 6: 运行测试并提交**

Run: `python -m unittest test_class_cube_settings test_class_cube_notifier`
Expected: PASS。

```bash
git add backend/app/class_cube_settings.py backend/app/class_cube_notifier.py backend/app/class_cube_router.py backend/app/class_cube_models.py backend/test_class_cube_settings.py backend/test_class_cube_notifier.py
git commit -m "添加班级魔方企业微信配置"
```

### Task 2: MySQL 调度字段与兼容迁移

**Files:**
- Modify: `backend/app/class_cube_db_models.py`
- Modify: `backend/app/class_cube_database.py`
- Modify: `backend/app/class_cube_repository.py`
- Test: `backend/test_class_cube_repository.py`
- Test: `backend/test_class_cube_mysql.py`

**Interfaces:**
- Produces: task fields `schedule_times: list[str]`, `start_date: date | None`, `end_date: date | None`, `notify_wecom: bool`, `last_schedule_key: str`
- Produces: `claim_task_schedule(task_id: int, schedule_key: str, now: datetime) -> bool`

- [ ] **Step 1: 写持久化和原子认领失败测试**

```python
def test_task_schedule_round_trip(repository, actor):
    task = repository.save_task({
        **valid_task(),
        "schedule_times": ["08:00:00", "18:00:00"],
        "start_date": date(2026, 8, 1),
        "end_date": date(2026, 8, 31),
        "notify_wecom": False,
    }, actor["id"], False)
    assert task["schedule_times"] == ["08:00:00", "18:00:00"]
    assert task["notify_wecom"] is False

def test_schedule_key_can_only_be_claimed_once(repository, saved_task):
    assert repository.claim_task_schedule(saved_task["id"], "2026-08-01T08:00:00")
    assert not repository.claim_task_schedule(saved_task["id"], "2026-08-01T08:00:00")
```

- [ ] **Step 2: 运行仓储测试并确认缺少字段而失败**

Run: `python -m unittest test_class_cube_repository`
Expected: FAIL，任务记录缺少 `schedule_times` 或认领方法。

- [ ] **Step 3: 增加模型字段和序列化**

```python
schedule_times_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
notify_wecom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
last_schedule_key: Mapped[str] = mapped_column(String(32), nullable=False, default="")
```

仓储边界将 JSON 文本转换为 `list[str]`，仅允许保存白名单字段。认领使用：

```python
update(ClassCubeTaskRow).where(
    ClassCubeTaskRow.id == task_id,
    ClassCubeTaskRow.enabled.is_(True),
    ClassCubeTaskRow.last_schedule_key != schedule_key,
).values(last_schedule_key=schedule_key, last_scan_at=now, updated_at=now)
```

- [ ] **Step 4: 增加 MySQL 5.7 启动兼容迁移**

在 `ClassCubeDatabase.initialize()` 的既有表检查中通过 `information_schema.columns` 检测并执行单列 `ALTER TABLE`，默认 `schedule_times_json='[]'`、`notify_wecom=1`、`last_schedule_key=''`。

- [ ] **Step 5: 运行仓储和 MySQL 测试并提交**

Run: `python -m unittest test_class_cube_repository test_class_cube_mysql`
Expected: PASS；未配置 MySQL 的集成用例允许明确 SKIP。

```bash
git add backend/app/class_cube_db_models.py backend/app/class_cube_database.py backend/app/class_cube_repository.py backend/test_class_cube_repository.py backend/test_class_cube_mysql.py
git commit -m "添加班级魔方定时任务字段"
```

### Task 3: 任务校验、到期计算与调度执行

**Files:**
- Create: `backend/app/class_cube_schedule.py`
- Modify: `backend/app/class_cube_models.py`
- Modify: `backend/app/class_cube_service.py`
- Modify: `backend/app/class_cube_scheduler.py`
- Test: `backend/test_class_cube_schedule.py`
- Test: `backend/test_class_cube_service.py`
- Test: `backend/test_class_cube_scheduler.py`

**Interfaces:**
- Produces: `normalize_schedule_times(values: list[str]) -> list[str]`
- Produces: `due_schedule_key(task: dict, now: datetime, grace_seconds: int = 59) -> str | None`
- Consumes: `repository.claim_task_schedule(task_id, schedule_key, now)`

- [ ] **Step 1: 写时间和日期失败测试**

```python
def test_normalizes_sorts_and_deduplicates_times():
    assert normalize_schedule_times(["18:00:00", "08:00:00", "08:00:00"]) == [
        "08:00:00", "18:00:00"
    ]

def test_due_key_respects_date_range_and_grace_window():
    task = {"schedule_times": ["08:00:00"], "start_date": date(2026, 8, 1),
            "end_date": date(2026, 8, 31), "last_schedule_key": ""}
    assert due_schedule_key(task, datetime(2026, 8, 1, 8, 0, 30)) == "2026-08-01T08:00:00"
    assert due_schedule_key(task, datetime(2026, 9, 1, 8, 0, 10)) is None

def test_old_task_without_times_is_never_due():
    assert due_schedule_key({"schedule_times": []}, datetime.now()) is None
```

- [ ] **Step 2: 运行测试并确认模块不存在**

Run: `python -m unittest test_class_cube_schedule`
Expected: FAIL，无法导入 `app.class_cube_schedule`。

- [ ] **Step 3: 实现纯函数调度模块**

严格使用 `datetime.strptime(value, "%H:%M:%S")` 校验时间；日期范围含首尾日期；只在时间点后的 59 秒宽限窗口内返回键，避免服务重启后补执行很久以前的任务。

- [ ] **Step 4: 扩展 Pydantic 请求模型和服务校验**

```python
schedule_times: list[str] = Field(min_length=1, max_length=24)
start_date: date | None = None
end_date: date | None = None
notify_wecom: bool = True
```

创建任务必须至少一个执行时间；更新任务仅校验传入字段。合并更新后的日期后验证 `start_date <= end_date`。

- [ ] **Step 5: 改造调度器原子认领**

`list_due_tasks()` 只读取启用任务并调用 `due_schedule_key`；确认到期后使用 `claim_task_schedule`，认领成功才提交线程池。手动 `run_task_now()` 直接执行，不调用到期判断和时间点认领。

- [ ] **Step 6: 运行服务和调度测试并提交**

Run: `python -m unittest test_class_cube_schedule test_class_cube_service test_class_cube_scheduler`
Expected: PASS。

```bash
git add backend/app/class_cube_schedule.py backend/app/class_cube_models.py backend/app/class_cube_service.py backend/app/class_cube_scheduler.py backend/test_class_cube_schedule.py backend/test_class_cube_service.py backend/test_class_cube_scheduler.py
git commit -m "改造班级魔方任务调度"
```

### Task 4: 执行汇总通知接入

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/class_cube_service.py`
- Modify: `backend/app/class_cube_scheduler.py`
- Test: `backend/test_class_cube_service.py`
- Test: `backend/test_class_cube_isolation.py`

**Interfaces:**
- Consumes: `load_class_cube_settings()`
- Consumes: `ClassCubeNotifier.send_summary(webhook_url, summary)`
- Produces: 每次自动或手动任务执行最多一条通知

- [ ] **Step 1: 写汇总和隔离失败测试**

```python
def test_task_sends_one_wecom_summary_after_multiple_items(service, notifier):
    service.run_task_now(TASK_ID, ACTOR)
    assert len(notifier.summaries) == 1
    assert notifier.summaries[0]["success"] == 2

def test_disabled_notification_and_empty_webhook_do_not_send(service, notifier):
    service.run_task_now(DISABLED_NOTIFY_TASK_ID, ACTOR)
    assert notifier.summaries == []

def test_notification_failure_keeps_checkin_success(service, failing_notifier):
    result = service.run_task_now(TASK_ID, ACTOR)
    assert result["accepted"] is True
    assert class_cube_log_contains("企业微信通知发送失败")
    assert not xxqd_log_contains("班级魔方")
```

- [ ] **Step 2: 运行测试并确认通知尚未触发**

Run: `python -m unittest test_class_cube_service test_class_cube_isolation`
Expected: FAIL，通知记录数量为 0。

- [ ] **Step 3: 注入通知器并在执行结束统一发送**

收集本次运行的账号、课程、签到项和结果，在执行循环的 `finally` 之后调用一次 `_notify_task_summary()`；捕获 `ClassCubeNotificationError`，只写班级魔方 logger，不覆盖签到结果。

- [ ] **Step 4: 运行测试并提交**

Run: `python -m unittest test_class_cube_service test_class_cube_isolation`
Expected: PASS。

```bash
git add backend/app/main.py backend/app/class_cube_service.py backend/app/class_cube_scheduler.py backend/test_class_cube_service.py backend/test_class_cube_isolation.py
git commit -m "接入班级魔方企业微信通知"
```

### Task 5: BJMF 风格前端表单与设置页面

**Files:**
- Create: `frontend/src/utils/classCubeTaskForm.js`
- Modify: `frontend/src/api/classCube.js`
- Modify: `frontend/src/composables/useClassCube.js`
- Modify: `frontend/src/views/ClassCubeOverview.vue`
- Modify: `frontend/src/components/class-cube/AutoTaskPanel.vue`
- Test: `frontend/src/utils/classCubeTaskForm.test.js`
- Test: `frontend/src/utils/classCubeUi.test.js`

**Interfaces:**
- Produces: `parseCoordinates(value: string) -> { latitude: number, longitude: number }`
- Produces: `normalizeScheduleTimes(values: string[]) -> string[]`
- Consumes: `/api/class-cube/settings`

- [ ] **Step 1: 写坐标和界面契约失败测试**

```javascript
test('parses BJMF coordinate separators', () => {
  for (const value of ['20.656756 119.196135', '20.656756,119.196135',
    '20.656756，119.196135', '20.656756|119.196135']) {
    assert.deepEqual(parseCoordinates(value), {
      latitude: 20.656756, longitude: 119.196135,
    })
  }
})

test('task UI uses enterprise WeCom only', async () => {
  const source = await readComponent('AutoTaskPanel.vue')
  assert.match(source, /发送企业微信通知/)
  assert.match(source, /https:\/\/www\.lddgo\.net\/convert\/position/)
  assert.doesNotMatch(source, /Qmsg|Server酱|QQ通知|微信通知 Key/)
})
```

- [ ] **Step 2: 运行前端测试并确认失败**

Run: `node --test src/utils/classCubeTaskForm.test.js src/utils/classCubeUi.test.js`
Expected: FAIL，缺少坐标解析模块和新表单字段。

- [ ] **Step 3: 实现坐标与时间纯函数**

```javascript
export function parseCoordinates(value) {
  const parts = String(value).trim().split(/[\s,，|]+/).filter(Boolean)
  if (parts.length !== 2) throw new Error('请输入纬度和经度')
  const [latitude, longitude] = parts.map(Number)
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90)
    throw new Error('纬度必须在 -90 到 90 之间')
  if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180)
    throw new Error('经度必须在 -180 到 180 之间')
  return { latitude, longitude }
}
```

- [ ] **Step 4: 改造系统概览设置**

管理员页面读取和保存 `class_cube_webhook_url`，输入框使用密码显示切换；普通用户只看到“已配置/未配置”。保存失败显示后端中文校验信息。

- [ ] **Step 5: 改造自动任务编辑器**

表单分为账号课程、签到参数、执行计划、通知四区；位置为单输入框；“拾取坐标”使用 `<a target="_blank" rel="noopener noreferrer">`；时间点可添加删除，日期使用两个 `el-date-picker`；保存时提交 `schedule_times/start_date/end_date/notify_wecom`。删除所有 Server 酱与 Qmsg 字段或文案。

- [ ] **Step 6: 运行测试和构建并提交**

Run: `node --test src/utils/*.test.js`
Expected: PASS。

Run: `npm.cmd run build`
Expected: Vite build success。

```bash
git add frontend/src/utils/classCubeTaskForm.js frontend/src/utils/classCubeTaskForm.test.js frontend/src/api/classCube.js frontend/src/composables/useClassCube.js frontend/src/views/ClassCubeOverview.vue frontend/src/components/class-cube/AutoTaskPanel.vue frontend/src/utils/classCubeUi.test.js
git commit -m "改造班级魔方任务填写界面"
```

### Task 6: 全量回归与交付

**Files:**
- Modify only if verification reveals a regression in files already listed above.

**Interfaces:**
- Verifies all preceding interfaces together.

- [ ] **Step 1: 运行班级魔方后端全量测试**

Run: `python -m unittest discover -s . -p "test_class_cube_*.py"`
Expected: 全部 PASS，数据库依赖测试仅在未配置测试库时 SKIP。

- [ ] **Step 2: 运行前端全量测试**

Run: `node --test src/utils/*.test.js`
Expected: 全部 PASS。

- [ ] **Step 3: 运行生产构建和差异检查**

Run: `npm.cmd run build`
Expected: `✓ built`。

Run: `git diff --check`
Expected: 无输出。

- [ ] **Step 4: 检查配置与通知隔离**

Run: `rg -n "Qmsg|Server酱|WXKey|QmsgKEY" backend/app frontend/src`
Expected: 班级魔方实现无匹配；若小小签到历史代码存在匹配，逐项确认不位于 `class_cube_*` 文件或班级魔方组件。

- [ ] **Step 5: 提交最终修正**

```bash
git add backend frontend
git commit -m "完成班级魔方定时任务与通知改造"
```

