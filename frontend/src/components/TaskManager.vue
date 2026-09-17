<template>
  <div class="page-container">
    <el-row :gutter="16" class="task-layout">
      <el-col :xs="24" :lg="14">
        <el-card shadow="hover" class="task-list-card">
          <template #header>
            <div class="card-header">
              <span>任务列表</span>
              <div class="task-account-toolbar">
                <el-select
                  v-model="selectedAccountIndex"
                  placeholder="请选择用户"
                  clearable
                  style="width: 220px"
                  @change="onAccountChange"
                >
                  <el-option
                    v-for="(acc, idx) in state.accounts"
                    :key="idx"
                    :label="`${acc.name} (${acc.mobile})`"
                    :value="idx"
                  />
                </el-select>
                <el-button
                  type="warning"
                  plain
                  :icon="Refresh"
                  :disabled="
                    selectedAccountIndex == null ||
                    selectedAccountIndex < 0 ||
                    tokenRefreshing
                  "
                  :loading="tokenRefreshing"
                  @click="refreshSelectedAccountToken"
                  >刷新 Token</el-button
                >
                <el-tag
                  v-if="
                    currentAccount &&
                    currentAccount.projects &&
                    currentAccount.projects.length > 0
                  "
                  type="info"
                  size="small"
                >
                  任务上限 {{ (currentAccount.tasks || []).length }}/{{
                    currentAccount.projects.length
                  }}
                </el-tag>
              </div>
            </div>
          </template>

          <el-table
            ref="taskTableRef"
            class="desktop-task-table"
            :data="accountTasks"
            highlight-current-row
            @current-change="onSelectTask"
            style="width: 100%"
            max-height="360"
            empty-text="当前账号下暂无任务"
          >
            <el-table-column prop="task.title" label="标题" min-width="80" />
            <el-table-column prop="task.index" label="序号" width="80" />
            <el-table-column label="文本" min-width="80" show-overflow-tooltip>
              <template #default="scope">{{
                scope.row.task.text || "-"
              }}</template>
            </el-table-column>
            <el-table-column label="位置" width="80">
              <template #default="scope">
                <el-tag :type="locationTagType(scope.row.task)" size="small">
                  {{ locationTagText(scope.row.task) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="图片" width="80">
              <template #default="scope">
                <el-tag
                  :type="
                    (scope.row.task.pic_path || []).length ? 'warning' : 'info'
                  "
                  size="small"
                >
                  {{ (scope.row.task.pic_path || []).length }}张
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="时间" min-width="80">
              <template #default="scope">{{
                (scope.row.task.times || []).join(", ")
              }}</template>
            </el-table-column>
            <el-table-column label="日期" min-width="92">
              <template #default="scope">
                {{
                  scope.row.task.date_mode === "specific"
                    ? `指定 ${(scope.row.task.run_dates || []).length} 天`
                    : "每天"
                }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="88">
              <template #default="scope">
                <el-tag
                  :type="taskStatusType(scope.row.task)"
                  size="small"
                  :title="
                    scope.row.task.completed_at
                      ? `完成于 ${formatDateTime(scope.row.task.completed_at)}`
                      : ''
                  "
                >
                  {{ taskStatusText(scope.row.task) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="周末跳过" width="80">
              <template #default="scope">
                <el-tag
                  :type="scope.row.task.skip_weekends ? 'warning' : 'info'"
                  size="small"
                >
                  {{ scope.row.task.skip_weekends ? "是" : "否" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column v-if="isAdmin" label="企微通知" width="80">
              <template #default="scope">
                <el-tag
                  :type="
                    scope.row.task.notify_wechat !== false ? 'success' : 'info'
                  "
                  size="small"
                >
                  {{ scope.row.task.notify_wechat !== false ? "是" : "否" }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div class="mobile-task-list">
            <el-empty
              v-if="!accountTasks.length"
              description="当前账号下暂无任务"
              :image-size="72"
            />
            <article
              v-for="row in accountTasks"
              :key="row.actualIndex"
              class="mobile-task-card"
              :class="{ 'is-active': selectedActualIndex === row.actualIndex }"
              @click="onSelectTask(row)"
            >
              <header>
                <div class="mobile-task-card__heading">
                  <strong>{{ row.task.title || "未命名任务" }}</strong>
                  <span>项目序号 {{ row.task.index }}</span>
                </div>
                <el-tag :type="taskStatusType(row.task)" size="small">{{
                  taskStatusText(row.task)
                }}</el-tag>
              </header>
              <p :class="{ 'is-empty': !row.task.text }">
                {{ row.task.text || "未设置签到文本" }}
              </p>
              <div class="mobile-task-card__facts">
                <span
                  >执行时间
                  <strong>{{
                    (row.task.times || []).join("、") || "未设置"
                  }}</strong></span
                >
                <span
                  >日期
                  <strong>{{
                    row.task.date_mode === "specific"
                      ? `指定 ${(row.task.run_dates || []).length} 天`
                      : "每天"
                  }}</strong></span
                >
                <span
                  >位置 <strong>{{ locationTagText(row.task) }}</strong></span
                >
                <span
                  >图片
                  <strong
                    >{{ (row.task.pic_path || []).length }} 张</strong
                  ></span
                >
              </div>
              <footer>
                <div class="mobile-task-card__policies">
                  <span v-if="isAdmin">{{
                    row.task.skip_weekends ? "跳过周末" : "周末执行"
                  }}</span>
                  <span v-if="isAdmin">{{
                    row.task.notify_wechat !== false ? "企微通知" : "不通知"
                  }}</span>
                </div>
              </footer>
            </article>
          </div>

          <div class="form-section project-section">
            <div class="section-header">
              <span>签到项目列表</span>
              <div class="section-header-actions">
                <el-button
                  type="primary"
                  plain
                  :icon="Search"
                  size="small"
                  @click="fetchProjects"
                  :disabled="selectedAccountIndex < 0 || projectsLoading"
                  :loading="projectsLoading"
                >
                  {{ projectsLoading ? "获取中…" : "获取项目列表" }}
                </el-button>
                <el-button
                  type="primary"
                  plain
                  :icon="DocumentChecked"
                  size="small"
                  @click="detectFillOptions"
                  :disabled="selectedProjectIndex < 0 || fillOptionsLoading"
                  :loading="fillOptionsLoading"
                >
                  {{ fillOptionsLoading ? "检测中…" : "检测填写项" }}
                </el-button>
              </div>
            </div>
            <el-empty
              v-if="!projects.length"
              description="先选择账号，再点击“获取签到项目列表”"
              :image-size="80"
            />
            <el-scrollbar v-else max-height="220">
              <div
                v-for="(item, idx) in projects"
                :key="idx"
                class="project-item"
                :class="{ 'is-active': selectedProjectIndex === idx }"
                @click="applyProject(idx, item)"
              >
                <span class="project-index">{{ idx + 1 }}</span>
                <span class="project-title">{{
                  item.title || "未命名项目"
                }}</span>
                <el-icon v-if="selectedProjectIndex === idx" class="project-check">
                  <Check />
                </el-icon>
              </div>
            </el-scrollbar>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="hover" class="task-form-card">
          <template #header>
            <div class="card-header">
              <span>任务设置</span>
              <div class="card-header-right">
                <el-tag
                  :type="
                    form.pic_path && form.pic_path.length ? 'warning' : 'primary'
                  "
                >
                  {{
                    form.pic_path && form.pic_path.length
                      ? "图片签到"
                      : "普通签到"
                  }}
                </el-tag>
              </div>
            </div>
          </template>
          <el-form
            class="task-settings-form"
            :model="form"
            label-width="100px"
            :rules="rules"
            ref="formRef"
          >
            <el-form-item label="任务标题" prop="title">
              <el-input v-model="form.title" placeholder="请输入任务标题" />
            </el-form-item>
            <el-form-item label="项目序号" prop="index">
              <el-input-number
                v-model="form.index"
                :min="1"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="执行时间" prop="times">
              <el-input
                v-model="timesText"
                placeholder="08:00:00 18:00:00（支持空格、逗号、竖线等分隔符）"
              />
            </el-form-item>
            <el-form-item label="执行日期" prop="run_dates">
              <TaskDateSchedule
                :date-mode="form.date_mode"
                :run-dates="form.run_dates"
                :skip-dates="form.skip_dates"
                :skip-weekends="form.skip_weekends"
                :times="form.times"
                :auto-disable-after-finish="form.auto_disable_after_finish"
                @update:date-mode="form.date_mode = $event"
                @update:run-dates="form.run_dates = $event"
                @update:skip-dates="form.skip_dates = $event"
                @update:skip-weekends="form.skip_weekends = $event"
                @update:auto-disable-after-finish="
                  form.auto_disable_after_finish = $event
                "
              />
            </el-form-item>
            <el-form-item
              v-if="fillOptionsLoading"
              class="detect-status-item"
            >
              <el-alert
                type="info"
                :closable="false"
                show-icon
                title="正在检测填写项，请稍候…"
              />
            </el-form-item>
            <el-form-item v-else-if="fillOptionsError" class="detect-status-item">
              <el-alert
                type="error"
                :closable="false"
                show-icon
                :title="`检测失败：${fillOptionsError}`"
                description="请检查账号 Token 与项目序号后，点击「检测填写项」重试；检测成功前无法填写签到内容。"
              />
            </el-form-item>
            <el-form-item v-else-if="!fillOptionsChecked" class="detect-status-item">
              <el-alert
                type="info"
                :closable="false"
                show-icon
                title="尚未检测填写项"
                description="请先点击右上角「检测填写项」，检测成功后才会在此显示需要填写的签到内容。"
              />
            </el-form-item>
            <template v-else>
              <div class="fill-detect-result">
                <span>检测结果</span>
                <div class="fill-detect-tags">
                  <template v-if="displayFillOptions.length">
                    <el-tooltip
                      v-for="item in displayFillOptions"
                      :key="item.key"
                      :content="Number(item.key) === LOCATION_KEY ? '位置信息始终提交' : '点击切换是否提交该项'"
                      placement="top"
                    >
                      <el-tag
                        class="fill-option-tag"
                        :type="isFillKeySelected(item.key) ? fillTagType(item) : 'info'"
                        :effect="isFillKeySelected(item.key) ? 'light' : 'plain'"
                        size="small"
                        @click="toggleFillKey(item.key)"
                      >
                        {{ isFillKeySelected(item.key) ? "✓ " : "" }}{{ item.name }}{{ fillTagType(item) === 'warning' ? '（暂不支持）' : '' }}
                      </el-tag>
                    </el-tooltip>
                    <small class="fill-detect-tip">点击标签可取消勾选，保存任务时将不提交该项（位置始终提交）</small>
                  </template>
                </div>
              </div>
              <el-form-item v-if="hasTextFill" label="签到文本" prop="text">
                <el-input
                  v-model="form.text"
                  type="textarea"
                  :rows="3"
                  placeholder="该项目要求提交文字，请输入签到文本内容"
                />
              </el-form-item>
              <el-form-item v-if="hasImageFill" label="签到图片">
                <TaskImageUpload
                  :file-list="fileList"
                  :http-request="customUpload"
                  :on-remove="onImageRemove"
                  :limit="3"
                />
                <div class="upload-tip">
                  该项目要求提交图片，最多可上传 3 张
                </div>
              </el-form-item>
              <el-form-item label="签到位置">
                <div class="location-field">
                  <el-radio-group v-model="locationMode" class="location-mode-group">
                    <el-radio-button value="none">不显示</el-radio-button>
                    <el-radio-button value="auto">自动获取</el-radio-button>
                    <el-radio-button value="map">地图选择</el-radio-button>
                  </el-radio-group>
                  <div class="location-mode-tip">位置信息始终随签到提交，选择「地图选择」可指定准确坐标</div>
                  <div v-if="locationMode === 'map'" class="location-choice-card">
                    <div class="location-choice-icon">
                      <el-icon><MapLocation /></el-icon>
                    </div>
                    <div class="location-choice-info">
                      <strong>{{ form.location_address || '尚未选择地图位置' }}</strong>
                      <small v-if="form.location_latitude != null">{{ Number(form.location_latitude).toFixed(6) }}, {{ Number(form.location_longitude).toFixed(6) }}</small>
                      <small v-else>点击右侧按钮在地图上选择签到坐标</small>
                    </div>
                    <el-button type="primary" plain size="small" @click="locationPickerVisible = true">
                      {{ form.location_latitude == null ? '选择位置' : '重新选择' }}
                    </el-button>
                  </div>
                </div>
              </el-form-item>
              <el-form-item v-if="hasNameFill" label="签到姓名">
                <el-input
                  v-model="form.fill_name"
                  maxlength="50"
                  placeholder="该项目要求填写姓名，例如：张三"
                />
              </el-form-item>
              <el-form-item
                v-for="item in customFillItems"
                :key="item.key"
                :label="item.name"
              >
                <el-select
                  v-if="Number(item.field_type) === 1"
                  v-model="form.fill_values[String(item.key)]"
                  :placeholder="`请选择${item.name}`"
                  style="width: 100%"
                >
                  <el-option
                    v-for="choice in item.options"
                    :key="choice"
                    :label="choice"
                    :value="choice"
                  />
                </el-select>
                <el-input
                  v-else
                  v-model="form.fill_values[String(item.key)]"
                  :maxlength="200"
                  :placeholder="`该项目要求填写「${item.name}」`"
                />
              </el-form-item>
            </template>
            <el-form-item class="task-primary-actions">
              <el-checkbox v-model="form.enable">启用任务</el-checkbox>
              <el-checkbox v-if="isAdmin" v-model="form.notify_wechat"
                >发送企业微信通知</el-checkbox
              >
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveTask">保存任务</el-button>
              <el-button @click="createNew">重置</el-button>
            </el-form-item>
            <el-form-item
              v-if="selectedActualIndex >= 0"
              class="task-secondary-actions"
            >
              <div class="task-secondary-grid">
                <el-button
                  type="success"
                  :icon="VideoPlay"
                  :loading="runningTask"
                  :disabled="runningTask"
                  @click="runTask"
                  >执行选中任务</el-button
                >
                <el-button type="danger" :icon="Delete" @click="deleteTask"
                  >删除任务</el-button
                >
              </div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <CheckinResultDialog
      v-model="checkinResultVisible"
      :result="checkinResult"
    />
    <TaskLocationPickerDialog
      v-model="locationPickerVisible"
      :address="form.location_address"
      :latitude="form.location_latitude"
      :longitude="form.location_longitude"
      @confirm="applyMapLocation"
    />
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch, nextTick } from "vue";
import { Search, VideoPlay, Delete, Refresh, Check, DocumentChecked, MapLocation } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import CheckinResultDialog from "./CheckinResultDialog.vue";
import TaskDateSchedule from "./TaskDateSchedule.vue";
import TaskImageUpload from "./TaskImageUpload.vue";
import TaskLocationPickerDialog from "./TaskLocationPickerDialog.vue";
import { useAppState } from "../composables/useAppState";
import { createCheckinResult } from "../utils/checkinResult";
import { buildXxqdTaskPayload } from "../utils/xxqdTaskPayload.js";
import { applyMembershipUpdate } from "../utils/userMembership";
import api from "../api";

const emit = defineEmits(["saved"]);

const { state, refreshState, refreshLogs, selectedAccountIndex } =
  useAppState();

const isAdmin = (() => {
  try {
    const user = JSON.parse(localStorage.getItem("user") || "null");
    return user?.role === "admin";
  } catch {
    return false;
  }
})();

const selectedActualIndex = ref(-1);
const projects = ref([]);
const selectedProjectIndex = ref(-1);
const projectsLoading = ref(false);
const fillOptions = ref([]);
const fillOptionsTitle = ref("");
const fillOptionsLoading = ref(false);
const fillOptionsChecked = ref(false);
const fillOptionsError = ref("");
const tokenRefreshing = ref(false);
const formRef = ref(null);
const fileList = ref([]);
const checkinResultVisible = ref(false);
const checkinResult = ref(null);
const runningTask = ref(false);
const locationMode = ref("none");
const locationPickerVisible = ref(false);
const selectedMapLocation = ref(null);
const taskTableRef = ref(null);
// 编辑已有任务时临时抑制「检测状态重置」watcher，避免刚合成的提交项被清掉
let suppressFillReset = false;

const fillKeys = computed(
  () => new Set(fillOptions.value.map((item) => Number(item.key))),
);
// 用户勾选要提交的填写项 key（字符串）；检测成功后默认全选
const selectedFillKeys = ref(new Set());
const activeFillOptions = computed(() =>
  fillOptions.value.filter((item) => selectedFillKeys.value.has(String(item.key))),
);
// 位置填写项始终存在、始终提交，不受检测结果影响
const LOCATION_KEY = 6;
const displayFillOptions = computed(() => {
  const items = [...fillOptions.value];
  if (!items.some((item) => Number(item.key) === LOCATION_KEY)) {
    items.push({ key: LOCATION_KEY, name: "位置", forced: true });
  }
  return items;
});
const activeFillKeys = computed(
  () => new Set(activeFillOptions.value.map((item) => Number(item.key))),
);
const hasTextFill = computed(() => activeFillKeys.value.has(1));
const hasImageFill = computed(() => activeFillKeys.value.has(2));
const hasLocationFill = computed(() => activeFillKeys.value.has(6));
const hasNameFill = computed(() =>
  activeFillOptions.value.some(
    (item) =>
      ![1, 2, 6].includes(Number(item.key)) &&
      /姓名|名字/.test(item.name || ""),
  ),
);
const customFillItems = computed(() =>
  activeFillOptions.value.filter(
    (item) =>
      ![1, 2, 6].includes(Number(item.key)) &&
      !/姓名|名字/.test(item.name || ""),
  ),
);

function isFillKeySelected(key) {
  if (Number(key) === LOCATION_KEY) return true; // 位置始终提交
  return selectedFillKeys.value.has(String(key));
}

function toggleFillKey(key) {
  if (Number(key) === LOCATION_KEY) {
    ElMessage.info("位置信息始终提交，无法取消");
    return;
  }
  const next = new Set(selectedFillKeys.value);
  const k = String(key);
  if (next.has(k)) {
    next.delete(k);
  } else {
    next.add(k);
  }
  selectedFillKeys.value = next;
}

const form = reactive({
  title: "",
  index: 1,
  times: [],
  text: "",
  fill_name: "",
  fill_values: {},
  fill_fields: null,
  pic_path: [],
  enable: true,
  use_location: false,
  location_address: "",
  location_latitude: null,
  location_longitude: null,
  skip_weekends: false,
  date_mode: "daily",
  run_dates: [],
  skip_dates: [],
  auto_disable_after_finish: true,
  mode: "normal",
  notify_wechat: true,
});

// Keep the input text independent from the normalized array.  Rebuilding the
// input value from `form.times` on every keystroke causes the browser caret to
// jump/reset after the first complete time (for example, after `08:00:00`).
// The raw text stays untouched while typing and is parsed only for form data.
const timesText = ref("");

function parseTimesText(value) {
  return String(value || "")
    .split(/[\s,|;，；、]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

watch(timesText, (value) => {
  form.times = parseTimesText(value);
});

const rules = {
  title: [{ required: true, message: "请输入任务标题", trigger: "blur" }],
  index: [{ required: true, message: "请输入项目序号", trigger: "blur" }],
  times: [
    {
      validator: (rule, value, callback) => {
        if (!value || value.length === 0) {
          callback(new Error("请至少设置一个执行时间"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
};

const currentAccount = computed(
  () => state.value.accounts[selectedAccountIndex.value] || null,
);

watch(locationMode, (val) => {
  if (val === "none") {
    form.use_location = false;
    form.location_address = "";
    form.location_latitude = null;
    form.location_longitude = null;
    selectedMapLocation.value = null;
  } else if (val === "auto") {
    form.use_location = true;
    form.location_address = "";
    form.location_latitude = null;
    form.location_longitude = null;
    selectedMapLocation.value = null;
  } else if (val === "map") {
    form.use_location = true;
  }
});

function syncLocationMode() {
  locationMode.value = form.location_latitude != null && form.location_longitude != null
    ? "map"
    : form.use_location ? "auto" : "none";
}

function locationTagType(task) {
  return task.use_location ? "success" : "info";
}

function locationTagText(task) {
  if (task.location_latitude != null && task.location_longitude != null) return "地图";
  return task.use_location ? "自动" : "无";
}

function taskStatusText(task) {
  if (task.completed_at)
    return task.completion_result === "failed" ? "已结束" : "已完成";
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

const accountTasks = computed(() => {
  if (!currentAccount.value) return [];
  return (currentAccount.value.tasks || []).map((task, actualIndex) => ({
    task,
    actualIndex,
  }));
});

onMounted(async () => {
  if (selectedAccountIndex.value != null) {
    await fetchProjects();
  }
});

async function onAccountChange() {
  selectedActualIndex.value = -1;
  projects.value = currentAccount.value?.projects || [];
  createNew();
  if (selectedAccountIndex.value != null) {
    await fetchProjects();
  }
}

function syncFileList() {
  const paths = Array.isArray(form.pic_path)
    ? form.pic_path
    : form.pic_path
      ? [form.pic_path]
      : [];
  fileList.value = paths.map((path, idx) => {
    const name =
      String(path).replace(/\\/g, "/").split("/").pop() || "image.jpg";
    const url = path.startsWith("http") ? path : `/uploads/${name}`;
    return { uid: `${idx}`, name, url, path, status: "success" };
  });
}

function createNew() {
  selectedActualIndex.value = -1;
  selectedProjectIndex.value = -1;
  resetFillOptionsState();
  form.title = "";
  form.index = 1;
  form.times = [];
  timesText.value = "";
  form.text = "";
  form.fill_name = "";
  form.fill_values = {};
  form.fill_fields = null;
  form.pic_path = [];
  form.enable = true;
  form.use_location = false;
  form.location_address = "";
  form.location_latitude = null;
  form.location_longitude = null;
  selectedMapLocation.value = null;
  form.skip_weekends = false;
  form.date_mode = "daily";
  form.run_dates = [];
  form.skip_dates = [];
  form.auto_disable_after_finish = true;
  form.mode = "normal";
  form.notify_wechat = true;
  locationMode.value = "none";
  fileList.value = [];
}

function onSelectTask(row) {
  if (!row) return;
  suppressFillReset = true;
  selectedActualIndex.value = row.actualIndex;
  const task = row.task;
  // 自动选中任务对应的项目（项目序号从 1 开始）
  const projIdx = Number(task.index) - 1;
  selectedProjectIndex.value =
    projects.value.length && projIdx >= 0 && projIdx < projects.value.length
      ? projIdx
      : -1;
  form.title = task.title;
  form.index = task.index;
  form.times = [...(task.times || [])];
  timesText.value = form.times.join(", ");
  form.text = task.text;
  form.fill_name = task.fill_name || "";
  form.fill_values = { ...(task.fill_values || {}) };
  form.fill_fields = Array.isArray(task.fill_fields)
    ? [...task.fill_fields.map(String)]
    : null;
  const taskPicPaths = Array.isArray(task.pic_path)
    ? task.pic_path
    : task.pic_path
      ? [task.pic_path]
      : [];
  form.pic_path = taskPicPaths;
  form.enable = task.enable;
  form.use_location = task.use_location;
  form.location_address = task.location_address || "";
  form.location_latitude = task.location_latitude ?? null;
  form.location_longitude = task.location_longitude ?? null;
  selectedMapLocation.value = (
    form.location_latitude != null && form.location_longitude != null
  ) ? {
    address: form.location_address,
    latitude: form.location_latitude,
    longitude: form.location_longitude,
  } : null;
  form.skip_weekends = task.skip_weekends;
  form.date_mode = task.date_mode || "daily";
  form.run_dates = [...(task.run_dates || [])];
  form.skip_dates = [...(task.skip_dates || [])];
  form.auto_disable_after_finish = task.auto_disable_after_finish === true;
  form.mode = task.mode || (taskPicPaths.length ? "image" : "normal");
  form.notify_wechat = isAdmin ? task.notify_wechat !== false : true;
  syncLocationMode();
  syncFileList();
  // 已保存提交项的任务直接按其渲染表单，无需重新检测
  const saved = buildSavedFillOptions(task);
  if (saved) {
    fillOptions.value = saved.items;
    fillOptionsTitle.value = task.title || "";
    fillOptionsChecked.value = true;
    fillOptionsError.value = "";
    selectedFillKeys.value = saved.keys;
  } else {
    // 旧任务未配置提交项，仍走检测流程
    resetFillOptionsState();
  }
  nextTick(() => {
    suppressFillReset = false;
  });
}

// 根据任务保存的 fill_fields 合成检测结果（用于编辑时免检测渲染表单）
function buildSavedFillOptions(task) {
  if (!Array.isArray(task.fill_fields) || !task.fill_fields.length) return null;
  const knownNames = { 1: "签到文本", 2: "签到图片" };
  const items = [];
  const keys = new Set([String(LOCATION_KEY)]); // 位置始终提交
  let nameAssigned = false;
  for (const raw of task.fill_fields) {
    const k = String(raw);
    if (Number(k) === LOCATION_KEY) continue; // 展示逻辑会自动补位置标签
    keys.add(k);
    if (knownNames[k]) {
      items.push({ key: Number(k), name: knownNames[k], field_type: 0 });
    } else if (
      task.fill_name &&
      !nameAssigned &&
      !String(task.fill_values?.[k] ?? "").trim()
    ) {
      // 该 key 原为姓名项（值存在 fill_name 里）
      items.push({ key: Number(k), name: "签到姓名", field_type: 0 });
      nameAssigned = true;
    } else {
      items.push({ key: Number(k), name: `填写项 ${k}`, field_type: 0 });
    }
  }
  return { items, keys };
}

function applyMapLocation(location) {
  form.use_location = true;
  form.location_address = location.address || "";
  form.location_latitude = location.latitude;
  form.location_longitude = location.longitude;
  selectedMapLocation.value = { ...location };
}

async function customUpload(options) {
  try {
    const res = await api.uploadImage(options.file);
    if (res.data && res.data.path) {
      if (!Array.isArray(form.pic_path)) form.pic_path = [];
      form.pic_path.push(res.data.path);
      syncFileList();
    }
    options.onSuccess(res);
    ElMessage.success("图片上传成功");
  } catch (err) {
    options.onError(err);
    ElMessage.error(err.message || "图片上传失败");
  }
}

function onImageRemove(file, fileList) {
  const removedPath = file.path || file.url;
  form.pic_path = form.pic_path.filter((p) => {
    const pName = String(p).replace(/\\/g, "/").split("/").pop();
    const rName = String(removedPath).replace(/\\/g, "/").split("/").pop();
    return pName !== rName;
  });
  syncFileList();
}

async function fetchProjects() {
  if (selectedAccountIndex.value == null || projectsLoading.value) return;
  projectsLoading.value = true;
  try {
    const res = await api.fetchProjects(selectedAccountIndex.value);
    projects.value = res.data || [];
    selectedProjectIndex.value = -1;
    ElMessage.success(`项目列表获取成功，共 ${projects.value.length} 项`);
  } catch (err) {
    ElMessage.error(err.message || "项目列表获取失败");
  } finally {
    projectsLoading.value = false;
  }
}

async function detectFillOptions() {
  if (selectedAccountIndex.value == null || selectedAccountIndex.value < 0) {
    ElMessage.warning("请先选择账号");
    return;
  }
  if (fillOptionsLoading.value) return;
  fillOptionsLoading.value = true;
  fillOptionsError.value = "";
  try {
    const res = await api.fetchFillOptions(
      selectedAccountIndex.value,
      form.index || 1,
    );
    const data = res.data || {};
    fillOptions.value = data.items || [];
    fillOptionsTitle.value = data.title || "";
    fillOptionsChecked.value = true;
    // 编辑已有任务时优先沿用其保存的勾选，否则默认全选
    const currentTask = selectedActualIndex.value >= 0
      ? state.value.accounts[selectedAccountIndex.value]?.tasks?.[selectedActualIndex.value]
      : null;
    const savedFields = Array.isArray(currentTask?.fill_fields)
      ? currentTask.fill_fields.map(String)
      : null;
    selectedFillKeys.value = new Set(
      savedFields ?? fillOptions.value.map((item) => String(item.key)),
    );
    // 位置填写项始终勾选并提交
    selectedFillKeys.value.add(String(LOCATION_KEY));
    // 位置始终提交，默认改为自动获取位置
    if (locationMode.value === "none") {
      locationMode.value = "auto";
    }
    ElMessage.success(
      fillOptions.value.length
        ? `《${fillOptionsTitle.value}》检测到填写项：${fillOptions.value
            .map((item) => item.name)
            .join("、")}（不需要的可点击标签取消）`
        : `《${fillOptionsTitle.value}》未要求填写内容`,
    );
  } catch (err) {
    fillOptionsChecked.value = false;
    fillOptions.value = [];
    fillOptionsError.value = err.message || "填写项检测失败";
  } finally {
    fillOptionsLoading.value = false;
  }
}

function resetFillOptionsState() {
  fillOptions.value = [];
  fillOptionsTitle.value = "";
  fillOptionsChecked.value = false;
  fillOptionsError.value = "";
  selectedFillKeys.value = new Set();
}

function fillTagType(item) {
  const key = Number(item.key);
  if ([1, 2, 6].includes(key)) return "success";
  if ([0, 1].includes(Number(item.field_type))) return "success";
  return "warning";
}

watch([selectedAccountIndex, () => form.index], () => {
  if (suppressFillReset) return;
  resetFillOptionsState();
});

async function refreshSelectedAccountToken() {
  if (
    selectedAccountIndex.value == null ||
    selectedAccountIndex.value < 0 ||
    tokenRefreshing.value
  )
    return;
  tokenRefreshing.value = true;
  try {
    await api.refreshAccountToken(selectedAccountIndex.value);
    await Promise.all([refreshState(), refreshLogs()]);
    ElMessage.success(
      `账号「${currentAccount.value?.name || "当前账号"}」Token 已刷新`,
    );
  } catch (err) {
    ElMessage.error(err.message || "Token 刷新失败");
  } finally {
    tokenRefreshing.value = false;
  }
}

function applyProject(idx, item) {
  const hadTaskSelected = selectedActualIndex.value >= 0;
  if (hadTaskSelected) {
    // 从编辑任务切换到重新新建：取消任务选中并清空表单
    selectedActualIndex.value = -1;
    taskTableRef.value?.setCurrentRow?.(null);
    form.title = "";
    form.times = [];
    timesText.value = "";
    form.text = "";
    form.fill_name = "";
    form.fill_values = {};
    form.fill_fields = null;
    form.pic_path = [];
    form.enable = true;
    form.use_location = false;
    form.location_address = "";
    form.location_latitude = null;
    form.location_longitude = null;
    selectedMapLocation.value = null;
    form.skip_weekends = false;
    form.date_mode = "daily";
    form.run_dates = [];
    form.skip_dates = [];
    form.auto_disable_after_finish = true;
    form.mode = "normal";
    form.notify_wechat = true;
    locationMode.value = "none";
    fileList.value = [];
    resetFillOptionsState();
  }
  selectedProjectIndex.value = idx;
  form.index = idx + 1;
  if (!form.title) form.title = item.title || `任务${idx + 1}`;
}

watch(
  () => form.index,
  (val) => {
    if (selectedProjectIndex.value >= 0 && val !== selectedProjectIndex.value + 1) {
      selectedProjectIndex.value = -1;
    }
  },
);

async function saveTask() {
  if (!fillOptionsChecked.value) {
    ElMessage.warning("请先点击「检测填写项」，检测成功后再保存任务");
    return;
  }
  // Parse the latest raw value before validation/submission without rewriting
  // what the user typed into the input.
  form.times = parseTimesText(timesText.value);
  // 位置始终提交，保存时强制带上
  form.fill_fields = [...new Set([...selectedFillKeys.value, String(LOCATION_KEY)])];
  if (
    hasLocationFill.value
    && locationMode.value === "map"
    && (form.location_latitude == null || form.location_longitude == null)
  ) {
    ElMessage.warning("请先通过地图选择签到位置");
    return;
  }
  if (form.date_mode === "specific" && !form.run_dates.length) {
    ElMessage.warning("指定日期模式下请至少选择一个执行日期");
    return;
  }
  if (!form.times.length) {
    formRef.value?.validateField("times").catch(() => {});
    ElMessage.warning("请至少设置一个执行时间");
    return;
  }
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;
  if (selectedAccountIndex.value == null) {
    ElMessage.warning("请先选择账号");
    return;
  }
  form.mode = form.pic_path && form.pic_path.length ? "image" : "normal";
  if (!isAdmin) form.notify_wechat = true;
  try {
    const account = state.value.accounts[selectedAccountIndex.value];
    const tasks = account?.tasks || [];
    const existingTaskIndex = tasks.findIndex((t) => t.index === form.index);

    const taskPayload = buildXxqdTaskPayload(
      form,
      locationMode.value,
      selectedMapLocation.value,
    );
    if (existingTaskIndex >= 0) {
      await api.updateTask(selectedAccountIndex.value, existingTaskIndex, {
        ...taskPayload,
      });
      ElMessage.success("任务已更新");
    } else {
      const projectCount = account?.projects?.length || 0;
      if (projectCount > 0 && tasks.length >= projectCount) {
        ElMessage.warning(
          `任务数量已达上限，最多可添加 ${projectCount} 个任务`,
        );
        return;
      }
      await api.addTask(selectedAccountIndex.value, taskPayload);
      ElMessage.success("任务已新增");
      createNew();
    }
    await refreshState();
    await refreshLogs();
    emit("saved");
  } catch (err) {
    ElMessage.error(err.message);
  }
}

async function runTask() {
  if (
    runningTask.value ||
    selectedAccountIndex.value == null ||
    selectedActualIndex.value < 0
  )
    return;
  runningTask.value = true;
  try {
    const res = await api.runTask(
      selectedAccountIndex.value,
      selectedActualIndex.value,
    );
    checkinResult.value = createCheckinResult(res.data || {});
    applyMembershipUpdate(res.data || {});
    checkinResultVisible.value = true;
    await refreshLogs();
  } catch (err) {
    ElMessage.error(err.message);
  } finally {
    runningTask.value = false;
  }
}

async function deleteTask() {
  try {
    await ElMessageBox.confirm("确认删除当前任务吗？", "提示", {
      type: "warning",
    });
    await api.deleteTask(selectedAccountIndex.value, selectedActualIndex.value);
    createNew();
    await refreshState();
    await refreshLogs();
    ElMessage.success("任务已删除");
  } catch (err) {
    if (err !== "cancel") ElMessage.error(err.message);
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
.card-header-right { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.detect-status-item :deep(.el-alert) { width:100%; }
.fill-detect-result { width:100%; margin-bottom:14px; padding:10px 14px; border:1px dashed #bfdbfe; border-radius:10px; background:#f8fbff; }
.fill-detect-result > span { color:#94a3b8; font-size:11px; }
.fill-detect-tags { display:flex; align-items:center; flex-wrap:wrap; gap:6px; margin-top:6px; }
.fill-detect-empty { color:#64748b; font-size:12px; }
.fill-option-tag { cursor:pointer; user-select:none; }
.fill-detect-tip { width:100%; color:#94a3b8; font-size:11px; }
.page-container {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  overflow-x: clip;
}
.task-layout,
.task-layout > .el-col,
.task-list-card,
.task-form-card,
.task-form-card :deep(.el-card__body),
.task-form-card :deep(.el-form),
.task-form-card :deep(.el-form-item),
.task-form-card :deep(.el-form-item__content) {
  min-width: 0;
  max-width: 100%;
}
.task-form-card :deep(.el-card__body) {
  overflow-x: hidden;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 500;
}
.section-header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
.project-section {
  background: #f8fafc;
  border-radius: 12px;
  padding: 16px;
  margin-top: 16px;
}
.project-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  margin-bottom: 6px;
  background: #fff;
  transition: all 0.2s ease;
}
.project-item:hover {
  background: #eef4ff;
  border-color: #dbeafe;
  transform: translateX(4px);
}
.project-item.is-active {
  background: #eff6ff;
  border-color: #2563eb;
  box-shadow: inset 3px 0 0 #2563eb;
}
.project-item.is-active .project-title {
  color: #1d4ed8;
  font-weight: 600;
}
.project-item.is-active .project-index {
  background: #2563eb;
  color: #fff;
}
.project-check {
  margin-left: auto;
  color: #2563eb;
  font-size: 16px;
  flex-shrink: 0;
}
.project-index {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e0e7ff;
  color: #4338ca;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.project-title {
  font-size: 14px;
  color: #334155;
}
.upload-tip {
  width: 100%;
  min-width: 0;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
}
.mobile-task-list {
  display: none;
}
.task-account-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.task-secondary-grid {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* The sidebar reduces the real content width considerably.  Keep the two
   cards stacked until there is enough room for the form labels and calendar. */
@media (max-width: 1600px) {
  .task-layout {
    row-gap: 16px;
  }

  .task-layout > .el-col {
    max-width: 100%;
    flex: 0 0 100%;
  }

  .task-form-card :deep(.el-form) {
    width: 100%;
    max-width: 980px;
    margin: 0 auto;
  }
}

@media (max-width: 768px) {
  .task-layout {
    row-gap: 8px;
  }
  .desktop-task-table {
    display: none;
  }
  .mobile-task-list {
    display: grid;
    gap: 8px !important;
    background: #f1f5f9;
  }
  .mobile-task-card {
    overflow: hidden;
    border: 0 !important;
    border-left: 3px solid #cbd5e1 !important;
    border-radius: 0;
    background: #fff;
    transition:
      border-color 0.2s,
      background 0.2s;
  }
  .mobile-task-card.is-active {
    border-left: 3px solid #3b82f6 !important;
    background: #f4f8ff !important;
    box-shadow: none !important;
  }
  .mobile-task-card.is-active > header,
  .mobile-task-card.is-active > p,
  .mobile-task-card.is-active > .mobile-task-card__facts,
  .mobile-task-card.is-active > footer {
    background: transparent !important;
  }
  .mobile-task-card header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 14px 16px 8px;
  }
  .mobile-task-card__heading {
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-width: 0;
  }
  .mobile-task-card header strong,
  .mobile-task-card__heading span {
    display: block;
  }
  .mobile-task-card header strong {
    overflow: hidden;
    color: #172033;
    font-size: 16px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mobile-task-card__heading span {
    flex: none;
    color: #94a3b8;
    font-size: 11px;
  }
  .mobile-task-card > p {
    margin: 0;
    padding: 0 16px 12px;
    color: #475569;
    font-size: 12px;
    line-height: 1.55;
    overflow-wrap: anywhere;
  }
  .mobile-task-card > p.is-empty {
    color: #94a3b8;
  }
  .mobile-task-card__facts {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0;
    padding: 0 16px 13px;
  }
  .mobile-task-card__facts span {
    min-width: 0;
    padding-left: 10px;
    border-left: 1px solid #e2e8f0;
    color: #94a3b8;
    font-size: 11px;
  }
  .mobile-task-card__facts span:first-child {
    padding-left: 0;
    border-left: 0;
  }
  .mobile-task-card__facts strong {
    display: block;
    margin-top: 3px;
    overflow: hidden;
    color: #334155;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mobile-task-card footer {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 8px;
    min-height: 42px;
    padding: 8px 16px;
    border-top: 1px solid #e2e8f0;
    color: #64748b;
    font-size: 11px;
  }
  .mobile-task-card__policies {
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .mobile-task-card__policies span {
    padding: 3px 7px;
    border-radius: 999px;
    color: #475569;
    background: #f1f5f9;
  }
  .task-account-toolbar {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    width: 100%;
  }
  .task-account-toolbar .el-select {
    width: 100% !important;
  }
  .task-account-toolbar .el-button {
    min-height: 40px;
    margin: 0;
  }
  .task-account-toolbar .el-tag {
    grid-column: 1 / -1;
    justify-self: start;
  }
  .section-header {
    align-items: center;
    gap: 8px;
  }
  .section-header .el-button {
    min-height: 40px;
    margin: 0;
  }
  .project-section {
    margin: 8px -16px 0;
    padding: 16px;
    border-top: 8px solid #f1f5f9;
    border-radius: 0;
    background: #fff;
  }

  .project-item {
    padding: 10px;
  }

  .project-title {
    font-size: 13px;
  }

  .task-settings-form :deep(.el-form-item) {
    display: block;
    margin-bottom: 20px;
  }
  .task-settings-form :deep(.el-form-item__label) {
    display: block;
    width: 100% !important;
    height: auto;
    margin-bottom: 8px;
    padding: 0;
    font-size: 13px;
    line-height: 1.4;
    text-align: left;
  }
  .task-settings-form :deep(.el-form-item__content) {
    width: 100%;
    margin-left: 0 !important;
  }
  .task-primary-actions :deep(.el-form-item__content) {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
  }
  .task-primary-actions .el-button {
    min-height: 44px;
    margin: 0;
  }
  .task-secondary-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }
  .task-secondary-grid .el-button {
    width: 100%;
    min-height: 44px;
    margin: 0;
  }
}

@media (max-width: 480px) {
  .mobile-task-card__facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px 0;
  }
  .mobile-task-card__facts span:nth-child(3) {
    padding-left: 0;
    border-left: 0;
  }
  .project-section {
    padding: 14px 16px;
  }

  .project-item {
    padding: 8px;
    gap: 8px;
  }

  .project-index {
    width: 22px;
    height: 22px;
    font-size: 11px;
  }

  .project-title {
    font-size: 12px;
  }

  .task-account-toolbar {
    grid-template-columns: 1fr;
  }
  .task-account-toolbar .el-button {
    width: 100%;
  }
  .task-settings-form :deep(.el-form-item__label) {
    font-size: 12px;
  }
}
</style>
