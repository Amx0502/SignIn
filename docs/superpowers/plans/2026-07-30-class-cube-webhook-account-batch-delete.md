# 班级魔方 Webhook 与账号批量删除 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让班级魔方 Webhook 默认明文显示，账号卡片自适应保留右侧操作，并支持事务化批量删除账号。

**Architecture:** 后端沿用任务批量删除的分层方式，新增账号批量删除模型、路由、服务和仓储事务；服务层同时取消被删账号的二维码会话。前端由 `useClassCube` 暴露批量接口，账号页面通过可等待的 action prop 负责删除和刷新，账号面板管理选择与确认交互；CSS 网格保证可伸缩文本列不会挤掉状态和操作列。

**Tech Stack:** Python 3、FastAPI、Pydantic 2、SQLAlchemy 2、Vue 3、Element Plus、Vite

## Global Constraints

- Webhook 输入框直接使用 `type="text"`，移除 `show-password`，不保留隐藏按钮。
- 非管理员仍不能获取完整 Webhook，现有日志脱敏规则保持不变。
- 账号批量删除最多接受 200 个正整数 ID，重复 ID 只删除一次。
- 所有目标账号必须在当前用户作用域内；任一账号不存在或越权时整批回滚。
- 账号行不得通过横向滚动隐藏状态或操作入口。
- 不新增运行时依赖。
- 仓库忽略 `backend/test_*.py` 与 `frontend/src/**/*.test.js`；测试文件只用于本地 TDD，最终验证后删除，不纳入提交。

---

### Task 1: 后端事务化账号批量删除

**Files:**
- Modify: `backend/app/class_cube_models.py`
- Modify: `backend/app/class_cube_repository.py`
- Modify: `backend/app/class_cube_service.py`
- Modify: `backend/app/class_cube_router.py`
- Test: `backend/test_class_cube_account_batch_delete.py`（本地临时测试）

**Interfaces:**
- Consumes: 现有 `ClassCubeNotFound`、`_actor_scope(actor)`、`_qr_targets` 和数据库 session 上下文。
- Produces: `ClassCubeAccountBatchDelete(ids: list[int])`、`ClassCubeRepository.delete_accounts(account_ids, actor_user_id, is_admin) -> int`、`ClassCubeService.batch_delete_accounts(account_ids, actor) -> int`、`POST /api/class-cube/accounts/batch-delete`。

- [ ] **Step 1: 写批量模型、仓储事务和二维码会话清理的失败测试**

在 `backend/test_class_cube_account_batch_delete.py` 中覆盖：

```python
import unittest
from unittest.mock import Mock

from app.class_cube_models import ClassCubeAccountBatchDelete
from app.class_cube_repository import ClassCubeNotFound
from app.class_cube_service import ClassCubeService


class AccountBatchDeleteContractTest(unittest.TestCase):
    def test_model_rejects_empty_and_non_positive_ids(self):
        with self.assertRaises(ValueError):
            ClassCubeAccountBatchDelete(ids=[])
        with self.assertRaises(ValueError):
            ClassCubeAccountBatchDelete(ids=[0])

    def test_service_deduplicates_ids_and_cancels_matching_qr_targets(self):
        service = object.__new__(ClassCubeService)
        service.repository = Mock()
        service.repository.delete_accounts.return_value = 2
        service._qr_lock = __import__("threading").RLock()
        first = Mock(account_id=11)
        second = Mock(account_id=12)
        untouched = Mock(account_id=99)
        service._qr_targets = {"a": first, "b": second, "c": untouched}
        service._actor_scope = Mock(return_value=(7, False))
        service._cancel_targets = Mock()

        deleted = service.batch_delete_accounts([12, 11, 12], {"id": 7})

        self.assertEqual(deleted, 2)
        service.repository.delete_accounts.assert_called_once_with(
            [11, 12], 7, False
        )
        self.assertEqual(service._qr_targets, {"c": untouched})
        cancelled = service._cancel_targets.call_args.args[0]
        self.assertEqual(set(cancelled), {"a", "b"})

    def test_repository_failure_leaves_qr_targets_intact(self):
        service = object.__new__(ClassCubeService)
        service.repository = Mock()
        service.repository.delete_accounts.side_effect = ClassCubeNotFound(
            "班级魔方账号不存在"
        )
        service._qr_lock = __import__("threading").RLock()
        target = Mock(account_id=11)
        service._qr_targets = {"a": target}
        service._actor_scope = Mock(return_value=(7, False))
        service._cancel_targets = Mock()

        with self.assertRaises(ClassCubeNotFound):
            service.batch_delete_accounts([11], {"id": 7})

        self.assertEqual(service._qr_targets, {"a": target})
        service._cancel_targets.assert_not_called()
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `Set-Location backend; python -m unittest test_class_cube_account_batch_delete.py -v`

Expected: FAIL，提示无法导入 `ClassCubeAccountBatchDelete` 或服务缺少 `batch_delete_accounts`。

- [ ] **Step 3: 实现请求模型**

在 `class_cube_models.py` 导入 `Annotated` 并新增：

```python
class ClassCubeAccountBatchDelete(BaseModel):
    ids: list[Annotated[int, Field(gt=0)]] = Field(
        min_length=1,
        max_length=200,
    )
