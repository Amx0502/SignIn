<template>
  <div class="password-page">
    <el-card class="password-card" shadow="never">
      <template #header>
        <div>
          <h2>修改登录密码</h2>
          <p>修改当前登录账号的密码。</p>
        </div>
      </template>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="当前密码" prop="current_password">
          <el-input v-model="form.current_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="form.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input v-model="form.confirm_password" type="password" show-password @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit-btn" @click="submit">
          保存新密码
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { changePasswordApi } from '../api'

const router = useRouter()
const formRef = ref()
const loading = ref(false)
const form = reactive({ current_password: '', new_password: '', confirm_password: '' })
const currentUser = computed(() => {
  try { return JSON.parse(localStorage.getItem('user') || 'null') } catch { return null }
})
const rules = {
  current_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' }
  ],
  confirm_password: [{
    validator: (_rule, value, callback) => {
      if (!value) callback(new Error('请再次输入新密码'))
      else if (value !== form.new_password) callback(new Error('两次输入的密码不一致'))
      else callback()
    },
    trigger: 'blur'
  }]
}

async function submit() {
  await formRef.value.validate()
  loading.value = true
  try {
    const response = await changePasswordApi({
      current_password: form.current_password,
      new_password: form.new_password
    })
    localStorage.setItem('user', JSON.stringify(response.data))
    ElMessage.success('密码修改成功')
    router.replace('/overview')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.password-page { min-height: calc(100vh - 130px); display: grid; place-items: center; padding: 24px; }
.password-card { width: min(100%, 520px); border-radius: 18px; }
h2 { margin: 0 0 8px; color: #0f172a; }
p { margin: 0; color: #64748b; }
.submit-btn { width: 100%; height: 44px; }
</style>
