<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <div class="brand-logo">
          <img src="../img/xxqd.png" alt="Logo" class="logo-img" />
        </div>
        <h1>超级签到</h1>
        <p>专业的自动化签到管理系统</p>
      </div>
      
      <el-form ref="loginForm" :model="form" :rules="rules" class="login-form">
        <el-form-item prop="username">
          <el-input 
            v-model="form.username" 
            placeholder="用户名" 
            prefix-icon="User"
            size="large"
            :disabled="loading"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input 
            v-model="form.password" 
            type="password" 
            placeholder="密码" 
            prefix-icon="Lock"
            size="large"
            :disabled="loading"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        
        <el-form-item class="form-row">
          <el-checkbox v-model="form.rememberMe" :disabled="loading">
            记住登录状态
          </el-checkbox>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            size="large" 
            class="login-btn"
            :loading="loading"
            @click="handleLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { loginApi } from '../api'

const router = useRouter()

const loginForm = ref(null)

const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  rememberMe: false
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }, { min: 6, message: '密码至少6位', trigger: 'blur' }]
}

async function handleLogin() {
  if (!loginForm.value) return
  
  try {
    const valid = await loginForm.value.validate()
    if (!valid) return
    
    loading.value = true
    
    const response = await loginApi({
      username: form.username,
      password: form.password,
      remember_me: form.rememberMe
    })
    
    if (response.ok) {
      const { access_token, expires_at, user } = response.data
      
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('expires_at', expires_at)
      localStorage.setItem('user', JSON.stringify(user))
      
      ElMessage.success('登录成功')
      
      const urlParams = new URLSearchParams(window.location.search)
      const redirect = urlParams.get('redirect') || '/overview'
      window.location.href = redirect
    } else {
      ElMessage.error(response.error || '登录失败')
    }
  } catch (error) {
    ElMessage.error('登录失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px);
  border-radius: 24px;
  padding: 40px 32px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.brand-logo {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  border-radius: 20px;
  background: linear-gradient(135deg, #60a5fa, #2563eb);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 30px rgba(37, 99, 235, 0.3);
}

.logo-img {
  width: 50px;
  height: 50px;
  object-fit: contain;
}

.login-header h1 {
  margin: 0 0 8px;
  font-size: 28px;
  color: #fff;
  font-weight: 700;
}

.login-header p {
  margin: 0;
  font-size: 14px;
  color: #94a3b8;
}

.login-form {
  margin-bottom: 24px;
}

.form-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.login-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  border: none;
}

.login-btn:hover {
  background: linear-gradient(135deg, #1d4ed8, #1e40af);
}

.login-footer {
  text-align: center;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.login-footer p {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}

:deep(.el-input__wrapper) {
  background: rgba(0, 0, 0, 0.2);
  border-color: rgba(255, 255, 255, 0.1);
}

:deep(.el-input__wrapper:hover) {
  border-color: rgba(96, 165, 250, 0.5);
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.3);
  border-color: #2563eb;
}

:deep(.el-input__inner) {
  color: #fff;
}

:deep(.el-input__placeholder) {
  color: #64748b;
}

:deep(.el-checkbox__label) {
  color: #cbd5e1;
}

:deep(.el-link) {
  color: #60a5fa;
}

:deep(.el-dialog) {
  background: rgba(15, 23, 42, 0.95);
  border-color: rgba(255, 255, 255, 0.1);
}

:deep(.el-dialog__header) {
  border-bottom-color: rgba(255, 255, 255, 0.1);
}

:deep(.el-dialog__title) {
  color: #fff;
}

:deep(.el-form-item__label) {
  color: #cbd5e1;
}
</style>
