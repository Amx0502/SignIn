<template>
  <div class="login-page">
    <div class="login-shell">
      <section class="brand-panel">
        <div class="brand-heading">
          <img :src="logoImage" alt="轻签系统图标" class="brand-logo" />
          <div><strong>轻签</strong><span>多平台自动化签到管理中台</span></div>
        </div>
        <div class="brand-copy">
          <p class="eyebrow">统一管理，轻松签到</p>
          <h1>一个后台<br />连接多种签到工具</h1>
          <p>集中管理账号、自动任务、定位搜索和运行记录，让重复操作交给系统完成。</p>
        </div>
      </section>

      <section class="form-panel">
        <div class="form-card">
          <a class="back-home" href="/" title="返回官网">‹ 返回官网</a>
          <div class="form-heading">
            <div class="form-icon"><img :src="logoImage" alt="轻签" /></div>
            <div><h2>轻签</h2></div>
          </div>

          <el-form ref="loginForm" :model="form" :rules="rules" class="login-form" label-position="top" @submit.prevent="handleLogin">
            <el-form-item prop="username">
              <template #label><span class="field-label">用户名</span></template>
              <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" size="large" :disabled="loading" @keyup.enter="handleLogin" />
            </el-form-item>
            <el-form-item prop="password">
              <template #label><span class="field-label">密码</span></template>
              <el-input v-model="form.password" type="password" placeholder="请输入密码" :prefix-icon="Lock" size="large" show-password :disabled="loading" @keyup.enter="handleLogin" />
            </el-form-item>
            <el-form-item class="submit-item">
              <el-button type="primary" size="large" class="login-btn" :loading="loading" native-type="submit">{{ loading ? '登录中...' : '登录' }}</el-button>
            </el-form-item>
          </el-form>

          <div class="form-footer"><span>没有账号？</span><a href="#purchase" @click.prevent="openPurchasePage">前往购买会员卡</a></div>
        </div>
      </section>

      <section class="platform-panel">
        <div class="platform-strip">
          <div class="platform-item"><img :src="xxqdImage" alt="小小签到" /><span>小小签到</span></div>
          <div class="platform-item"><img :src="classCubeImage" alt="班级魔方" /><span>班级魔方</span></div>
          <div class="platform-item"><img :src="miaoyingImage" alt="秒应" /><span>秒应</span></div>
          <div class="platform-item platform-item--more"><el-icon><Plus /></el-icon><span>更多工具</span></div>
        </div>
        <p class="platform-note"><span></span>更多常用工具持续接入中</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { Lock, Plus, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getSiteConfigApi, loginApi } from '../api'
import logoImage from '../img/logo.png'
import xxqdImage from '../img/xxqd.png'
import classCubeImage from '../img/bjmf.png'
import miaoyingImage from '../img/miaoying.png'

const loginForm = ref(null)
const loading = ref(false)
const purchaseUrl = ref('https://m.tb.cn/h.8sGQxfh?tk=Dz6vT8OEx7h')
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

async function loadPurchaseUrl() {
  try {
    const response = await getSiteConfigApi()
    purchaseUrl.value = response.data.purchase_url || purchaseUrl.value
  } catch {
    // Keep the default purchase address when the public config is unavailable.
  }
}
function openPurchasePage() { window.open(purchaseUrl.value, '_blank', 'noopener,noreferrer') }