```

- [ ] **Step 4: 实现仓储层单事务删除**

在 `ClassCubeRepository` 新增 `delete_accounts`。先用 `sorted(set(account_ids))` 规范化 ID，再在同一个 session 中按 ID 和用户作用域查询全部账号；查询数量不等于目标数量时抛出 `ClassCubeNotFound("班级魔方账号不存在")`，否则逐行 `session.delete(row)`、`session.flush()` 并返回数量。普通用户查询必须附加 `ClassCubeAccountRow.owner_user_id == actor_user_id`，管理员不附加该条件。

- [ ] **Step 5: 实现服务层批量删除与二维码会话清理**

在 `ClassCubeService` 新增：

```python
def batch_delete_accounts(self, account_ids, actor):
    normalized_ids = sorted(set(account_ids))
    actor_user_id, is_admin = self._actor_scope(actor)
    with self._qr_lock:
        deleted = self.repository.delete_accounts(
            normalized_ids,
            actor_user_id,
            is_admin,
        )
        deleted_ids = set(normalized_ids)
        cancelled_targets = {
            token: target
            for token, target in self._qr_targets.items()
            if target.account_id in deleted_ids
        }
        for token in cancelled_targets:
            self._qr_targets.pop(token, None)
    self._cancel_targets(cancelled_targets)
    return deleted
```

- [ ] **Step 6: 暴露批量删除路由**

在 `class_cube_router.py` 导入 `ClassCubeAccountBatchDelete`，并在单账号动态路由附近新增：

```python
@router.post("/accounts/batch-delete")
def batch_delete_accounts(
    payload: ClassCubeAccountBatchDelete,
    request: Request,
    actor=Depends(auth_dependency),
):
    return _invoke(
        request,
        _service(request).batch_delete_accounts,
        payload.ids,
        actor,
    )
```

- [ ] **Step 7: 运行后端测试**

Run: `Set-Location backend; python -m unittest test_class_cube_account_batch_delete.py -v`

Expected: 3 tests PASS。

- [ ] **Step 8: 提交后端实现**

```powershell
git add backend/app/class_cube_models.py backend/app/class_cube_repository.py backend/app/class_cube_service.py backend/app/class_cube_router.py
git commit -m "添加班级魔方账号批量删除接口"
```

---

### Task 2: 前端批量删除数据流

**Files:**
- Modify: `frontend/src/api/classCube.js`
- Modify: `frontend/src/composables/useClassCube.js`
- Modify: `frontend/src/views/ClassCubeAccounts.vue`
- Test: `frontend/src/views/ClassCubeAccounts.test.js`（本地临时测试）

**Interfaces:**
- Consumes: `POST /api/class-cube/accounts/batch-delete`，请求 `{ ids: number[] }`，响应 `data: number`。
- Produces: `classCubeApi.batchDeleteAccounts(ids)`、`useClassCube().deleteAccounts(ids)`、传给 `AccountCheckinPanel` 的 `batchDeleteAccountsAction(ids) -> Promise<boolean>`。

- [ ] **Step 1: 写前端数据流失败测试**

在 `ClassCubeAccounts.test.js` 使用 Node 内置断言读取源码，验证 API、composable 和页面事件接线：

```js
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api = fs.readFileSync(new URL('../api/classCube.js', import.meta.url), 'utf8')
const composable = fs.readFileSync(new URL('../composables/useClassCube.js', import.meta.url), 'utf8')
const view = fs.readFileSync(new URL('./ClassCubeAccounts.vue', import.meta.url), 'utf8')

