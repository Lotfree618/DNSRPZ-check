<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import DnsForm from './components/DnsForm.vue'
import ResultCard from './components/ResultCard.vue'
import HistoryList from './components/HistoryList.vue'

const currentResult = ref(null)
const loading = ref(false)
const error = ref(null)
const history = ref([])

const HISTORY_KEY = 'dnsrpz_history_v1'

onMounted(() => {
  loadHistory()
  // Clean URL if testing
})

const loadHistory = () => {
  try {
    const saved = localStorage.getItem(HISTORY_KEY)
    if (saved) {
      history.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('Failed to load history', e)
  }
}

const saveHistory = (item) => {
  // Add to top, dedupe
  const newHistory = [item, ...history.value.filter(h => h.domain !== item.domain)].slice(0, 30)
  history.value = newHistory
  localStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory))
}

const handleSearch = async (domain) => {
  if (!domain) return
  
  loading.value = true
  error.value = null
  currentResult.value = null
  
  try {
    // Determine API URL (assuming relative path proxy, or direct localhost for dev)
    // For dev, we might need full URL if not proxied yet. 
    // Assuming backend is at http://localhost:8000 for now or user configures proxy.
    // Let's use relative '/api/resolve' and assume we set up proxy in vite.config.js
    const response = await axios.get(`/api/resolve?domain=${encodeURIComponent(domain)}`)
    
    currentResult.value = response.data
    
    // Save brief history
    saveHistory({
      domain: response.data.domain,
      status: response.data.conclusion.status,
      ts: new Date().toISOString()
    })
    
  } catch (err) {
    console.error(err)
    error.value = err.response?.data?.detail || err.message || '查询失败'
  } finally {
    loading.value = false
  }
}

const handleHistoryClick = (domain) => {
  handleSearch(domain)
}
</script>

<template>
  <header>
    <h1>DNS RPZ 污染监测</h1>
    <p class="subtitle">检测域名是否受到 DNS 污染或 RPZ 拦截 (Taiwan ISP focus)</p>
  </header>

  <main>
    <div class="content-grid">
      <div class="left-panel">
        <DnsForm :loading="loading" @search="handleSearch" />
        
        <div v-if="error" class="error-msg">
          {{ error }}
        </div>

        <ResultCard v-if="currentResult" :result="currentResult" />
      </div>

      <div class="right-panel">
        <HistoryList :history="history" @select="handleHistoryClick" />
      </div>
    </div>
  </main>
</template>

<style scoped>
header {
  text-align: center;
  margin-bottom: 2rem;
}

h1 {
  background: linear-gradient(135deg, var(--primary-color), var(--success-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: var(--text-muted);
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 2rem;
  align-items: start;
}

@media (max-width: 768px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}

.error-msg {
  margin-top: 1rem;
  padding: 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--danger-color);
  color: var(--danger-color);
  border-radius: 8px;
}
</style>
