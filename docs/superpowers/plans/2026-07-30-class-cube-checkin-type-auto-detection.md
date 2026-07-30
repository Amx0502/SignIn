# 班级魔方签到类型自动识别与兼容提交 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自动识别班级魔方二维码、GPS、GPS + 拍照和密码签到，并按 AutoCheckBJMF/FuckBJMF 的兼容协议切换界面和提交参数。

**Architecture:** 在 `class_cube_parser.py` 集中处理远端标记、证据优先级和无表单合成契约；在提交服务中统一保留通用参数并移除 GPS + 拍照的本地上传依赖；前端只根据后端输出的 `mode` 渲染参数表单。该功能跨解析、执行和展示三层，但共享同一个签到契约，作为一个实施计划完成。

**Tech Stack:** Python 3、FastAPI 服务层、BeautifulSoup、SQLAlchemy 持久化表单模式、Vue 3、Element Plus、Vite。

## Global Constraints

- GPS/二维码兼容提交地址为 `/student/punchs/course/{course_id}/{item_id}`；远端真实 POST 表单 action 始终优先。
- 通用字段为 `id`、`lat`、`lng`、`acc`、`res` 和 `gps_addr`。
- 密码签到标记为 `punch_pwd_frm_ID`，提交字段默认使用 `pwd`。
- GPS + 拍照不上传本地文件；`res` 优先使用远端值，否则发送空字符串。
- 单独存在 `res`、`lat`、`lng`、`acc` 等通用隐藏字段不能覆盖列表页的密码或二维码标记。
- 无法确认类型时使用 `unknown`，不发送试探性 POST。
- 不增加数据库表，不恢复测试专用文件，不记录 Cookie、签到密码或非空 `res`。

---

### Task 1: 远端标记识别与合成提交契约

**Files:**
- Modify: `backend/app/class_cube_parser.py:9-14`
- Modify: `backend/app/class_cube_parser.py:133-234`
- Modify: `backend/app/class_cube_parser.py:235-415`
- Modify: `backend/app/class_cube_parser.py:440-517`
- Modify: `backend/app/class_cube_parser.py:548-605`
- Modify: `backend/app/class_cube_parser.py:687-741`

**Interfaces:**
- Consumes: `ParsedItem(remote_item_id, course_id, remote_module, detail_url, mode_hint)`。
- Produces: `_password_item_id(tag: Tag) -> str`、`_tag_has_photo_marker(tag: Tag) -> bool`，以及带正确 `mode`、action、字段名和通用隐藏字段的 `ParsedForm`。

- [ ] **Step 1: 运行失败探针，固定现有缺陷**

Run:

```powershell
@'
import sys
sys.path.insert(0, r"backend")
from app.class_cube_parser import parse_checkin_form, parse_checkin_items

base = "https://bjmf.k8n.cn/student/course/140242/punchs"
password_html = """
<form id="punch_pwd_frm_5458157" method="post">
  <input type="hidden" name="id" value="5458157">
  <input type="hidden" name="lat"><input type="hidden" name="lng">
  <input type="hidden" name="acc"><input type="hidden" name="res">
  <input type="hidden" name="gps_addr"><input type="text" name="pwd">
</form>
"""
password_items = parse_checkin_items(password_html, "140242", "punchs", base)
assert len(password_items) == 1
assert password_items[0].mode_hint == "password"

gps_html = '<button onclick="punch_gps(5458155)">GPS</button>'
gps_item = parse_checkin_items(gps_html, "140242", "punchs", base)[0]
gps_form = parse_checkin_form(gps_html, base, gps_item)
assert gps_form.action.endswith("/student/punchs/course/140242/5458155")
'@ | python -
```

Expected: FAIL because密码标记没有生成签到项；继续单独运行 GPS 断言时，action 错误地包含 `/student/punch_gps/course/`。

- [ ] **Step 2: 增加密码标记和拍照显式证据解析**

在 `class_cube_parser.py` 中加入：

```python
def _password_item_id(tag: Tag) -> str:
    for attribute in ("id", "data-target", "data-id", "href"):
        value = _attribute_text(tag.get(attribute))
        match = re.search(
            r"(?:^|[#\s])punch_pwd_frm_([A-Za-z0-9_.-]+)(?:$|[\s])",
            value,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
    return ""


def _tag_has_photo_marker(tag: Tag) -> bool:
    if tag.find("input", attrs={"type": "file"}):
        return True
    if (
        _attribute_text(tag.get("data-mode")).lower() == "gps_photo"
        or bool(_attribute_text(tag.get("data-upload-action")))
    ):
        return True
    return "拍照" in tag.get_text(" ", strip=True)
```

