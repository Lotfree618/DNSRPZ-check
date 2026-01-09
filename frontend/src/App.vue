<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

// 状态
const domains = ref([])
const loading = ref(true)
const error = ref(null)
const selectedDomain = ref(null)
const detailData = ref(null)
const detailLoading = ref(false)
const lastUpdate = ref(null)

// API 基础地址
const API_BASE = import.meta.env.PROD ? '' : 'http://localhost:8000'

// 判斷是否為正常狀態（包括正常和空解析）
function isNormalStatus(status) {
  return status === '正常' || status === '空解析'
}

// 计算统计
const stats = computed(() => {
  const total = domains.value.length
  const normal = domains.value.filter(d => isNormalStatus(d.status)).length
  const abnormal = total - normal
  return { total, normal, abnormal }
})

// 取得狀態列表
async function fetchStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/status`)
    if (!res.ok) throw new Error('API 請求失敗')
    const data = await res.json()
    domains.value = data.domains
    lastUpdate.value = new Date().toLocaleTimeString('zh-TW')
    error.value = null
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// 取得網域詳情
async function fetchDetail(domain) {
  selectedDomain.value = domain
  detailLoading.value = true
  detailData.value = null
  
  try {
    const res = await fetch(`${API_BASE}/api/detail?domain=${encodeURIComponent(domain)}`)
    if (!res.ok) throw new Error('取得詳情失敗')
    detailData.value = await res.json()
  } catch (e) {
    console.error(e)
  } finally {
    detailLoading.value = false
  }
}

// 關閉彈窗
function closeModal() {
  selectedDomain.value = null
  detailData.value = null
}

// 格式化時間
function formatTime(isoStr) {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  return d.toLocaleTimeString('zh-TW')
}

// 取得分類樣式類
function getCategoryClass(category) {
  const map = {
    '正常': 'normal',
    '空解析': 'empty',
    '解析差異': 'diff',
    '被阻斷': 'blocked',
    '已封鎖': 'banned',
    '逾時': 'timeout',
    '錯誤': 'error'
  }
  return map[category] || 'error'
}

// 判斷 IP 是否符合基準
function isIpMatched(ip, baselineIps) {
  return baselineIps && baselineIps.includes(ip)
}

// 取得 IP 標籤樣式
function getIpClass(ip, baselineIps, category) {
  if (category === '正常' || category === '空解析') return 'match'
  if (category === '解析差異') {
    return isIpMatched(ip, baselineIps) ? 'match' : 'diff'
  }
  if (['被阻斷', '已封鎖', '逾時', '錯誤'].includes(category)) return 'error'
  return ''
}

// 取得 HTTP 狀態碼樣式
function getStatusClass(status) {
  if (!status || status === 0) return 'error'
  if (status >= 200 && status < 300) return 'success'
  if (status >= 300 && status < 400) return 'redirect'
  if (status >= 400) return 'error'
  return ''
}

// 定時更新
let timer = null

onMounted(() => {
  fetchStatus()
  timer = setInterval(fetchStatus, 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="app">
    <!-- 標題 -->
    <header class="header">
      <h1>🌐 網域台灣 DNS RPZ 檢測</h1>
      <p>即時檢測網域在台灣 DNS 解析器（中華電信、Twnic）的可用性</p>
    </header>

    <main class="container">
      <!-- 載入狀態 -->
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <p>正在載入資料...</p>
      </div>

      <!-- 主內容 -->
      <template v-else>
        <!-- 統計卡片 -->
        <div class="stats-row">
          <div class="stat-card">
            <div class="label">監控網域</div>
            <div class="value">{{ stats.total }}</div>
          </div>
          <div class="stat-card">
            <div class="label">正常</div>
            <div class="value normal">● {{ stats.normal }}</div>
          </div>
          <div class="stat-card">
            <div class="label">異常</div>
            <div class="value error">● {{ stats.abnormal }}</div>
          </div>
          <div class="stat-card">
            <div class="label">最後更新</div>
            <div class="value" style="font-size: 1.1rem;">{{ lastUpdate || '-' }}</div>
          </div>
        </div>

        <!-- 空狀態 -->
        <div v-if="domains.length === 0" class="empty-state">
          <p>尚無監控網域</p>
          <p style="font-size: 0.85rem; margin-top: 8px;">請在伺服器 Domains.txt 中新增網域</p>
        </div>

        <!-- 網域列表 -->
        <div v-else class="domain-list">
          <div
            v-for="item in domains"
            :key="item.domain"
            class="domain-card"
            @click="fetchDetail(item.domain)"
          >
            <div
              class="status-dot"
              :class="isNormalStatus(item.status) ? 'normal' : 'error'"
            ></div>
            <div class="domain-info">
              <div class="domain-name">{{ item.domain }}</div>
              <div class="domain-time">{{ formatTime(item.last_probe_at) }}</div>
            </div>
            <div
              class="status-badge"
              :class="isNormalStatus(item.status) ? 'normal' : 'error'"
            >
              {{ item.status }}
            </div>
          </div>
        </div>
      </template>
    </main>

    <!-- 詳情彈窗 -->
    <div v-if="selectedDomain" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h2>{{ selectedDomain }}</h2>
          <button class="modal-close" @click="closeModal">×</button>
        </div>

        <div class="modal-body">
          <!-- 載入中 -->
          <div v-if="detailLoading" class="loading">
            <div class="spinner"></div>
          </div>

          <!-- 詳情內容 -->
          <template v-else-if="detailData">
            <!-- 狀態 -->
            <div class="detail-section">
              <div class="section-title">檢測結果</div>
              <div
                class="status-display"
                :class="isNormalStatus(detailData.status) ? 'normal' : 'error'"
              >
                <span class="status-icon">{{ isNormalStatus(detailData.status) ? '✓' : '✗' }}</span>
                <span>{{ detailData.status }}</span>
              </div>
            </div>

            <!-- 異常原因 -->
            <div v-if="detailData.reasons.length > 0" class="detail-section">
              <div class="section-title">異常原因</div>
              <div class="reason-list">
                <span
                  v-for="reason in detailData.reasons"
                  :key="reason"
                  class="reason-tag"
                >
                  {{ reason }}
                </span>
              </div>
            </div>

            <!-- 基準 IP -->
            <div class="detail-section">
              <div class="section-title">基準 IP (Google / Cloudflare)</div>
              <div class="ip-box">
                <div v-if="detailData.baseline.ips.length === 0" class="ip-item empty">
                  無結果
                </div>
                <div
                  v-for="ip in detailData.baseline.ips"
                  :key="ip"
                  class="ip-item"
                >
                  {{ ip }}
                </div>
              </div>
            </div>

            <!-- 台灣解析器結果 -->
            <div class="detail-section">
              <div class="section-title">台灣 DNS 解析結果</div>
              <div
                v-for="r in detailData.tw"
                :key="r.resolver"
                class="resolver-card"
              >
                <div class="resolver-header">
                  <div class="resolver-info">
                    <div class="resolver-name">{{ r.name }}</div>
                    <div class="resolver-ip">{{ r.resolver }}</div>
                  </div>
                  <span
                    class="category-badge"
                    :class="getCategoryClass(r.category)"
                  >
                    {{ r.category }}
                  </span>
                </div>
                <div class="resolver-ips">
                  <span v-if="r.ips.length === 0" class="resolver-ip-tag error">
                    {{ r.msg || '無結果' }}
                  </span>
                  <span
                    v-for="ip in r.ips"
                    :key="ip"
                    class="resolver-ip-tag"
                    :class="getIpClass(ip, detailData.baseline.ips, r.category)"
                  >
                    {{ ip }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 網域跳轉追蹤 -->
            <div v-if="detailData.redirect_trace" class="detail-section">
              <div class="section-title">網域跳轉追蹤</div>
              <div class="redirect-trace-box">
                <!-- 錯誤狀態 -->
                <div v-if="detailData.redirect_trace.error" class="redirect-error">
                  <span class="error-icon">⚠</span>
                  {{ detailData.redirect_trace.error }}
                </div>
                
                <!-- 跳轉鏈 -->
                <div v-if="detailData.redirect_trace.chain.length > 0" class="redirect-chain">
                  <div
                    v-for="(step, idx) in detailData.redirect_trace.chain"
                    :key="idx"
                    class="redirect-step"
                  >
                    <span class="step-number">{{ idx + 1 }}</span>
                    <span 
                      class="step-status"
                      :class="getStatusClass(step.status)"
                    >
                      {{ step.status || '失敗' }}
                    </span>
                    <span class="step-url">{{ step.url }}</span>
                  </div>
                </div>

                <!-- 最終網域 -->
                <div v-if="detailData.redirect_trace.final_domain" class="final-domain">
                  <span class="final-label">最終網域:</span>
                  <span class="final-value">{{ detailData.redirect_trace.final_domain }}</span>
                  <span 
                    v-if="detailData.redirect_trace.success"
                    class="success-badge"
                  >✓ 可達</span>
                  <span v-else class="fail-badge">✗ 無法連線</span>
                </div>
                
                <!-- 無跳轉 -->
                <div v-if="detailData.redirect_trace.chain.length === 0 && !detailData.redirect_trace.error" class="no-redirect">
                  無法取得跳轉資訊
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
}
</style>
