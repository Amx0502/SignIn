<template>
  <div class="page-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>任务管理</span>
          <div class="task-toolbar">
            <el-tag type="info" size="small"
              >{{ allTasks.length }} 个任务</el-tag
            >
            <el-button
              type="danger"
              size="small"
              :icon="Delete"
              :disabled="selectedTaskKeys.size === 0 || batchDeleting"
              :loading="batchDeleting"
              @click="deleteSelectedTasks"
              >批量删除({{ selectedTaskKeys.size }})</el-button
            >
            <el-button
              type="primary"
              size="small"
              @click="openCreateTask"
              >新建任务</el-button
            >
          </div>
        </div>
      </template>

      <div v-if="allTasks.length === 0" class="empty-state">
        <el-empty description="系统中暂无任务" :image-size="80" />
      </div>

      <div v-else class="task-list">
        <div
          v-for="task in allTasks"
          :key="`${task.accountIndex}-${task.taskIndex}`"
          class="task-wrapper"
        >
          <div class="task-card">
            <div class="task-main">
              <div class="task-title-row">
                <el-checkbox
                  :model-value="selectedTaskKeys.has(getTaskKey(task))"
                  :aria-label="`选择任务 ${task.title}`"
                  @change="(checked) => toggleTaskSelection(task, checked)"
                />
                <el-tag :type="taskStatusType(task)" size="small">{{
                  taskStatusText(task)
                }}</el-tag>
                <span class="task-title">{{ task.title }}</span>
                <el-tag
                  :type="task.mode === 'image' ? 'warning' : 'primary'"
                  size="small"
                >
                  {{ task.mode === "image" ? "图片签到" : "普通签到" }}
                </el-tag>
              </div>
              <div class="task-info">
                <span
                  ><el-icon><User /></el-icon>{{ task.accountName }}</span
                >
                <span
                  ><el-icon><List /></el-icon>项目{{ task.index }}</span
                >
                <span
                  ><el-icon><Clock /></el-icon
                  >{{ (task.times || []).join(", ") }}</span
                >
                <span>
                  <el-icon><Calendar /></el-icon>
                  {{
                    task.date_mode === "specific"
                      ? `指定 ${(task.run_dates || []).length} 天`
                      : "每天执行"
                  }}
                </span>
                <span v-if="task.text" class="text-content">
                  <el-icon><ChatLineSquare /></el-icon>
                  <el-tooltip
                    :content="task.text"
                    placement="top"
                    :max-width="300"
                  >
                    <span>{{
                      task.text.length > 15
                        ? task.text.substring(0, 15) + "..."
                        : task.text
                    }}</span>
                  </el-tooltip>
                </span>
                <span v-if="task.use_location"
                  ><el-icon><MapLocation /></el-icon>{{ taskLocationLabel(task) }}</span
                >
                <span v-if="task.fill_name"
                  ><el-icon><User /></el-icon>{{ task.fill_name }}</span
                >
                <span v-if="task.pic_path && task.pic_path.length"
                  ><el-icon><Picture /></el-icon
                  >{{ task.pic_path.length }}张图</span
                >
                <span v-if="task.skip_weekends"
                  ><el-icon><Calendar /></el-icon>周末跳过</span
                >
                <span v-if="isAdmin && task.notify_wechat !== false"
                  ><el-icon><VideoPlay /></el-icon>企微通知</span
                >
                <span
                  v-if="task.completed_at"
                  :title="formatDateTime(task.completed_scheduled_for)"
                >
                  <el-icon><Calendar /></el-icon>完成于
                  {{ formatDateTime(task.completed_at) }}
                </span>
              </div>
              <div class="mobile-task-summary">
                <span><el-icon><User /></el-icon>{{ task.accountName }}</span>
                <span><el-icon><List /></el-icon>项目{{ task.index }}</span>
                <span>
                  <el-icon><Clock /></el-icon>
                  {{ (task.times || [])[0] || "未设置" }}
                  <small v-if="(task.times || []).length > 1"
                    >+{{ task.times.length - 1 }}</small
                  >
                </span>
                <span>
                  <el-icon><Calendar /></el-icon>
                  {{
                    task.date_mode === "specific"
                      ? `${(task.run_dates || []).length} 天`
                      : "每天"
                  }}
                </span>
                <span v-if="task.use_location"
                  ><el-icon><MapLocation /></el-icon>{{ taskLocationLabel(task) }}</span
                >
                <span v-if="task.pic_path && task.pic_path.length"
                  ><el-icon><Picture /></el-icon>{{ task.pic_path.length }} 图</span
                >
                <span v-if="isAdmin && task.notify_wechat !== false"
                  ><el-icon><VideoPlay /></el-icon>企微</span
                >
              </div>
            </div>
            <div class="task-actions">
              <el-button
                :type="isEditing(task) ? 'info' : 'primary'"
                size="small"
                :icon="Edit"
                @click="toggleInlineEdit(task)"
                >{{ isEditing(task) ? "关闭" : "编辑" }}</el-button
              >
              <el-button
                type="success"
                size="small"
                :icon="VideoPlay"
                :loading="runningTaskKey === getTaskKey(task)"
                :disabled="
                  runningTaskKey !== null && runningTaskKey !== getTaskKey(task)
                "
                @click="runTask(task)"
                >执行</el-button
              >
              <el-button
                type="danger"
                size="small"
                :icon="Delete"
                @click="deleteTask(task)"
                >删除</el-button
              >
            </div>
          </div>
          <div v-if="isEditing(task)" class="inline-edit-panel">
            <el-card shadow="always" class="edit-card">
              <template #header>
                <div class="edit-header">
                  <span>编辑任务 - {{ task.title }}</span>
                </div>
              </template>
              <el-form
                :model="getEditForm(task)"
                label-width="100px"
              >
                <el-form-item label="任务标题" prop="title">
                  <el-input
                    v-model="getEditForm(task).title"
                    placeholder="请输入任务标题"
                  />
                </el-form-item>
                <el-form-item label="项目序号" prop="index">
                  <el-input-number
                    v-model="getEditForm(task).index"
                    :min="1"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item label="执行时间" prop="times">
                  <el-input
                    v-model="editTimesInputs[getTaskKey(task)]"
                    placeholder="08:00:00 18:00:00（支持空格、逗号、竖线等分隔符）"
                  />
                </el-form-item>
                <el-form-item label="执行日期" prop="run_dates">
                  <TaskDateSchedule
                    :date-mode="getEditForm(task).date_mode"
                    :run-dates="getEditForm(task).run_dates"
                    :skip-dates="getEditForm(task).skip_dates"
                    :skip-weekends="getEditForm(task).skip_weekends"
                    :times="getEditForm(task).times"
                    :auto-disable-after-finish="
                      getEditForm(task).auto_disable_after_finish
                    "
                    @update:date-mode="getEditForm(task).date_mode = $event"
                    @update:run-dates="getEditForm(task).run_dates = $event"
                    @update:skip-dates="getEditForm(task).skip_dates = $event"
                    @update:skip-weekends="
                      getEditForm(task).skip_weekends = $event
                    "
                    @update:auto-disable-after-finish="
                      getEditForm(task).auto_disable_after_finish = $event
                    "
                  />
                </el-form-item>
                <el-form-item v-if="hasFillKey(task, 1)" label="签到文本" prop="text">
                  <el-input
                    v-model="getEditForm(task).text"
                    type="textarea"
                    :rows="3"
                    placeholder="请输入签到时需要提交的文本内容"
                  />
                </el-form-item>
                <el-form-item v-if="hasFillKey(task, 2)" label="签到图片">
                  <TaskImageUpload
                    :file-list="getEditFileList(task)"
                    :http-request="(options) => customUpload(task, options)"
                    :on-remove="(file) => onImageRemove(task, file)"
                    :limit="3"
                  />
                  <div class="upload-tip">
                    最多可上传 3 张图片
                  </div>
                </el-form-item>
                <el-form-item label="签到位置">
                  <div class="location-field">
                    <el-radio-group v-model="editLocationModes[getTaskKey(task)]" class="location-mode-group">
                      <el-radio-button value="none">不显示</el-radio-button>
                      <el-radio-button value="auto">自动获取</el-radio-button>
                      <el-radio-button value="map">地图选择</el-radio-button>
                    </el-radio-group>
                    <div class="location-mode-tip">「不显示」时不提交位置；「自动获取」使用定位坐标，「地图选择」可指定准确坐标</div>
                    <div v-if="editLocationModes[getTaskKey(task)] === 'map'" class="location-choice-card">
                      <div class="location-choice-icon">
                        <el-icon><MapLocation /></el-icon>
                      </div>
                      <div class="location-choice-info">
                        <strong>{{ getEditForm(task).location_address || '尚未选择地图位置' }}</strong>
                        <small v-if="getEditForm(task).location_latitude != null">{{ Number(getEditForm(task).location_latitude).toFixed(6) }}, {{ Number(getEditForm(task).location_longitude).toFixed(6) }}</small>
                        <small v-else>点击右侧按钮在地图上选择签到坐标</small>
                      </div>
                      <el-button type="primary" plain size="small" @click="openInlineLocationPicker(task)">
                        {{ getEditForm(task).location_latitude == null ? '选择位置' : '重新选择' }}
                      </el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item
                  v-if="!Array.isArray(task.fill_fields) || savedNameKey(task) !== null"
                  label="签到姓名"
                >
                  <el-input
                    v-model="getEditForm(task).fill_name"
                    maxlength="50"
                    placeholder="项目要求填写姓名时自动提交，请提前填写，例如：张三"
                  />
                </el-form-item>
                <el-form-item
                  v-for="entry in customFillEntries(task)"
                  :key="entry.key"
                  :label="entry.label"
                >
                  <el-input
                    v-model="getEditForm(task).fill_values[entry.key]"
                    maxlength="200"
                    :placeholder="`请输入「${entry.label}」提交内容`"
                  />
                </el-form-item>
                <el-form-item>
                  <el-checkbox v-model="getEditForm(task).enable"
                    >启用任务</el-checkbox
                  >
                  <el-checkbox
                    v-if="isAdmin"
                    v-model="getEditForm(task).notify_wechat"
                    >发送企业微信通知</el-checkbox
                  >
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="saveInlineEdit(task)"
                    >保存任务</el-button
                  >
                  <el-button @click="toggleInlineEdit(task)">取消</el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog
      v-model="taskDialogVisible"
      title="新建任务"
      width="min(1180px, 96vw)"
      align-center
      append-to-body
      destroy-on-close
      class="create-task-dialog"
      @closed="refreshAfterDialog"
    >
      <TaskManager @saved="taskDialogVisible = false" />
    </el-dialog>

    <TaskLocationPickerDialog
      v-model="locationPickerVisible"
      :address="activeLocationForm?.location_address || ''"
      :latitude="activeLocationForm?.location_latitude ?? null"
      :longitude="activeLocationForm?.location_longitude ?? null"
      @confirm="applyInlineMapLocation"
    />

    <CheckinResultDialog
      v-model="checkinResultVisible"
      :result="checkinResult"
    />
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch } from "vue";
import {
  Edit,
  VideoPlay,
  Delete,
  User,
  List,
  Clock,
  MapLocation,
  Picture,
  Calendar,
  ChatLineSquare,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import CheckinResultDialog from "../components/CheckinResultDialog.vue";
import TaskManager from "../components/TaskManager.vue";
import TaskDateSchedule from "../components/TaskDateSchedule.vue";
import TaskImageUpload from "../components/TaskImageUpload.vue";
import TaskLocationPickerDialog from "../components/TaskLocationPickerDialog.vue";
import { useAppState } from "../composables/useAppState";
import { createCheckinResult } from "../utils/checkinResult";
import { getTaskDeleteTargets } from "../utils/batchDelete";
import { buildXxqdTaskPayload } from "../utils/xxqdTaskPayload.js";
import api from "../api";

const { state: appState, refreshState, refreshLogs } = useAppState();
const checkinResultVisible = ref(false);
const checkinResult = ref(null);
const taskDialogVisible = ref(false);
const editingKey = ref(null);
const editForms = reactive({});
const editFileLists = reactive({});
const editTimesInputs = reactive({});
const editLocationModes = reactive({});
const inlineMapLocations = reactive({});
const selectedTaskKeys = ref(new Set());
const batchDeleting = ref(false);
const runningTaskKey = ref(null);
const locationPickerVisible = ref(false);
const locationPickerTaskKey = ref(null);
const activeLocationForm = computed(() => (
  locationPickerTaskKey.value ? editForms[locationPickerTaskKey.value] : null
));

const isAdmin = (() => {
  try {
    const user = JSON.parse(localStorage.getItem("user") || "null");
    return user?.role === "admin";
  } catch {
    return false;
  }
})();

const allTasks = computed(() => {
  const tasks = [];
  appState.value.accounts.forEach((account, accountIdx) => {
    (account.tasks || []).forEach((task, taskIdx) => {
      tasks.push({
        ...task,
        accountName: account.name,
        accountIndex: accountIdx,
        taskIndex: taskIdx,
      });
    });
  });
  return tasks;
});

function getTaskKey(task) {
  return `${task.accountIndex}-${task.taskIndex}`;
}

function taskStatusText(task) {
  if (task.completed_at)
    return task.completion_result === "failed" ? "已结束·失败" : "已完成";
  return task.enable ? "启用" : "禁用";
}

function taskStatusType(task) {
  if (task.completed_at)
    return task.completion_result === "failed" ? "warning" : "primary";
  return task.enable ? "success" : "info";
}

function formatDateTime(value) {
  return String(value || "").replace("T", " ");
}

function toggleTaskSelection(task, checked) {
  const nextKeys = new Set(selectedTaskKeys.value);
  const key = getTaskKey(task);
  if (checked) {
    nextKeys.add(key);
  } else {
    nextKeys.delete(key);
  }
  selectedTaskKeys.value = nextKeys;
}

function openCreateTask() {
  taskDialogVisible.value = true;
}

async function refreshAfterDialog() {
  selectedTaskKeys.value = new Set();
  await Promise.allSettled([refreshState(), refreshLogs()]);
}

function isEditing(task) {
  return editingKey.value === getTaskKey(task);
}

function fillKeysOf(task) {
  // 任务保存时勾选的提交项；null 表示旧任务未配置，保持旧行为显示全部
  return Array.isArray(task.fill_fields)
    ? new Set(task.fill_fields.map(String))
    : null;
}

function hasFillKey(task, key) {
  const keys = fillKeysOf(task);
  return keys === null || keys.has(String(key));
}

function customFillEntries(task) {
  const keys = fillKeysOf(task);
  if (keys === null) return [];
  const nameKey = savedNameKey(task);
  return Object.keys(task.fill_values || {})
    .filter(
      (k) =>
        keys.has(String(k))
        && !["1", "2", "6"].includes(String(k))
        && k !== nameKey,
    )
    .map((k) => ({ key: k, label: `填写项(${k})` }));
}

// 保存任务时「签到姓名」的值存在 fill_name（不在 fill_values），
// 对应 fill_fields 里第一个没有 fill_values 值的非标准 key
function savedNameKey(task) {
  const keys = fillKeysOf(task);
  if (keys === null) return null;
  if (!String(task.fill_name || "").trim()) return null;
  const custom = [...keys].filter((k) => !["1", "2", "6"].includes(k));
  if (!custom.length) return null;
  return (
    custom.find((k) => !String(task.fill_values?.[k] ?? "").trim()) || null
  );
}

function getEditForm(task) {
  const key = getTaskKey(task);
  if (!editForms[key]) {
    editForms[key] = reactive({
      title: task.title || "",
      index: task.index || 1,
      times: [...(task.times || [])],
      text: task.text || "",
      fill_name: task.fill_name || "",
      fill_values: { ...(task.fill_values || {}) },
      fill_fields: Array.isArray(task.fill_fields)
        ? [...task.fill_fields.map(String)]
        : null,
      pic_path: [...(task.pic_path || [])],
      enable: task.enable !== false,
      use_location: task.use_location || false,
      location_address: task.location_address || "",
      location_latitude: task.location_latitude ?? null,
      location_longitude: task.location_longitude ?? null,
      skip_weekends: task.skip_weekends || false,
      date_mode: task.date_mode || "daily",
      run_dates: [...(task.run_dates || [])],
      skip_dates: [...(task.skip_dates || [])],
      auto_disable_after_finish: task.auto_disable_after_finish === true,
      mode: task.mode || "normal",
      notify_wechat: task.notify_wechat !== false,
    });
  }
  return editForms[key];
}

function getEditFileList(task) {
  const key = getTaskKey(task);
  if (!editFileLists[key]) {
    const paths = Array.isArray(task.pic_path)
      ? task.pic_path
      : task.pic_path
        ? [task.pic_path]
        : [];
    editFileLists[key] = paths.map((path, idx) => ({
      uid: `${idx}`,
      name: String(path).replace(/\\/g, "/").split("/").pop() || "image.jpg",
      url: path.startsWith("http")
        ? path
        : `/uploads/${String(path).replace(/\\/g, "/").split("/").pop()}`,
      path,
      status: "success",
    }));
  }
  return editFileLists[key];
}

function toggleInlineEdit(task) {
  const key = getTaskKey(task);
  if (editingKey.value === key) {
    editingKey.value = null;
    delete editForms[key];
    delete editFileLists[key];
    delete editTimesInputs[key];
    delete editLocationModes[key];
    delete inlineMapLocations[key];
  } else {
    editingKey.value = key;
    getEditForm(task);

    const paths = Array.isArray(task.pic_path)
      ? task.pic_path
      : task.pic_path
        ? [task.pic_path]
        : [];
    editFileLists[key] = paths.map((path, idx) => ({
      uid: `${idx}`,
      name: String(path).replace(/\\/g, "/").split("/").pop() || "image.jpg",
      url: path.startsWith("http")
        ? path
        : `/uploads/${String(path).replace(/\\/g, "/").split("/").pop()}`,
      path,
      status: "success",
    }));

    editTimesInputs[key] = (task.times || []).join(", ");
    editLocationModes[key] = (
      task.location_latitude != null && task.location_longitude != null
    ) ? "map" : task.use_location ? "auto" : "none";
    inlineMapLocations[key] = (
      task.location_latitude != null && task.location_longitude != null
    ) ? {
      address: task.location_address || "",
      latitude: task.location_latitude,
      longitude: task.location_longitude,
    } : null;

    watch(
      () => editTimesInputs[key],
      (val) => {
        if (val != null && editForms[key]) {
          editForms[key].times = val
            .split(/[\s,|;，；、]+/)
            .map((t) => t.trim())
            .filter(Boolean);
        }
      },
    );

    watch(
      () => editLocationModes[key],
      (val) => {
        if (val != null && editForms[key]) {
          editForms[key].use_location = val !== "none";
          if (val === "none" || val === "auto") {
            editForms[key].location_address = "";
            editForms[key].location_latitude = null;
            editForms[key].location_longitude = null;
            inlineMapLocations[key] = null;
          }
        }
      },
    );
  }
}

function taskLocationLabel(task) {
  return task.location_latitude != null && task.location_longitude != null
    ? "地图"
    : "自动";
}

function openInlineLocationPicker(task) {
  locationPickerTaskKey.value = getTaskKey(task);
  locationPickerVisible.value = true;
}

function applyInlineMapLocation(location) {
  const form = activeLocationForm.value;
  if (!form) return;
  form.use_location = true;
  form.location_address = location.address || "";
  form.location_latitude = location.latitude;
  form.location_longitude = location.longitude;
  inlineMapLocations[locationPickerTaskKey.value] = { ...location };
}

async function saveInlineEdit(task) {
  const key = getTaskKey(task);
  if (
    editLocationModes[key] === "map"
    && (
      editForms[key].location_latitude == null
      || editForms[key].location_longitude == null
    )
  ) {
    ElMessage.warning("请先通过地图选择签到位置");
    return;
  }
  editForms[key].times = editTimesInputs[key]
    .split(/[\s,|;，；、]+/)
    .map((t) => t.trim())
    .filter(Boolean);
  if (
    editForms[key].date_mode === "specific" &&
    !editForms[key].run_dates.length
  ) {
    ElMessage.warning("指定日期模式下请至少选择一个执行日期");
    return;
  }
  editForms[key].mode =
    editForms[key].pic_path && editForms[key].pic_path.length
      ? "image"
      : "normal";
  if (!isAdmin) editForms[key].notify_wechat = true;

  try {
    await api.updateTask(
      task.accountIndex,
      task.taskIndex,
      buildXxqdTaskPayload(
        editForms[key],
        editLocationModes[key],
        inlineMapLocations[key],
      ),
    );
    ElMessage.success("任务已更新");
    await refreshState();
    await refreshLogs();
    toggleInlineEdit(task);
  } catch (err) {
    ElMessage.error(err.message);
  }
}

async function customUpload(task, options) {
  const key = getTaskKey(task);
  try {
    const res = await api.uploadImage(options.file);
    if (res.data && res.data.path) {
      if (!Array.isArray(editForms[key].pic_path)) editForms[key].pic_path = [];
      editForms[key].pic_path.push(res.data.path);
      const paths = editForms[key].pic_path;
      editFileLists[key] = paths.map((path, idx) => ({
        uid: `${idx}`,
        name: String(path).replace(/\\/g, "/").split("/").pop() || "image.jpg",
        url: path.startsWith("http")
          ? path
          : `/uploads/${String(path).replace(/\\/g, "/").split("/").pop()}`,
        path,
        status: "success",
      }));
    }
    options.onSuccess(res);
    ElMessage.success("图片上传成功");
  } catch (err) {
    options.onError(err);
    ElMessage.error(err.message || "图片上传失败");
  }
}

function onImageRemove(task, file) {
  const key = getTaskKey(task);
  const removedPath = file.path || file.url;
  editForms[key].pic_path = editForms[key].pic_path.filter((p) => {
    const pName = String(p).replace(/\\/g, "/").split("/").pop();
    const rName = String(removedPath).replace(/\\/g, "/").split("/").pop();
    return pName !== rName;
  });
  const paths = editForms[key].pic_path;
  editFileLists[key] = paths.map((path, idx) => ({
    uid: `${idx}`,
    name: String(path).replace(/\\/g, "/").split("/").pop() || "image.jpg",
    url: path.startsWith("http")
      ? path
      : `/uploads/${String(path).replace(/\\/g, "/").split("/").pop()}`,
    path,
    status: "success",
  }));
}

async function runTask(row) {
  if (runningTaskKey.value !== null) return;
  runningTaskKey.value = getTaskKey(row);
  try {
    const res = await api.runTask(row.accountIndex, row.taskIndex);
    checkinResult.value = createCheckinResult(res.data || {});
    checkinResultVisible.value = true;
    await refreshLogs();
  } catch (err) {
    ElMessage.error(err.message);
  } finally {
    runningTaskKey.value = null;
  }
}

async function deleteTask(row) {
  try {
    await ElMessageBox.confirm(`确认删除任务「${row.title}」吗？`, "提示", {
      type: "warning",
    });
    await api.deleteTask(row.accountIndex, row.taskIndex);
    await refreshState();
    await refreshLogs();
    ElMessage.success("任务已删除");
  } catch (err) {
    if (err !== "cancel") ElMessage.error(err.message);
  }
}

async function deleteSelectedTasks() {
  const count = selectedTaskKeys.value.size;
  if (!count || batchDeleting.value) return;

  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${count} 个任务吗？`,
      "批量删除任务",
      { type: "warning" },
    );
  } catch (err) {
    if (err === "cancel" || err === "close") return;
    ElMessage.error(err.message || "操作失败");
    return;
  }

  const targets = getTaskDeleteTargets(selectedTaskKeys.value);
  batchDeleting.value = true;
  try {
    for (const target of targets) {
      await api.deleteTask(target.accountIndex, target.taskIndex);
    }
    selectedTaskKeys.value = new Set();
    await refreshState();
    await refreshLogs();
    ElMessage.success(`已删除 ${targets.length} 个任务`);
  } catch (err) {
    selectedTaskKeys.value = new Set();
    await Promise.allSettled([refreshState(), refreshLogs()]);
    ElMessage.error(err.message || "批量删除任务失败");
  } finally {
    batchDeleting.value = false;
  }
}
</script>

<style scoped>
.location-field { width:100%; display:flex; flex-direction:column; gap:10px; }
.location-mode-group { width:100%; }
.location-mode-group :deep(.el-radio-button__inner) { padding:8px 0; width:104px; border-radius:0; }
.location-mode-group :deep(.el-radio-button:first-child .el-radio-button__inner) { border-radius:8px 0 0 8px; }
.location-mode-group :deep(.el-radio-button:last-child .el-radio-button__inner) { border-radius:0 8px 8px 0; }
.location-choice-card { display:flex; width:100%; padding:12px 14px; align-items:center; gap:12px; border:1px solid #cfe2ff; border-radius:12px; background:linear-gradient(135deg, #f3f9ff, #f8fbff); }
.location-choice-icon { flex:none; display:grid; width:38px; height:38px; place-items:center; border-radius:10px; color:#2563eb; font-size:20px; background:#eaf3ff; }
.location-choice-info { flex:1; min-width:0; }
.location-choice-info strong { display:block; overflow:hidden; color:#1e3a5f; font-size:13px; line-height:20px; text-overflow:ellipsis; white-space:nowrap; }
.location-choice-info small { display:block; margin-top:2px; color:#94a3b8; font-size:11px; }
.location-choice-card .el-button { flex:none; margin:0; }
.location-mode-tip { width:100%; color:#94a3b8; font-size:11px; line-height:1.5; }
@media (max-width:640px) { .location-choice-card { gap:10px; padding:10px 12px; } .location-mode-group :deep(.el-radio-button__inner) { width:auto; min-width:96px; padding:8px 10px; } }
.page-container {
  padding: 0;
}
:global(.create-task-dialog .el-dialog__body) {
  max-height: 78vh;
  padding-top: 8px;
  overflow: auto;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.task-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #fafafa;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  transition: all 0.2s ease;
}

.task-card:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.task-main {
  flex: 1;
  min-width: 0;
}

.task-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.task-title {
  font-weight: 700;
  color: #1f2937;
  font-size: 15px;
}

.task-info {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: #6b7280;
}

.task-info span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.mobile-task-summary {
  display: none;
}

.task-actions {
  display: flex;
  gap: 8px;
  margin-left: 20px;
}

.inline-edit-panel {
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.edit-card {
  margin: 0;
  border-radius: 12px;
}

.edit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-state {
  padding: 40px 0;
}

.upload-tip {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
}

@media (max-width: 768px) {
  .card-header {
    align-items: center;
    flex-direction: row;
    width: 100%;
  }
  .task-toolbar {
    margin-left: auto;
  }
  .task-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    padding: 13px 16px;
  }

  .task-main {
    width: 100%;
  }

  .task-title-row {
    margin-bottom: 8px;
  }
  .task-info {
    display: none;
  }
  .mobile-task-summary {
    display: flex;
    align-items: center;
    gap: 13px;
    padding-left: 26px;
    overflow-x: auto;
    color: #64748b;
    font-size: 11px;
    scrollbar-width: none;
    white-space: nowrap;
  }
  .mobile-task-summary::-webkit-scrollbar {
    display: none;
  }
  .mobile-task-summary span {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    flex: none;
  }
  .mobile-task-summary small {
    color: #2563eb;
    font-size: 10px;
  }

  .task-actions {
    width: 100%;
    margin-left: 0;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .task-actions .el-button {
    flex: 1;
    min-width: 0;
    min-height: 38px;
    margin: 0;
  }
  .edit-card {
    border-width: 1px 0 0 !important;
    border-radius: 0;
    box-shadow: none !important;
  }
  .edit-card :deep(.el-form-item) {
    display: block;
    margin-bottom: 20px;
  }
  .edit-card :deep(.el-form-item__label) {
    display: block;
    width: 100% !important;
    height: auto;
    margin-bottom: 8px;
    padding: 0;
    font-size: 13px;
    line-height: 1.4;
    text-align: left;
  }
  .edit-card :deep(.el-form-item__content) {
    width: 100%;
    margin-left: 0 !important;
  }
}

@media (max-width: 480px) {
  .task-title {
    font-size: 14px;
  }

  .task-title-row {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .task-title {
    flex: 1;
    min-width: 120px;
  }
  .edit-card :deep(.el-form-item__label) {
    font-size: 12px;
  }
}
</style>