在 `parse_checkin_items()` 的标签循环中使用 `_password_item_id(tag)` 添加 `mode_hint="password"` 的签到项；`_item_mode_hint()` 也需要优先返回 `password`。GPS 标记所在标签如果 `_tag_has_photo_marker(tag)` 为真，则列表提示使用 `gps_photo`，否则使用 `gps`。

- [ ] **Step 3: 实现类型证据优先级**

将 `parse_checkin_form()` 的 mode 判断改为以下等价顺序：

```python
if password_field or item.mode_hint == "password":
    mode = "password"
    password_field = password_field or "pwd"
elif item.mode_hint == "qr" or _has_qr_marker(soup, html):
    mode = "qr"
elif item.mode_hint == "gps_photo" or (
    has_gps_field
    and isinstance(form, Tag)
    and _tag_has_photo_marker(form)
):
    mode = "gps_photo"
elif item.mode_hint == "gps" or has_gps_field:
    mode = "gps"
else:
    mode = "unknown"
```

这一步必须确保列表页密码/二维码提示不会被详情页的通用 GPS 隐藏字段覆盖。

- [ ] **Step 4: 扩展表单选择和无表单合成契约**

让 `_select_checkin_form()` 同时查找 `punchcard_{id}` 与 `punch_pwd_frm_{id}` 容器。让 `_synthetic_contract()` 支持密码标记，并使所有合成契约调用：

```python
_canonical_submit_url(response_url, "punchs", item)
```

真实 POST 表单没有显式 `action` 时，也使用上述 item 级兼容地址，不能把列表页 URL 当作提交地址。

合成成功后设置：

```python
hidden_fields.update({
    "lat": "",
    "lng": "",
    "acc": "",
    "res": "",
    "gps_addr": "",
})
item_id_field = "id"
photo_resource_field = "res"
if mode in {"gps", "gps_photo"}:
    latitude_field = "lat"
    longitude_field = "lng"
    accuracy_field = "acc"
    gps_address_field = "gps_addr"
if mode == "password":
    password_field = "pwd"
```

- [ ] **Step 5: 运行通过探针**

重复 Step 1，并增加以下断言：

```python
password_form = parse_checkin_form(password_html, base, password_items[0])
assert password_form.mode == "password"
assert password_form.password_field == "pwd"
assert password_form.hidden_fields["res"] == ""

qr_html = '<div id="punchcard_5458156">扫码签到</div>'
qr_item = parse_checkin_items(qr_html, "140242", "punchs", base)[0]
qr_form = parse_checkin_form(qr_html, base, qr_item)
assert qr_form.mode == "qr"
assert qr_form.action.endswith("/student/punchs/course/140242/5458156")
assert set(("lat", "lng", "acc", "res", "gps_addr")) <= set(qr_form.hidden_fields)
```

Expected: PASS，且探针不发出任何网络请求。

- [ ] **Step 6: 提交解析器改动**

```powershell
git add backend/app/class_cube_parser.py
git commit -m "修复班级魔方签到类型识别"
```

---

### Task 2: GPS 拍照兼容提交与密码安全处理

**Files:**
- Modify: `backend/app/class_cube_service.py:126-195`
- Modify: `backend/app/class_cube_service.py:854-881`
- Modify: `backend/app/class_cube_service.py:1030-1038`
- Modify: `backend/app/class_cube_service.py:1338-1345`
- Modify: `backend/app/class_cube_service.py:1502-1636`
- Modify: `backend/app/class_cube_client.py:251-322`

**Interfaces:**
- Consumes: Task 1 产生的 `ParsedForm`，特别是 `photo_resource_field="res"`、`password_field="pwd"` 和通用 `hidden_fields`。
- Produces: `build_submission_fields(form, parameters, remote_item_id, remote_photo_value="") -> dict[str, str]`；GPS + 拍照无需 `photo_path` 即可执行，客户端保留空 `res`。

- [ ] **Step 1: 运行失败探针，证明空 res 尚未进入字段**

Run:

```powershell
@'
import sys
sys.path.insert(0, r"backend")
from app.class_cube_parser import ParsedForm
from app.class_cube_service import CheckinParameters, build_submission_fields

form = ParsedForm(
    action="https://bjmf.k8n.cn/student/punchs/course/1/2",
    method="post",
    mode="gps_photo",
    hidden_fields={},
    item_id_field="id",
    latitude_field="lat",
    longitude_field="lng",
    accuracy_field="acc",
    gps_address_field="gps_addr",
    photo_resource_field="res",
    submit_capable=True,
)
fields = build_submission_fields(
    form,
    CheckinParameters(latitude=26.03, longitude=119.21, accuracy=20),
    remote_item_id="2",
)
assert fields["res"] == ""
'@ | python -
```

Expected: FAIL with `KeyError: 'res'`。

- [ ] **Step 2: 让字段构造器始终保留 GPS + 拍照的 res**

