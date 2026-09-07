<template>
  <div class="roster">
    <strong>签到身份 · 项目固定名单</strong>
    <div class="fields">
      <label>{{ identity.class_label || '班级' }}
        <el-select v-model="group" filterable clearable placeholder="请选择班级" @change="clearSelection">
          <el-option v-for="value in groups" :key="value" :value="value" :label="value || '未分班'" />
        </el-select>
      </label>
      <label>{{ identity.name_label || '姓名' }}
        <el-select :model-value="selectedIndex" filterable clearable placeholder="请选择姓名" @change="select">
          <el-option v-for="item in students" :key="item.index" :value="item.index" :label="`${item.row.name}（${item.row.noLabel}）`" />
        </el-select>
      </label>
      <label>{{ identity.number_label || '学号' }}<el-input :model-value="selected?.noLabel || ''" readonly placeholder="选择姓名后自动填写" /></label>
    </div>
    <small>手动签到使用本次选择；自动任务保存所选身份。名单变更后需重新选择。</small>
    <el-alert v-if="!roster.length" title="当前固定名单为空，请同步项目后重试" type="warning" :closable="false" />
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
const props=defineProps({modelValue:{type:Object,default:()=>({})},identity:{type:Object,required:true}})
const emit=defineEmits(['update:modelValue'])
const group=ref('')
const roster=computed(()=>props.identity.roster||[])
const groups=computed(()=>[...new Set(roster.value.map(row=>row.groupName))])
const selected=computed(()=>props.modelValue.__identity)
const selectedIndex=computed(()=>{const index=roster.value.findIndex(row=>selected.value&&['no','noLabel','name','groupName'].every(key=>String(row[key])===String(selected.value[key])));return index<0?undefined:index})
const students=computed(()=>roster.value.map((row,index)=>({row,index})).filter(item=>item.row.groupName===group.value))
function clearSelection(){const value={...props.modelValue};delete value.__identity;emit('update:modelValue',value)}
function select(index){if(index===''||index==null){clearSelection();return}emit('update:modelValue',{...props.modelValue,__identity:{...roster.value[index]}})}
watch(()=>props.identity,()=>{group.value=selectedIndex.value===undefined?'':selected.value.groupName},{immediate:true})
watch(selected,()=>{if(selectedIndex.value!==undefined)group.value=selected.value.groupName})
</script>
<style scoped>
.roster{display:grid;gap:12px;padding:15px;margin-bottom:14px;border:1px solid #bfdbfe;border-radius:16px;background:white}.fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}label{display:grid;gap:6px;min-width:0;font-size:13px;color:#475569}.el-select{width:100%}small{color:#64748b}@media(max-width:700px){.fields{grid-template-columns:1fr}}
</style>