assert.match(api, /batchDeleteAccounts:\s*ids\s*=>/)
assert.match(api, /accounts\/batch-delete/)
assert.match(composable, /async function deleteAccounts\(ids\)/)
assert.match(view, /:batch-delete-accounts-action="removeAccounts"/)
assert.match(view, /async function removeAccounts\(ids\)/)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `Set-Location frontend; node src/views/ClassCubeAccounts.test.js`

Expected: FAIL，缺少 `batchDeleteAccounts`。

- [ ] **Step 3: 添加 API 与 composable 方法**

在 `classCube.js` 新增：

```js
batchDeleteAccounts: ids =>
  instance.post(`${root}/accounts/batch-delete`, { ids }),
```

在 `useClassCube.js` 新增：

```js
async function deleteAccounts(ids) {
  if (!ids.length) return 0
  const response = await api.batchDeleteAccounts(ids)
  return responseData(response, 0)
}
```

并在返回对象中暴露 `deleteAccounts`。

- [ ] **Step 4: 页面处理删除后的完整刷新**

在 `ClassCubeAccounts.vue` 解构 `deleteAccounts`，向面板传入 `:batch-delete-accounts-action="removeAccounts"`，并新增：

```js
async function refreshAfterAccountDelete() {
  await Promise.all([loadAccounts(), loadTasks(), loadRuns()])
  await selectAccount(selectedAccountId.value)
}

async function removeAccounts(ids) {
  const deleted = await safely(() => deleteAccounts(ids))
  if (deleted === null) return false
  await refreshAfterAccountDelete()
  ElMessage.success(`已删除 ${deleted} 个账号`)
  return true
}
```

让现有 `removeAccount` 也调用 `refreshAfterAccountDelete()`，避免单删与批量删除刷新行为分叉。

- [ ] **Step 5: 运行前端数据流测试**

Run: `Set-Location frontend; node src/views/ClassCubeAccounts.test.js`

Expected: PASS，无输出。

- [ ] **Step 6: 提交前端数据流**

```powershell
git add frontend/src/api/classCube.js frontend/src/composables/useClassCube.js frontend/src/views/ClassCubeAccounts.vue
git commit -m "接入班级魔方账号批量删除"
```

---

### Task 3: 账号选择交互、自适应布局与 Webhook 明文

**Files:**
- Modify: `frontend/src/components/class-cube/AccountCheckinPanel.vue`
- Modify: `frontend/src/views/ClassCubeOverview.vue`
- Test: `frontend/src/components/class-cube/AccountCheckinPanel.test.js`（本地临时测试）

**Interfaces:**
- Consumes: `accounts: Account[]`、面板现有 `delete-account` 事件、`batchDeleteAccountsAction(ids: number[]) -> Promise<boolean>`。
- Produces: 账号行固定显示复选框、状态和操作按钮；Webhook 文本输入框。

- [ ] **Step 1: 写模板与样式失败测试**

在 `AccountCheckinPanel.test.js` 中验证：