async function handleLogin() {
  if (!loginForm.value) return
  try {
    const valid = await loginForm.value.validate()
    if (!valid) return
    loading.value = true
    const response = await loginApi({ username: form.username, password: form.password })
    if (response.ok) {
      const { access_token, expires_at, user } = response.data
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('expires_at', expires_at)
      localStorage.setItem('user', JSON.stringify(user))
      ElMessage.success('登录成功')
      const redirect = new URLSearchParams(window.location.search).get('redirect') || '/dashboard'
      window.location.href = redirect
    } else {
      ElMessage.error(response.error || '登录失败')
    }
  } catch (error) {
    ElMessage.error(error?.message || '登录失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
loadPurchaseUrl()
</script>

<style scoped>
.login-page { --primary:#3157d5; --text:#172033; --muted:#64748b; --border:#dce5f2; display:grid; min-height:100vh; padding:28px; place-items:center; color:var(--text); background:radial-gradient(circle at 12% 10%,#dce6ff 0,transparent 30%),linear-gradient(145deg,#f8faff 0%,#eef3ff 100%); font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; }
.login-shell { display:grid; width:min(1120px,100%); min-height:680px; grid-template-columns:1.05fr .95fr; grid-template-areas:"brand form" "platform form"; grid-template-rows:minmax(0,1fr) auto; overflow:hidden; border:1px solid rgb(205 218 240 / 92%); border-radius:26px; background:#fff; box-shadow:0 28px 70px rgb(35 63 122 / 14%); }
.brand-panel { display:flex; grid-area:brand; padding:48px 48px 24px; flex-direction:column; justify-content:center; background:linear-gradient(150deg,#f8fbff 0%,#e9f0ff 58%,#dfe8ff 100%); }
.brand-heading { display:flex; align-items:center; gap:13px; }
.brand-logo { width:48px; height:48px; object-fit:contain; }
.brand-heading strong,.brand-heading span { display:block; }
.brand-heading strong { font-size:22px; }
.brand-heading span { margin-top:2px; color:var(--muted); font-size:12px; }
.brand-copy { max-width:480px; }
.eyebrow { margin:0 0 12px; color:var(--primary); font-size:12px; font-weight:800; letter-spacing:.08em; }
.brand-copy h1 { margin:0; color:#15233d; font-size:42px; line-height:1.24; }
.brand-copy > p:last-child { margin:20px 0 0; color:#5b6b84; font-size:15px; line-height:1.85; }
.platform-strip { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
.platform-item { display:flex; min-height:58px; padding:10px 12px; align-items:center; gap:10px; border:1px solid rgb(211 222 240 / 88%); border-radius:13px; background:rgb(255 255 255 / 76%); color:#334155; font-size:13px; font-weight:700; }
.platform-item img { width:32px; height:32px; object-fit:contain; }
.platform-item--more { color:var(--primary); background:rgb(238 243 255 / 86%); }
.platform-item--more .el-icon { width:32px; font-size:20px; }
.platform-note { display:flex; margin:0; align-items:center; gap:8px; color:#64748b; font-size:12px; }
.platform-note span { width:7px; height:7px; border-radius:50%; background:#22a06b; box-shadow:0 0 0 4px rgb(34 160 107 / 11%); }
.platform-panel { display:grid; grid-area:platform; padding:0 48px 44px; gap:12px; background:linear-gradient(180deg,#dfe8ff 0%,#e9f0ff 100%); }
.form-panel { display:grid; grid-area:form; padding:48px; place-items:center; background:#fff; }
.form-card { width:min(410px,100%); padding:34px 30px; border:1px solid #e3eaf6; border-radius:20px; background:#fff; box-shadow:0 18px 48px rgb(35 63 122 / 9%); }
.back-home { display:inline-block; margin-bottom:20px; color:var(--muted); font-size:13px; font-weight:600; text-decoration:none; transition:color .2s; }
.back-home:hover { color:var(--primary); }
.form-heading { display:flex; margin-bottom:30px; align-items:center; gap:13px; }
.form-icon { display:grid; width:52px; height:52px; flex:none; place-items:center; border-radius:15px; background:#eef3ff; }
.form-icon img { width:40px; height:40px; object-fit:contain; }
.form-heading h2 { margin:0; font-size:24px; }
.form-heading p { margin:5px 0 0; color:var(--muted); font-size:12px; }
.login-form :deep(.el-form-item) { margin-bottom:18px; }
.login-form :deep(.el-form-item__label) { height:auto; padding:0 0 4px; margin:0; line-height:1.4; }
.field-label { display:inline; color:#485870; font-size:13px; font-weight:600; }
.login-form :deep(.el-input) { height:48px; }
.login-form :deep(.el-input__wrapper) { height:48px; min-height:48px; padding-inline:14px; align-items:center; border-radius:10px; box-shadow:0 0 0 1px #d9e2ef inset; }
.login-form :deep(.el-input__wrapper:hover) { box-shadow:0 0 0 1px #9fb5e8 inset; }
.login-form :deep(.el-input__wrapper.is-focus) { box-shadow:0 0 0 2px rgb(49 87 213 / 18%),0 0 0 1px var(--primary) inset; }
.login-form :deep(.el-input__prefix) { display:flex; width:20px; height:100%; align-items:center; justify-content:center; }
.login-form :deep(.el-input__inner) { height:48px; line-height:48px; }
.login-form :deep(.el-input__suffix) { height:100%; align-items:center; }
.submit-item { margin-top:24px !important; margin-bottom:0 !important; }
.login-btn { width:100%; min-height:48px; border:0; border-radius:10px; background:var(--primary); font-size:15px; font-weight:800; box-shadow:0 8px 20px rgb(49 87 213 / 18%); }
.login-btn:hover { background:#2849bd; }
.form-footer { display:flex; margin-top:24px; justify-content:center; gap:5px; color:var(--muted); font-size:12px; }
.form-footer a { color:var(--primary); font-weight:700; text-decoration:none; }
.form-footer a:hover { text-decoration:underline; }
@media (max-width:900px) {
  .login-page { display:grid; min-height:100dvh; padding:24px 20px; place-items:center; background:linear-gradient(180deg,#f3f7ff 0%,#fff 50%,#eef4ff 100%); }
  .login-shell { display:grid; width:100%; max-width:420px; min-height:auto; grid-template-columns:1fr; grid-template-areas:"form"; grid-template-rows:1fr; gap:0; overflow:visible; border:0; border-radius:0; box-shadow:none; background:transparent; }
  .brand-panel { display:none; }
  .platform-panel { display:none; }
  .form-panel { padding:0; border:0; border-radius:0; background:transparent; box-shadow:none; }
  .form-card { width:100%; padding:36px 28px; border:0; border-radius:20px; background:#fff; box-shadow:0 8px 40px rgb(35 63 122 / 10%); }
  .form-heading { display:flex; flex-direction:column; align-items:center; text-align:center; margin-bottom:32px; gap:14px; }
  .form-icon { width:64px; height:64px; border-radius:18px; }
  .form-icon img { width:48px; height:48px; }
  .form-heading h2 { font-size:24px; }
  .form-heading p { font-size:13px; line-height:1.5; }
  .login-form :deep(.el-form-item) { margin-bottom:16px; }
  .login-form :deep(.el-form-item__label) { padding:0 0 4px; margin:0; font-size:13px; font-weight:600; line-height:1.4; }
  .login-form :deep(.el-input),.login-form :deep(.el-input__wrapper),.login-form :deep(.el-input__inner) { height:48px; min-height:48px; }
  .login-form :deep(.el-input__inner) { line-height:48px; }
  .login-form :deep(.el-input__wrapper) { border-radius:10px; background:#eef3ff; box-shadow:0 0 0 1px transparent inset; }
  .login-form :deep(.el-input__wrapper.is-focus) { box-shadow:0 0 0 2px rgb(37 99 235 / 15%),0 0 0 1px #2563eb inset; background:#fff; }
  .submit-item { margin-top:24px !important; }
  .login-btn { min-height:48px; font-size:16px; border-radius:10px; background:#2563eb; box-shadow:0 8px 20px rgb(37 99 235 / 18%); }
  .login-btn:hover { background:#1d4ed8; }
  .form-footer { margin-top:24px; justify-content:center; font-size:13px; }
}
@media (max-width:380px) {
  .login-page { padding:16px 16px; }
  .form-card { padding:28px 20px; }
  .form-heading h2 { font-size:22px; }
  .form-heading p { display:none; }
}
@media (max-width:520px) and (max-height:740px) {
  .brand-copy,.platform-note { display:none; }
  .brand-panel { gap:10px; }
  .platform-panel { gap:0; }
  .platform-item { min-height:44px; }
}
</style>
