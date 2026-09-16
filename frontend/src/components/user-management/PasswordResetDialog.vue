<template>
  <el-dialog
    :model-value="modelValue"
    title="重置密码"
    width="420px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="新密码" prop="new_password">
        <el-input v-model="form.new_password" type="password" show-password />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="resetPassword">确认重置</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { resetUserPasswordApi } from '../../api'

const props = defineProps({
  modelValue: Boolean,
  user: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const saving = ref(false)
const formRef = ref()
const form = reactive({ new_password: '' })
const rules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) form.new_password = ''
  },
)

async function resetPassword() {
  await formRef.value.validate()
  if (!props.user?.id) return
  saving.value = true
  try {
    await resetUserPasswordApi(props.user.id, { new_password: form.new_password })
    ElMessage.success('密码已重置')
    emit('update:modelValue', false)
    emit('saved')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    saving.value = false
  }
}
</script>
