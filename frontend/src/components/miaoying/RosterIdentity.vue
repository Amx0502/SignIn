<template>
  <div class="roster">
    <header><div><strong>签到身份</strong><small>项目固定名单</small></div><el-tag size="small" :type="selected ? 'success' : 'warning'" effect="plain">{{ selected ? '已选择' : '待选择' }}</el-tag></header>
    <div class="fields">
      <label><span>{{ identity.class_label || '班级' }}</span>
        <el-select v-model="group" filterable clearable placeholder="请选择班级" @change="clearSelection">
          <el-option v-for="value in groups" :key="value" :value="value" :label="value || '未分班'" />
        </el-select>
      </label>
      <label><span>{{ identity.name_label || '姓名' }}</span>
        <el-select :model-value="selectedIndex" filterable clearable :disabled="!group" placeholder="请先选择班级" @change="select">
          <el-option v-for="item in students" :key="item.index" :value="item.index" :label="`${item.row.name}（${item.row.noLabel}）`" />
        </el-select>
      </label>
      <label><span>{{ identity.number_label || '学号' }}</span><el-input :model-value="selected?.noLabel || ''" readonly placeholder="选择姓名后自动填写" /></label>
    </div>
    <div v-if="selected" class="identity-summary"><span>当前身份</span><strong>{{ selected.groupName }} · {{ selected.name }} · {{ selected.noLabel }}</strong></div>
    <small class="roster-tip">手动签到使用本次选择；自动任务保存所选身份。名单变化后请重新选择。</small>
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
.roster{display:grid;gap:13px;padding:16px;margin-bottom:14px;border:1px solid #bfdbfe;border-radius:16px;background:#fff}.roster>header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-bottom:12px;border-bottom:1px solid #dbeafe}.roster>header strong,.roster>header small{display:block}.roster>header strong{color:#172033;font-size:16px}.roster>header small{margin-top:2px;color:#64748b;font-size:12px}.fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}label{display:grid;gap:7px;min-width:0}label>span{color:#475569;font-size:12px;font-weight:700}.el-select{width:100%}.identity-summary{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:9px 11px;border-radius:10px;background:#eff6ff;color:#1e40af;font-size:12px}.identity-summary strong{text-align:right;overflow-wrap:anywhere}.roster-tip{color:#64748b;font-size:12px;line-height:1.55}@media(max-width:700px){.fields{grid-template-columns:1fr}.identity-summary{align-items:flex-start;flex-direction:column;gap:4px}.identity-summary strong{text-align:left}}
</style>
