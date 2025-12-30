<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: Object
})

const conclusionClass = computed(() => {
  switch (props.result.conclusion.status) {
    case 'OK': return 'badge-success'
    case 'SUSPECTED_RPZ': return 'badge-danger'
    case 'DOMAIN_NOT_FOUND': return 'badge-danger'
    case 'POSSIBLE_INTERFERENCE': return 'badge-warning'
    default: return 'badge-neutral'
  }
})

const conclusionText = computed(() => {
  const map = {
    'OK': '正常 (OK)',
    'SUSPECTED_RPZ': '疑似污染/RPZ',
    'DOMAIN_NOT_FOUND': '域名不存在',
    'POSSIBLE_INTERFERENCE': '可能干扰',
    'UNCERTAIN': '不确定 (Uncertain)'
  }
  return map[props.result.conclusion.status] || props.result.conclusion.status
})

const resolversList = computed(() => {
  return [
    { key: 'google', name: 'Google (8.8.8.8)' },
    { key: 'cloudflare', name: 'Cloudflare (1.1.1.1)' },
    { key: 'hinet', name: '中华电信' },
    { key: 'twm', name: '台湾大哥大' },
    { key: 'fet', name: '远传电信' },
    { key: 'quad101', name: 'TWNIC (101)' },
  ]
})

const getStatusDisplay = (resolverResult) => {
  const status = resolverResult.A.status
  const answers = resolverResult.A.answers
  
  // Logic: NOERROR but no IPs -> Unknown
  if (status === 'NOERROR' && (!answers || answers.length === 0)) {
    return { text: '未知 (无结果)', class: 'text-warning' }
  }
  
  const map = {
    'NOERROR': { text: '正常', class: 'text-success' },
    'NXDOMAIN': { text: '不存在 (NX)', class: 'text-danger' },
    'TIMEOUT': { text: '超时', class: 'text-warning' },
    'SERVFAIL': { text: '失败 (ServFail)', class: 'text-danger' },
    'REFUSED': { text: '拒绝 (Refused)', class: 'text-danger' }
  }
  
  return map[status] || { text: status, class: 'text-muted' }
}
</script>

<template>
  <div class="result-card">
    <div class="result-header">
      <h2>监测结果: {{ result.domain }}</h2>
      <div class="badge" :class="conclusionClass">{{ conclusionText }}</div>
    </div>
    
    <div class="reasons" v-if="result.conclusion.reasons.length">
      <h3>判定依据:</h3>
      <ul>
        <li v-for="r in result.conclusion.reasons" :key="r">{{ r }}</li>
      </ul>
    </div>

    <h3>解析详情</h3>
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>解析来源</th>
            <th>状态</th>
            <th>A 记录 (IPv4)</th>
            <th>AAAA 记录 (IPv6)</th>
            <th>耗时</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="res in resolversList" :key="res.key">
            <td class="res-name">{{ res.name }}</td>
            <template v-if="result.resolvers[res.key]">
              <td>
                <span :class="getStatusDisplay(result.resolvers[res.key]).class">
                  {{ getStatusDisplay(result.resolvers[res.key]).text }}
                </span>
              </td>
              <td class="ip-cell">
                <div v-for="ip in result.resolvers[res.key].A.answers" :key="ip">{{ ip }}</div>
                <span v-if="!result.resolvers[res.key].A.answers.length" class="text-muted">-</span>
              </td>
              <td class="ip-cell">
                 <div v-for="ip in result.resolvers[res.key].AAAA.answers" :key="ip" class="text-small">{{ ip }}</div>
                 <span v-if="!result.resolvers[res.key].AAAA.answers.length" class="text-muted">-</span>
              </td>
              <td>{{ result.resolvers[res.key].elapsed_ms }}ms</td>
            </template>
            <template v-else>
              <td colspan="4" class="text-muted">无数据</td>
            </template>
          </tr>
        </tbody>
      </table>
    </div>
  
  </div>
</template>

<style scoped>
.result-card {
  background: var(--surface-color);
  padding: 2rem;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

h2 { margin: 0; font-size: 1.5rem; }
h3 { font-size: 1.1rem; margin-top: 1.5rem; color: var(--text-muted); }

.badge {
  padding: 0.5rem 1rem;
  border-radius: 99px;
  font-weight: bold;
  font-size: 0.9rem;
}
.badge-success { background: rgba(16, 185, 129, 0.2); color: var(--success-color); }
.badge-danger { background: rgba(239, 68, 68, 0.2); color: var(--danger-color); }
.badge-warning { background: rgba(245, 158, 11, 0.2); color: var(--warning-color); }
.badge-neutral { background: var(--border-color); color: var(--text-muted); }

.reasons ul { margin: 0.5rem 0; padding-left: 1.5rem; color: var(--text-main); }
.reasons li { margin-bottom: 0.25rem; }

.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

th, td {
  text-align: left;
  padding: 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

th { color: var(--text-muted); font-weight: 500; }
.res-name { font-weight: 600; color: var(--primary-color); }
.ip-cell { max-width: 200px; word-break: break-all; }
.text-small { font-size: 0.8rem; opacity: 0.8; }
.text-danger { color: var(--danger-color); }
.text-muted { color: var(--text-muted); }
</style>
