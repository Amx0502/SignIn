<template>
  <el-result icon="info" title="暂无可用功能" sub-title="管理员当前未向你的账号开放任何业务菜单。">
    <template #extra>
      <el-button type="primary" :loading="loading" @click="retry">重新检查菜单</el-button>
    </template>
  </el-result>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { firstAllowedPath, refreshMenuCatalog } from '../menu/menuStore.js'

const router = useRouter()
const loading = ref(false)

async function retry() {
  loading.value = true
  try {
    await refreshMenuCatalog({ force: true })
    await router.replace(firstAllowedPath())
  } catch (error) {
    ElMessage.error(error.message || '菜单配置暂时无法同步')
  } finally {
    loading.value = false
  }
}
</script>