将现有真值判断改成：

```python
if (
    form.mode == "gps_photo"
    and form.photo_resource_field
    and (
        remote_photo_value
        or form.photo_resource_field not in form.hidden_fields
    )
):
    fields[form.photo_resource_field] = remote_photo_value
```

这样真实表单已有非空 `res` 时不会被空值覆盖；缺少 `res` 字段的合成/兼容表单仍会显式生成 `res=""`。

- [ ] **Step 3: 停止客户端删除空 res**

删除 `ClassCubeClient.submit_form()` 中以下逻辑：

```python
if (
    form.photo_resource_field
    and not payload.get(form.photo_resource_field)
    and not fields.get(form.photo_resource_field)
):
    payload.pop(form.photo_resource_field, None)
```

保留 `payload = form.hidden_fields + fields` 的合并行为，确保二维码、GPS 和 GPS + 拍照都能发送 `res=""`。

- [ ] **Step 4: 移除 GPS + 拍照的本地文件要求**

在 `manual_checkin()` 中删除 `photo_path`、`remote_photo_value`、`owned_photo` 和 `client.upload_photo()` 分支。字段构造与提交变成：

```python
fields = build_submission_fields(
    form,
    parameters,
    remote_item_id=str(item["remote_item_id"]),
)
result = self.client.submit_form(
    account["cookie"],
    form,
    fields,
)
```

自动任务调用 `manual_checkin()` 时不再传入 `photo_path`。

- [ ] **Step 5: 清理摘要中的照片依赖并遮蔽密码**

`_task_parameters()` 与 `_manual_parameters()` 将 `image_count` 固定为 `0`。`_parameter_log_parts()` 不得拼接密码原文，改成：

```python
if parameters.get("password"):
    parts.append("密码：已配置")
```

- [ ] **Step 6: 运行兼容字段探针**

重复 Step 1，并增加密码断言：

```python
password_form = ParsedForm(
    action="https://bjmf.k8n.cn/student/punchs/course/1/3",
    method="post",
    mode="password",
    hidden_fields={"lat": "", "lng": "", "acc": "", "res": "", "gps_addr": ""},
    item_id_field="id",
    password_field="pwd",
    submit_capable=True,
)
password_fields = build_submission_fields(
    password_form,
    CheckinParameters(password="2468"),
    remote_item_id="3",
)
merged = {**password_form.hidden_fields, **password_fields}
assert merged["pwd"] == "2468"
assert set(("id", "lat", "lng", "acc", "res", "gps_addr", "pwd")) <= set(merged)
```

Expected: PASS。

- [ ] **Step 7: 检查不再存在上传阻断文案**

Run:

```powershell
rg -n "请上传签到照片|无法识别远端照片上传方式|client\\.upload_photo" backend/app/class_cube_service.py
```

Expected: 无输出。

- [ ] **Step 8: 提交提交链路改动**

```powershell
git add backend/app/class_cube_service.py backend/app/class_cube_client.py
git commit -m "兼容班级魔方GPS拍照与密码提交"
```

---

### Task 3: 按 mode 自动切换前端参数界面

**Files:**
- Modify: `frontend/src/components/class-cube/AccountCheckinPanel.vue:112-140`
- Modify: `frontend/src/components/class-cube/AccountCheckinPanel.vue:159-220`
- Modify: `frontend/src/components/class-cube/AccountCheckinPanel.vue:295-341`
- Modify: `frontend/src/components/class-cube/AutoTaskPanel.vue:32-39`
- Modify: `frontend/src/components/class-cube/AutoTaskPanel.vue:85-100`
- Modify: `frontend/src/components/class-cube/AutoTaskPanel.vue:135-205`
- Modify: `frontend/src/views/ClassCubeAccounts.vue:1-12`
- Modify: `frontend/src/views/ClassCubeTasks.vue:1-24`

**Interfaces:**
- Consumes: 后端签到项 `mode`，取值为 `qr | gps | gps_photo | password | unknown`。
- Produces: 不含 `photo_path` 的手动签到和自动任务请求；GPS + 拍照显示兼容提示，未知类型禁止提交。

- [ ] **Step 1: 记录当前前端失败条件**

Run:

```powershell
rg -n "签到照片|TaskImageUpload|payload\\.photo_path|upload-photo-action" frontend/src/components/class-cube/AccountCheckinPanel.vue frontend/src/components/class-cube/AutoTaskPanel.vue frontend/src/views/ClassCubeAccounts.vue frontend/src/views/ClassCubeTasks.vue
```

Expected: 找到手动签到照片控件、自动任务默认照片控件、`payload.photo_path` 和两个上传 action 绑定。

- [ ] **Step 2: 改造手动签到界面**

