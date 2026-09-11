<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>账号列表</span>
              <div class="account-toolbar">
                <el-button
                  type="primary"
                  :icon="Plus"
                  size="small"
                  @click="createNew"
                  >新增账号</el-button
                >
                <el-button
                  type="danger"
                  :icon="Delete"
                  size="small"
                  :disabled="selectedAccounts.length === 0 || batchDeleting"
                  :loading="batchDeleting"
                  @click="deleteSelectedAccounts"
                  >批量删除({{ selectedAccounts.length }})</el-button
                >
                <el-button
                  type="warning"
                  :icon="Refresh"
                  size="small"
                  @click="refreshAllTokens"
                  >全局刷新Token</el-button
                >
              </div>
            </div>
          </template>
          <div class="account-search-bar">
            <el-input
              v-model="accountKeyword"
              clearable
              :prefix-icon="Search"
              placeholder="搜索名称或手机号"
              aria-label="搜索小小签到账号"
            />
            <span
              >显示 {{ filteredAccounts.length }}/{{
                state.accounts.length
              }}
              个账号</span
            >
          </div>
          <el-table
            class="desktop-account-table"
            ref="tableRef"
            :data="filteredAccounts"
            row-key="mobile"
            highlight-current-row
            @current-change="onSelectAccount"
            @selection-change="onSelectionChange"
            style="width: 100%"
            max-height="560"
          >
            <el-table-column type="selection" width="48" reserve-selection />
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="mobile" label="手机号" min-width="120" />
            <el-table-column label="任务数" width="90">
              <template #default="scope">{{
                (scope.row.tasks || []).length
              }}</template>
            </el-table-column>
            <el-table-column label="Token" min-width="180">
              <template #default="scope">
                <el-tooltip :content="scope.row.token || '无'" placement="top">
                  <span>{{
                    scope.row.token ? scope.row.token.slice(0, 24) + "..." : "-"
                  }}</span>
                </el-tooltip>
              </template>
            </el-table-column>
          </el-table>
          <div class="mobile-account-list">
            <el-empty
              v-if="!filteredAccounts.length"
              description="暂无匹配账号"
            />
            <article
              v-for="account in filteredAccounts"
              :key="account.mobile"
              class="mobile-account-card"
              :class="{ 'is-active': selectedMobile === account.mobile }"
              @click="onSelectAccount(account)"
            >
              <header>
                <el-checkbox
                  :model-value="isAccountSelected(account)"
                  :aria-label="`选择账号 ${account.name}`"
                  @click.stop
                  @change="
                    (checked) => toggleMobileAccountSelection(account, checked)
                  "
                />
                <div class="account-avatar" aria-hidden="true">
                  {{ String(account.name || "账").slice(0, 1) }}
                </div>
                <div class="account-identity">
                  <strong>{{ account.name }}</strong>
                  <div class="account-meta">
                    <span>{{ account.mobile }}</span>
                    <span>{{ (account.tasks || []).length }} 个任务</span>
                  </div>
                </div>
                <div class="account-state">
                  <span
                    class="token-status"
                    :class="{ 'is-empty': !account.token }"
                    >{{ account.token ? "Token 有效" : "无 Token" }}</span
                  >
                </div>
              </header>
            </article>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ selectedIndex >= 0 ? "编辑账号" : "新增账号" }}</span>
            </div>
          </template>
          <el-form
            class="account-form"
            :model="form"
            label-width="100px"
            :rules="rules"
            ref="formRef"
          >
            <el-form-item label="账号名称" prop="name">
              <el-input v-model="form.name" />
            </el-form-item>
            <el-form-item label="手机号" prop="mobile">
              <el-input v-model="form.mobile" />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="form.password" type="password" show-password />
            </el-form-item>
            <el-form-item class="form-primary-actions">
              <el-button type="primary" @click="saveAccount">{{
                selectedIndex >= 0 ? "保存账号" : "新增账号"
              }}</el-button>
              <el-button @click="createNew">重置</el-button>
            </el-form-item>
            <el-form-item
              v-if="selectedIndex >= 0"
              class="account-secondary-actions"
            >
              <div class="account-action-grid">
                <el-button type="success" :icon="Key" @click="loginAccount"
                  >登录获取 Token</el-button
                >
                <el-button type="warning" :icon="Refresh" @click="refreshToken"
                  >刷新 Token</el-button
                >
                <el-button type="danger" :icon="Delete" @click="deleteAccount"
                  >删除账号</el-button
                >
              </div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import {
  Plus,
  Key,
  Refresh,
  Delete,
  Search,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useAppState } from "../composables/useAppState";
