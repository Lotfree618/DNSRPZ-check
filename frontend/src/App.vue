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

// 判断是否为正常状态（包括正常和空解析）
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

// 获取状态列表
async function fetchStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/status`)
    if (!res.ok) throw new Error('API 请求失败')
    const data = await res.json()
    domains.value = data.domains
    lastUpdate.value = new Date().toLocaleTimeString('zh-CN')
    error.value = null
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// 获取域名详情
async function fetchDetail(domain) {
  selectedDomain.value = domain
  detailLoading.value = true
  detailData.value = null
  
  try {
    const res = await fetch(`${API_BASE}/api/detail?domain=${encodeURIComponent(domain)}`)
    if (!res.ok) throw new Error('获取详情失败')
    detailData.value = await res.json()
  } catch (e) {
    console.error(e)
  } finally {
    detailLoading.value = false
  }
}

// 关闭弹窗
function closeModal() {
  selectedDomain.value = null
  detailData.value = null
}

// 格式化时间
function formatTime(isoStr) {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  return d.toLocaleTimeString('zh-CN')
}

// 获取分类样式类
function getCategoryClass(category) {
  const map = {
    '正常': 'normal',
    '空解析': 'empty',
    '解析差异': 'diff',
    '被阻断': 'blocked',
    '已封锁': 'banned',
    '超时': 'timeout',
    '错误': 'error'
  }
  return map[category] || 'error'
}

// 判断 IP 是否匹配基准
function isIpMatched(ip, baselineIps) {
  return baselineIps && baselineIps.includes(ip)
}

// 获取 IP 标签样式
function getIpClass(ip, baselineIps, category) {
  if (category === '正常' || category === '空解析') return 'match'
  if (category === '解析差异') {
    return isIpMatched(ip, baselineIps) ? 'match' : 'diff'
  }
  if (['被阻断', '已封锁', '超时', '错误'].includes(category)) return 'error'
  return ''
}

// 定时刷新
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
    <!-- 头部 -->
    <header class="header">
      <h1>🌐 域名台湾DNS RPZ检测</h1>
      <p>实时检测域名在台湾DNS解析器（中华电信、Twnic）的可用性</p>
    </header>

    <main class="container">
      <!-- 加载状态 -->
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <p>正在加载数据...</p>
      </div>

      <!-- 主内容 -->
      <template v-else>
        <!-- 统计卡片 -->
        <div class="stats-row">
          <div class="stat-card">
            <div class="label">监控域名</div>
            <div class="value">{{ stats.total }}</div>
          </div>
          <div class="stat-card">
            <div class="label">正常</div>
            <div class="value normal">● {{ stats.normal }}</div>
          </div>
          <div class="stat-card">
            <div class="label">异常</div>
            <div class="value error">● {{ stats.abnormal }}</div>
          </div>
          <div class="stat-card">
            <div class="label">最后更新</div>
            <div class="value" style="font-size: 1.1rem;">{{ lastUpdate || '-' }}</div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="domains.length === 0" class="empty-state">
          <p>暂无监控域名</p>
          <p style="font-size: 0.85rem; margin-top: 8px;">请在服务器 Domains.txt 中添加域名</p>
        </div>

        <!-- 域名列表 -->
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

    <!-- 详情弹窗 -->
    <div v-if="selectedDomain" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h2>{{ selectedDomain }}</h2>
          <button class="modal-close" @click="closeModal">×</button>
        </div>

        <div class="modal-body">
          <!-- 加载中 -->
          <div v-if="detailLoading" class="loading">
            <div class="spinner"></div>
          </div>

          <!-- 详情内容 -->
          <template v-else-if="detailData">
            <!-- 状态 -->
            <div class="detail-section">
              <div class="section-title">检测结果</div>
              <div
                class="status-display"
                :class="isNormalStatus(detailData.status) ? 'normal' : 'error'"
              >
                <span class="status-icon">{{ isNormalStatus(detailData.status) ? '✓' : '✗' }}</span>
                <span>{{ detailData.status }}</span>
              </div>
            </div>

            <!-- 异常原因 -->
            <div v-if="detailData.reasons.length > 0" class="detail-section">
              <div class="section-title">异常原因</div>
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

            <!-- 基准 IP -->
            <div class="detail-section">
              <div class="section-title">基准 IP (Google / Cloudflare)</div>
              <div class="ip-box">
                <div v-if="detailData.baseline.ips.length === 0" class="ip-item empty">
                  无结果
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

            <!-- 台湾解析器结果 -->
            <div class="detail-section">
              <div class="section-title">台湾 DNS 解析结果</div>
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
                    {{ r.msg || '无结果' }}
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