```js
import assert from 'node:assert/strict'
import fs from 'node:fs'

const panel = fs.readFileSync(new URL('./AccountCheckinPanel.vue', import.meta.url), 'utf8')
const overview = fs.readFileSync(new URL('../../views/ClassCubeOverview.vue', import.meta.url), 'utf8')

assert.match(panel, /selectedAccountIds/)
assert.match(panel, /批量删除/)
assert.match(panel, /batchDeleteAccountsAction/)
assert.match(panel, /grid-template-columns:\s*auto\s+39px\s+minmax\(0,\s*1fr\)\s+auto\s+auto/)
assert.match(panel, /\.account-row\s*>\s*\.el-tag/)
assert.match(overview, /type="text"/)
assert.doesNotMatch(overview, /show-password/)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `Set-Location frontend; node src/components/class-cube/AccountCheckinPanel.test.js`

Expected: FAIL，缺少 `selectedAccountIds`。

- [ ] **Step 3: 实现批量选择状态与确认**

在 `AccountCheckinPanel.vue`：

- 将 `Delete` 加入图标导入。
- 在 props 中增加必填的 `batchDeleteAccountsAction: Function`。
- 新增 `const selectedAccountIds = ref(new Set())` 与 `const batchDeleting = ref(false)`。
- 监听 `props.accounts.map(account => account.id)`，过滤已不存在的选择。
- 复选框使用 `:model-value="selectedAccountIds.has(account.id)"`，点击时 `.stop`，通过复制新 `Set` 更新选择。
- 标题区添加危险按钮，文本为未选中时“批量删除”、选中时“批量删除（N）”，未选中或请求中禁用。
- 确认提示明确删除账号及关联课程、签到项和任务；确认后调用 `await props.batchDeleteAccountsAction([...selectedAccountIds.value])`。action 返回 `true` 时清空选择，返回 `false` 时保留选择；使用 `batchDeleting` 阻止重复提交。

- [ ] **Step 4: 改造账号行自适应布局**

将账号行单独改为：

```css
.account-row {
  display: grid;
  grid-template-columns: auto 39px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
}
.account-row > .el-checkbox,
.account-row > .el-tag,
.account-row > .el-dropdown {
  min-width: 0;
  flex: none;
}
.account-row > .el-tag {
  justify-self: end;
}
```

保持 `.account-main { min-width: 0; }` 和文本省略号；将 `.account-list` 设置为 `overflow-y: auto; overflow-x: hidden`。把工作区左栏最小宽度提高到足以容纳五列，并使用 `grid-template-columns: minmax(330px, .85fr) minmax(0, 1.5fr)`；现有 `max-width:1024px` 断点继续改为单列。

- [ ] **Step 5: 将 Webhook 输入框改为明文**

在 `ClassCubeOverview.vue` 把：

```vue
type="password"
show-password
```

改为：

```vue
type="text"
```

不改设置接口、保存逻辑、管理员判断或后端日志脱敏。

- [ ] **Step 6: 运行模板与样式测试**

Run: `Set-Location frontend; node src/components/class-cube/AccountCheckinPanel.test.js`

Expected: PASS，无输出。

- [ ] **Step 7: 构建前端**

Run: `Set-Location frontend; npm run build`

Expected: Vite 构建成功，无 Vue 模板编译错误。

- [ ] **Step 8: 提交界面改动**

```powershell
git add frontend/src/components/class-cube/AccountCheckinPanel.vue frontend/src/views/ClassCubeOverview.vue
git commit -m "优化班级魔方账号管理与企微显示"
```

---

### Task 4: 集成验证与临时测试清理

**Files:**
- Delete: `backend/test_class_cube_account_batch_delete.py`
- Delete: `frontend/src/views/ClassCubeAccounts.test.js`
- Delete: `frontend/src/components/class-cube/AccountCheckinPanel.test.js`

**Interfaces:**
- Consumes: 前三项任务的完整实现。
- Produces: 无临时测试残留、可构建的最终工作树。

- [ ] **Step 1: 运行全部临时测试与前端构建**

```powershell
Set-Location backend
python -m unittest test_class_cube_account_batch_delete.py -v
Set-Location ..\frontend
node src/views/ClassCubeAccounts.test.js
node src/components/class-cube/AccountCheckinPanel.test.js
npm run build
Set-Location ..
```

Expected: Python 3 tests PASS；两个 Node 源码断言通过；Vite 构建成功。

- [ ] **Step 2: 检查安全边界和差异**

Run:

```powershell
rg -n "type=\"password\"|show-password|type=\"text\"" frontend/src/views/ClassCubeOverview.vue
rg -n "class_cube_webhook_url|_webhook" backend/app/class_cube_service.py backend/app/class_cube_logging.py
git diff --check
git status --short
```

Expected: Overview 只保留 `type="text"`；非管理员移除 Webhook 与日志脱敏代码仍存在；`git diff --check` 无输出。

- [ ] **Step 3: 删除本地临时测试文件**

使用补丁删除三个被 `.gitignore` 忽略的临时测试文件，并确认：

Run: `git status --short --ignored | rg "test_class_cube_account_batch_delete|ClassCubeAccounts.test|AccountCheckinPanel.test"`

Expected: 无输出。

- [ ] **Step 4: 最终检查提交范围**

Run: `git status --short; git log -5 --oneline`

Expected: 工作树干净；最近提交依次包含后端批量接口、前端数据流和界面改动。