在 `AccountCheckinPanel.vue` 中：

- 删除 `TaskImageUpload`、`createUploadGenerationGuard`、`uploadPhotoAction`、`photoFiles`、`photo_path`、`uploadPhoto()`、`removePhoto()` 和上传身份监听逻辑。
- 删除 `payload.photo_path`。
- 将 GPS + 拍照区域替换为：

```vue
<el-alert
  v-if="selectedItem.mode === 'gps_photo'"
  title="兼容模式将自动附带 res，无需上传本地照片。"
  type="info"
  :closable="false"
  show-icon
/>
```

- 为 `unknown` 增加重新同步提示，并给执行按钮添加：

```vue
:disabled="selectedItem.mode === 'unknown'"
```

- 将等待参数提示中的“位置、照片或密码”改为“位置或密码”。

- [ ] **Step 3: 移除自动任务照片交互**

在 `AutoTaskPanel.vue` 中删除默认照片表单项、照片标签、`TaskImageUpload` 导入、`uploadPhotoAction` prop、`photoFiles`、`uploadPhoto()` 和 `removePhoto()`。保留旧任务模型中的 `photo_path` 字段兼容读取，但界面不再新增或要求它。

- [ ] **Step 4: 清理页面上传 action 绑定**

在 `ClassCubeAccounts.vue` 和 `ClassCubeTasks.vue` 中移除 `:upload-photo-action="uploadPhoto"`，并从对应的 `useClassCube()` 解构中删除 `uploadPhoto`。不删除公共上传 API，以免影响可能存在的外部调用。

- [ ] **Step 5: 验证模板不再依赖照片上传**

Run:

```powershell
rg -n "签到照片|TaskImageUpload|payload\\.photo_path|upload-photo-action" frontend/src/components/class-cube/AccountCheckinPanel.vue frontend/src/components/class-cube/AutoTaskPanel.vue frontend/src/views/ClassCubeAccounts.vue frontend/src/views/ClassCubeTasks.vue
```

Expected: 无输出。

Run:

```powershell
rg -n "兼容模式将自动附带 res|selectedItem\\.mode === 'unknown'" frontend/src/components/class-cube/AccountCheckinPanel.vue
```

Expected: 同时找到兼容提示和未知类型分支。

- [ ] **Step 6: 构建前端**

Run:

```powershell
npm.cmd run build
```

Working directory: `frontend`

Expected: Vite production build succeeds with exit code 0。

- [ ] **Step 7: 提交前端改动**

```powershell
git add frontend/src/components/class-cube/AccountCheckinPanel.vue frontend/src/components/class-cube/AutoTaskPanel.vue frontend/src/views/ClassCubeAccounts.vue frontend/src/views/ClassCubeTasks.vue
git commit -m "按签到类型切换班级魔方参数界面"
```

---

### Task 4: 全链路回归验证

**Files:**
- Verify: `backend/app/class_cube_parser.py`
- Verify: `backend/app/class_cube_service.py`
- Verify: `backend/app/class_cube_client.py`
- Verify: `frontend/src/components/class-cube/AccountCheckinPanel.vue`
- Verify: `frontend/src/components/class-cube/AutoTaskPanel.vue`
- Verify: `frontend/src/views/ClassCubeAccounts.vue`
- Verify: `frontend/src/views/ClassCubeTasks.vue`

**Interfaces:**
- Consumes: Tasks 1–3 的最终实现。
- Produces: 无新增文件的验证证据和干净的工作区。

- [ ] **Step 1: 运行四类型内存回归探针**

将 Task 1 与 Task 2 的断言合并运行，并额外验证：

```python
unknown_html = "<div>普通课程内容</div>"
assert parse_checkin_items(
    unknown_html,
    "140242",
    "punchs",
    base,
) == []
```

Expected: 所有断言 PASS，且没有网络请求。

- [ ] **Step 2: 编译后端**

Run:

```powershell
python -m compileall app
```

Working directory: `backend`

Expected: 所有生产 Python 模块编译成功。

- [ ] **Step 3: 再次构建前端**

Run:

```powershell
npm.cmd run build
```

Working directory: `frontend`

Expected: exit code 0。

- [ ] **Step 4: 检查敏感信息和旧照片依赖**

Run:

```powershell
rg -n "密码：\\{password\\}|请上传签到照片|无法识别远端照片上传方式|payload\\.photo_path" backend/app/class_cube_service.py frontend/src/components/class-cube/AccountCheckinPanel.vue
```

Expected: 无输出。

- [ ] **Step 5: 检查差异质量与提交历史**

Run:

```powershell
git diff --check
git status --short
git log -5 --oneline
```

Expected: `git diff --check` 无输出；工作区无未提交文件；最近提交依次覆盖解析器、提交链路和前端界面。
