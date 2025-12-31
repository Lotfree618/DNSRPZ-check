<script setup>
import { ref, computed, onMounted } from 'vue'

const query = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)
const history = ref([])
const expandedIps = ref({}) // 记录哪些IP列表已展开

const HISTORY_KEY = 'dnsrpz_history_v1'
const MAX_HISTORY = 10
const API_BASE = '/api'

function extractDomain(input) {
  input = input.trim()
  if (!input) return ''
  if (input.includes('://') || input.includes('/') || input.includes('?') || input.includes('#')) {
    try {
      if (!input.startsWith('http://') && !input.startsWith('https://')) input = 'http://' + input
      return new URL(input).hostname.toLowerCase()
    } catch { return input.toLowerCase() }
  }
  return input.toLowerCase().replace(/\.$/, '')
}

function handleBlur() {
  const domain = extractDomain(query.value)
  if (domain) query.value = domain
}

function loadHistory() {
  try {
    const data = localStorage.getItem(HISTORY_KEY)
    if (data) history.value = JSON.parse(data)
  } catch { history.value = [] }
}

function saveHistory(domain, status) {
  history.value = history.value.filter(item => item.domain !== domain)
  history.value.unshift({ domain, status, ts: Date.now() })
  if (history.value.length > MAX_HISTORY) history.value = history.value.slice(0, MAX_HISTORY)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
}

function clearHistory() {
  history.value = []
  localStorage.removeItem(HISTORY_KEY)
}

function formatTime(ts) {
  return new Date(ts).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function doQuery() {
  const domain = extractDomain(query.value)
  if (!domain) { error.value = '请输入有效的域名或URL'; return }
  query.value = domain
  loading.value = true
  error.value = ''
  result.value = null
  expandedIps.value = {}
  try {
    const res = await fetch(`${API_BASE}/resolve?target=${encodeURIComponent(domain)}`)
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '请求失败')
    result.value = data
    saveHistory(data.domain, data.conclusion.status)
  } catch (e) {
    error.value = e.message || '网络错误，请稍后重试'
  } finally { loading.value = false }
}

function queryFromHistory(domain) {
  query.value = domain
  doQuery()
}

function toggleIps(key) {
  expandedIps.value[key] = !expandedIps.value[key]
}

function formatIps(ips, key) {
  if (!ips || ips.length === 0) return '—'
  if (ips.length <= 2 || expandedIps.value[key]) return ips.join(', ')
  return ips.slice(0, 2).join(', ') + ` (+${ips.length - 2})`
}

const conclusionClass = computed(() => {
  if (!result.value) return ''
  const status = result.value.conclusion.status
  if (status === 'OK') return 'ok'
  if (status === '异常') return 'abnormal'
  return 'uncertain'
})

onMounted(() => { loadHistory() })
</script>

<template>
  <div class="app-container">
    <header class="header">
      <h1>🔍 台湾DNS RPZ检测</h1>
      <p>检测域名是否被台湾ISP的DNS封锁</p>
    </header>

    <section class="search-section">
      <form class="search-form" @submit.prevent="doQuery">
        <input v-model="query" type="text" class="search-input" placeholder="输入域名或URL" @blur="handleBlur" :disabled="loading" />
        <button type="submit" class="search-btn" :disabled="loading">{{ loading ? '检测中...' : '检测' }}</button>
      </form>
    </section>

    <div v-if="error" class="error-msg">❌ {{ error }}</div>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>正在查询...</span>
    </div>

    <div v-if="result && !loading" class="results">
      <!-- 结论 -->
      <div class="conclusion-card" :class="conclusionClass">
        <div class="conclusion-main">
          <span class="conclusion-icon">{{ conclusionClass === 'ok' ? '✅' : conclusionClass === 'abnormal' ? '🚫' : '⚠️' }}</span>
          <span class="conclusion-text">{{ result.conclusion.status }}</span>
          <span class="conclusion-domain">{{ result.domain }}</span>
        </div>
        <div class="conclusion-reason">{{ result.conclusion.reason[0] }}</div>
      </div>

      <!-- DNS结果表格 - 横向布局 -->
      <div class="dns-grid">
        <div class="dns-section">
          <div class="section-title">📡 基准DNS</div>
          <div class="dns-items">
            <div v-for="r in result.baseline.detail" :key="r.ip" class="dns-item">
              <div class="dns-name">{{ r.name.replace(' DNS', '') }}</div>
              <div class="dns-ips" :class="{ clickable: r.ips.length > 2 }" @click="r.ips.length > 2 && toggleIps('b-' + r.ip)">
                {{ formatIps(r.ips, 'b-' + r.ip) }}
              </div>
              <span class="status-dot ok"></span>
            </div>
          </div>
        </div>
        <div class="dns-section">
          <div class="section-title">📡 台湾DNS</div>
          <div class="dns-items">
            <div v-for="r in result.tw_resolvers" :key="r.ip" class="dns-item">
              <div class="dns-name">{{ r.name.replace('（中华电信）', '') }}</div>
              <div class="dns-ips" :class="{ clickable: r.ips.length > 2 }" @click="r.ips.length > 2 && toggleIps('tw-' + r.ip)">
                {{ formatIps(r.ips, 'tw-' + r.ip) }}
              </div>
              <span class="status-dot" :class="{ ok: r.classification === '正常', error: r.classification === '已封锁' || r.classification === '被阻断', warn: r.classification === '超时' || r.classification.includes('CDN') }"></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 历史记录 -->
    <section v-if="history.length > 0" class="history-section">
      <div class="history-header">
        <span>📜 历史</span>
        <button class="clear-btn" @click="clearHistory">清空</button>
      </div>
      <div class="history-list">
        <div v-for="item in history.slice(0, 5)" :key="item.ts" class="history-item" @click="queryFromHistory(item.domain)">
          <span class="h-domain">{{ item.domain }}</span>
          <span class="h-status" :class="{ ok: item.status === 'OK', error: item.status === '异常', warn: item.status === '不确定' }">{{ item.status }}</span>
        </div>
      </div>
    </section>
  </div>
</template>