import { getAccountDeleteIndexes } from "../utils/batchDelete";
import {
  reconcileAccountSelection,
  selectedAccountIndex,
} from "../utils/accountEditor.js";
import api from "../api";

const { state, refreshState, refreshLogs } = useAppState();

const formRef = ref(null);
const tableRef = ref(null);
const selectedIndex = ref(-1);
const selectedMobile = ref("");
const selectedAccounts = ref([]);
const batchDeleting = ref(false);
const accountKeyword = ref("");
const filteredAccounts = computed(() => {
  const keyword = accountKeyword.value.trim().toLowerCase();
  if (!keyword) return state.value.accounts;
  return state.value.accounts.filter((account) =>
    [account.name, account.mobile].some((value) =>
      String(value || "")
        .toLowerCase()
        .includes(keyword),
    ),
  );
});
const form = reactive({
  name: "",
  mobile: "",
  password: "",
  token: "",
});

const rules = {
  name: [{ required: true, message: "请输入账号名称", trigger: "blur" }],
  mobile: [{ required: true, message: "请输入手机号", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

function createNew() {
  tableRef.value?.setCurrentRow(null);
  selectedIndex.value = -1;
  selectedMobile.value = "";
  form.name = "";
  form.mobile = "";
  form.password = "";
  form.token = "";
}

function onSelectAccount(row) {
  if (!row) return;
  const selection = reconcileAccountSelection({
    accounts: state.value.accounts,
    row,
    selectedMobile: selectedMobile.value,
    draft: form,
  });
  selectedIndex.value = selection.index;
  if (!selection.shouldHydrateDraft) return;
  selectedMobile.value = selection.selectedMobile;
  Object.assign(form, selection.draft);
}

function onSelectionChange(rows) {
  selectedAccounts.value = rows;
}

function isAccountSelected(account) {
  return selectedAccounts.value.some((item) => item.mobile === account.mobile);
}

function toggleMobileAccountSelection(account, checked) {
  tableRef.value?.toggleRowSelection(account, checked);
}

async function saveAccount() {
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;
  try {
    if (selectedIndex.value >= 0) {
      const currentIndex = selectedAccountIndex(
        state.value.accounts,
        selectedMobile.value,
      );
      if (currentIndex < 0) throw new Error("当前账号已不存在，请重新选择");
      selectedIndex.value = currentIndex;
      await api.updateAccount(currentIndex, { ...form });
      ElMessage.success("账号已更新");
    } else {
      await api.addAccount({
        name: form.name,
        mobile: form.mobile,
        password: form.password,
        token: "",
      });
      await refreshState();
      const newIndex = state.value.accounts.length - 1;
      if (newIndex >= 0) {
        await api.loginAccount(newIndex);
        ElMessage.success("账号已新增并自动登录获取 Token");
      } else {
        ElMessage.success("账号已新增");
      }
      createNew();
    }
    await refreshState();
    await refreshLogs();
  } catch (err) {
    ElMessage.error(err.message);
  }
}

async function loginAccount() {
  try {
    const res = await api.loginAccount(selectedIndex.value);
    form.token = res.data.token;
    ElMessage.success("登录成功");
    await refreshState();
    await refreshLogs();
  } catch (err) {
    ElMessage.error(err.message);
  }
}

async function refreshToken() {
  try {
    const res = await api.refreshAccountToken(selectedIndex.value);
    form.token = res.data.token;
    ElMessage.success("Token 已刷新");
    await refreshState();
    await refreshLogs();
  } catch (err) {
    ElMessage.error(err.message);
  }
}

async function deleteAccount() {
  try {
    await ElMessageBox.confirm("确认删除当前账号吗？", "提示", {
      type: "warning",
    });
    await api.deleteAccount(selectedIndex.value);
    createNew();
    await refreshState();
    await refreshLogs();
    ElMessage.success("账号已删除");
  } catch (err) {
    if (err !== "cancel") ElMessage.error(err.message);
  }
}

async function deleteSelectedAccounts() {
  const count = selectedAccounts.value.length;
  if (!count || batchDeleting.value) return;

  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${count} 个账号吗？`,
      "批量删除账号",
      { type: "warning" },
    );
  } catch (err) {
    if (err === "cancel" || err === "close") return;
    ElMessage.error(err.message || "操作失败");
    return;
  }

  batchDeleting.value = true;
  try {
    const indexes = getAccountDeleteIndexes(
      state.value.accounts,
      selectedAccounts.value,
    );
    for (const index of indexes) {
      await api.deleteAccount(index);
    }
    createNew();
    selectedAccounts.value = [];
    await refreshState();
    await refreshLogs();
    ElMessage.success(`已删除 ${indexes.length} 个账号`);
  } catch (err) {
    createNew();
    selectedAccounts.value = [];
    await Promise.allSettled([refreshState(), refreshLogs()]);
    ElMessage.error(err.message || "批量删除账号失败");
  } finally {
    batchDeleting.value = false;
  }
}

async function refreshAllTokens() {
  try {
    const res = await api.refreshAllTokens();
    ElMessage.success(
      `全局刷新Token完成，成功${res.data?.success_count || 0}个账号`,
    );
    await refreshState();
    await refreshLogs();
  } catch (err) {
    ElMessage.error(err.message);
  }
}
</script>

<style scoped>
.account-search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.account-search-bar .el-input {
  max-width: 360px;
}
.account-search-bar span {
  flex: none;
  color: #64748b;
  font-size: 12px;
}
.mobile-account-list {
  display: none;
}
.account-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.account-action-grid {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .desktop-account-table {
    display: none;
  }
  .mobile-account-list {
    display: grid;
    gap: 10px;
  }
  .mobile-account-card {
    border: 1px solid #e1e9f4;
    border-radius: 13px;
    background: #fff;
    transition:
      border-color 0.2s,
      background 0.2s;
  }
  .mobile-account-card.is-active {
    border-color: #60a5fa;
    background: #f4f8ff;
    box-shadow: 0 0 0 2px rgb(59 130 246 / 8%);
  }
  .mobile-account-card header {
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 11px;
    min-height: 76px;
    padding: 10px 13px;
  }
  .mobile-account-card header strong {
    display: block;
  }
  .mobile-account-card header strong {
    overflow: hidden;
    color: #172033;
    font-size: 14px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .account-avatar {
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border-radius: 11px;
    color: #1d4ed8;
    background: #eaf2ff;
    font-size: 15px;
    font-weight: 800;
  }
  .account-identity {
    min-width: 0;
  }
  .account-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
    color: #718096;
    font-size: 11px;
  }
  .account-meta span + span::before {
    margin-right: 8px;
    color: #cbd5e1;
    content: "·";
  }
  .account-state {
    justify-self: end;
  }
  .token-status {
    color: #4d7c0f;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
  }
  .token-status::before {
    display: inline-block;
    width: 6px;
    height: 6px;
    margin-right: 5px;
    border-radius: 50%;
    background: #84cc16;
    content: "";
    vertical-align: 1px;
  }
  .token-status.is-empty {
    color: #94a3b8;
  }
  .token-status.is-empty::before {
    background: #cbd5e1;
  }
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .account-toolbar {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }
  .account-toolbar .el-button {
    width: 100%;
    min-height: 40px;
    margin: 0;
  }
  .account-toolbar .el-button:last-child {
    grid-column: 1 / -1;
  }
  .account-search-bar {
    align-items: stretch;
    flex-direction: column;
  }
  .account-search-bar .el-input {
    max-width: none;
  }
  .account-form :deep(.el-form-item) {
    display: block;
    margin-bottom: 18px;
  }
  .account-form :deep(.el-form-item__label) {
    display: block;
    width: 100% !important;
    height: auto;
    margin-bottom: 7px;
    padding: 0;
    line-height: 1.4;
    text-align: left;
  }
  .account-form :deep(.el-form-item__content) {
    width: 100%;
    margin-left: 0 !important;
  }
  .form-primary-actions :deep(.el-form-item__content) {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
  }
  .form-primary-actions .el-button {
    min-height: 42px;
    margin: 0;
  }
  .account-action-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }
  .account-action-grid .el-button {
    width: 100%;
    min-height: 42px;
    margin: 0;
    white-space: normal;
  }
  .account-action-grid .el-button:last-child {
    grid-column: 1 / -1;
  }
}
</style>
