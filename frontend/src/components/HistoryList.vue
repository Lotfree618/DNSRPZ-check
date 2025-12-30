<script setup>
defineProps({
  history: Array
})

defineEmits(['select'])

const formatDate = (iso) => {
  return new Date(iso).toLocaleString('zh-TW', {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute:'2-digit'
  })
}

const getStatusInfo = (status) => {
  const map = {
    'OK': { text: '正常', class: 'status-success' },
    'SUSPECTED_RPZ': { text: '疑似污染', class: 'status-danger' },
    'DOMAIN_NOT_FOUND': { text: '不存在', class: 'status-danger' },
    'POSSIBLE_INTERFERENCE': { text: '可能干扰', class: 'status-warning' },
    'UNCERTAIN': { text: '不确定', class: 'status-muted' }
  }
  return map[status] || { text: status, class: 'status-muted' }
}
</script>

<template>
  <div class="history-container">
    <h3>查询历史</h3>
    <div v-if="history.length === 0" class="empty">暂无记录</div>
    <ul v-else class="history-list">
      <li v-for="(item, idx) in history" :key="idx" @click="$emit('select', item.domain)">
        <div class="h-header">
          <span class="h-domain">{{ item.domain }}</span>
          <span class="h-time">{{ formatDate(item.ts) }}</span>
        </div>
        <div class="h-status" :class="getStatusInfo(item.status).class">
          {{ getStatusInfo(item.status).text }}
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.history-container {
  background: var(--surface-color);
  padding: 1.5rem;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  max-height: 80vh;
  overflow-y: auto;
}

h3 { margin-top: 0; }

.empty { color: var(--text-muted); font-style: italic; }

.history-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

li {
  padding: 0.75rem;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  transition: background 0.2s;
}

li:hover {
  background: rgba(255, 255, 255, 0.05);
}

.h-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.25rem;
}

.h-domain { font-weight: 500; }
.h-time { font-size: 0.8rem; color: var(--text-muted); }

.h-status { 
  font-size: 0.75rem; 
  display: inline-block; 
  padding: 2px 8px; 
  border-radius: 99px; 
  font-weight: 600;
}

.status-success { background: rgba(16, 185, 129, 0.15); color: var(--success-color); }
.status-danger { background: rgba(239, 68, 68, 0.15); color: var(--danger-color); }
.status-warning { background: rgba(245, 158, 11, 0.15); color: var(--warning-color); }
.status-muted { background: var(--border-color); color: var(--text-muted); }
</style>
