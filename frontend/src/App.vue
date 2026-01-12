<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

// 狀態
const domains = ref([])
const loading = ref(true)
const error = ref(null)
const selectedDomain = ref(null)
const detailData = ref(null)
const detailLoading = ref(false)
const lastUpdate = ref(null)

// 篩選/搜尋/排序狀態
const searchQuery = ref('')
const reportedFilter = ref('all')  // all, reported, unreported
const pollutedFilter = ref('all')  // all, polluted, unpolluted, empty
const sortOrder = ref('az')  // az, date

// 下拉選單開啟狀態
const reportedDropdownOpen = ref(false)
const pollutedDropdownOpen = ref(false)
const sortDropdownOpen = ref(false)

// 多選模式
const multiSelectMode = ref(false)
const selectedItems = ref(new Set())

// 彈窗狀態
const showAddModal = ref(false)
const showConfirmModal = ref(false)
const showEditModal = ref(false)
const showNoteModal = ref(false)
const newDomain = ref('')
const editDomain = ref('')
const editNote = ref('')
const confirmAction = ref(null)
const confirmMessage = ref('')

// API 基礎地址
const API_BASE = import.meta.env.PROD ? '' : 'http://localhost:8000'

// 下拉選項配置
const reportedOptions = [
  { value: 'all', label: '全部上報狀態' },
  { value: 'reported', label: '已上報' },
  { value: 'unreported', label: '未上報' }
]

const pollutedOptions = [
  { value: 'all', label: '全部污染狀態' },
  { value: 'polluted', label: '已污染' },
  { value: 'unpolluted', label: '未污染' },
  { value: 'empty', label: '空解析' }
]

const sortOptions = [
  { value: 'az', label: 'A-Z 排序' },
  { value: 'date', label: '導入時間 新→舊' }
]

// 獲取當前選項標籤
function getOptionLabel(options, value) {
  const opt = options.find(o => o.value === value)
  return opt ? opt.label : ''
}

// 關閉所有下拉選單
function closeAllDropdowns() {
  reportedDropdownOpen.value = false
  pollutedDropdownOpen.value = false
  sortDropdownOpen.value = false
}

// 點擊外部關閉下拉選單
function handleClickOutside(event) {
  if (!event.target.closest('.custom-select')) {
    closeAllDropdowns()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

// 從 localStorage 讀取篩選狀態
onMounted(() => {
  const saved = localStorage.getItem('dnsrpz-filters')
  if (saved) {
    try {
      const data = JSON.parse(saved)
      reportedFilter.value = data.reportedFilter || 'all'
      pollutedFilter.value = data.pollutedFilter || 'all'
      sortOrder.value = data.sortOrder || 'az'
    } catch {}
  }
})

// 保存篩選狀態到 localStorage
watch([reportedFilter, pollutedFilter, sortOrder], () => {
  localStorage.setItem('dnsrpz-filters', JSON.stringify({
    reportedFilter: reportedFilter.value,
    pollutedFilter: pollutedFilter.value,
    sortOrder: sortOrder.value
  }))
})

// 判斷是否為正常狀態
function isNormalStatus(status) {
  return status === '正常' || status === '空解析'
}

// 判斷是否為空解析
function isEmptyResolution(item) {
  return item.status === '空解析' || (!item.polluted && item.status === '空解析')
}

// 計算統計
const stats = computed(() => {
  const total = domains.value.length
  const normal = domains.value.filter(d => !d.polluted && d.status !== '空解析').length
  const abnormal = domains.value.filter(d => d.polluted).length
  const empty = domains.value.filter(d => d.status === '空解析').length
  const reported = domains.value.filter(d => d.reported).length
  return { total, normal, abnormal, empty, reported }
})

// 過濾並排序後的網域列表
const filteredDomains = computed(() => {
  let result = [...domains.value]
  
  // 搜尋過濾
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(d => 
      d.domain.toLowerCase().includes(query) ||
      (d.note && d.note.toLowerCase().includes(query))
    )
  }
  
  // 已上報過濾
  if (reportedFilter.value === 'reported') {
    result = result.filter(d => d.reported)
  } else if (reportedFilter.value === 'unreported') {
    result = result.filter(d => !d.reported)
  }
  
  // 已污染過濾
  if (pollutedFilter.value === 'polluted') {
    result = result.filter(d => d.polluted)
  } else if (pollutedFilter.value === 'unpolluted') {
    result = result.filter(d => !d.polluted && d.status !== '空解析')
  } else if (pollutedFilter.value === 'empty') {
    result = result.filter(d => d.status === '空解析')
  }
  
  // 排序
  if (sortOrder.value === 'az') {
    result.sort((a, b) => a.domain.localeCompare(b.domain))
  } else if (sortOrder.value === 'date') {
    result.sort((a, b) => {
      const dateA = new Date(a.created_at || 0)
      const dateB = new Date(b.created_at || 0)
      return dateB - dateA
    })
  }
  
  return result
})

// 全選當前篩選結果
const allSelected = computed(() => {
  if (filteredDomains.value.length === 0) return false
  return filteredDomains.value.every(d => selectedItems.value.has(d.domain))
})

function toggleSelectAll() {
  if (allSelected.value) {
    filteredDomains.value.forEach(d => selectedItems.value.delete(d.domain))
  } else {
    filteredDomains.value.forEach(d => selectedItems.value.add(d.domain))
  }
  selectedItems.value = new Set(selectedItems.value)
}

function toggleSelect(domain) {
  if (selectedItems.value.has(domain)) {
    selectedItems.value.delete(domain)
  } else {
    selectedItems.value.add(domain)
  }
  selectedItems.value = new Set(selectedItems.value)
}

// 獲取網域列表
async function fetchDomains() {
  try {
    const res = await fetch(`${API_BASE}/api/domains`)
    if (!res.ok) throw new Error('API 請求失敗')
    const data = await res.json()
    
    // 同時獲取狀態資訊
    const statusRes = await fetch(`${API_BASE}/api/status`)
    if (statusRes.ok) {
      const statusData = await statusRes.json()
      const statusMap = {}
      statusData.domains.forEach(d => {
        statusMap[d.domain] = d.status
      })
      
      // 合併狀態
      data.domains.forEach(d => {
        d.status = statusMap[d.domain] || '待檢測'
      })
    }
    
    domains.value = data.domains
    lastUpdate.value = new Date().toLocaleTimeString('zh-TW')
    error.value = null
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// 獲取網域詳情
async function fetchDetail(domain) {
  if (multiSelectMode.value) {
    toggleSelect(domain)
    return
  }
  
  selectedDomain.value = domain
  detailLoading.value = true
  detailData.value = null
  
  const domainInfo = domains.value.find(d => d.domain === domain)
  
  try {
    const res = await fetch(`${API_BASE}/api/detail?domain=${encodeURIComponent(domain)}`)
    if (!res.ok) throw new Error('取得詳情失敗')
    const data = await res.json()
    detailData.value = { ...data, ...domainInfo }
  } catch (e) {
    detailData.value = domainInfo || { domain, status: '待檢測' }
  } finally {
    detailLoading.value = false
  }
}

// 關閉彈窗
function closeModal() {
  selectedDomain.value = null
  detailData.value = null
}

// 複製到剪貼板
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
}

// 開啟網域
function openDomain(domain) {
  window.open(`https://${domain}`, '_blank')
}

// 開啟 URL
function openUrl(url) {
  window.open(url, '_blank')
}

// 新增網域
async function addDomain() {
  if (!newDomain.value.trim()) return
  
  try {
    const res = await fetch(`${API_BASE}/api/domains`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain: newDomain.value.trim() })
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '新增失敗')
    
    showAddModal.value = false
    newDomain.value = ''
    await fetchDomains()
  } catch (e) {
    alert(e.message)
  }
}

// 修改網域
async function updateDomainName() {
  if (!editDomain.value.trim()) return
  
  try {
    const res = await fetch(`${API_BASE}/api/domains/${encodeURIComponent(selectedDomain.value)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_domain: editDomain.value.trim() })
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '修改失敗')
    
    showEditModal.value = false
    closeModal()
    await fetchDomains()
  } catch (e) {
    alert(e.message)
  }
}

// 更新備註
async function updateNote() {
  try {
    const res = await fetch(`${API_BASE}/api/domains/${encodeURIComponent(selectedDomain.value)}/note`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: editNote.value })
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '更新失敗')
    
    showNoteModal.value = false
    detailData.value.note = editNote.value
    await fetchDomains()
  } catch (e) {
    alert(e.message)
  }
}

// 切換已上報狀態
async function toggleReported() {
  try {
    const res = await fetch(`${API_BASE}/api/domains/${encodeURIComponent(selectedDomain.value)}/reported`, {
      method: 'PATCH'
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '操作失敗')
    
    detailData.value.reported = data.reported
    await fetchDomains()
  } catch (e) {
    alert(e.message)
  }
}

// 刪除單個網域
function confirmDeleteDomain() {
  confirmMessage.value = `確定要刪除網域「${selectedDomain.value}」嗎？`
  confirmAction.value = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/domains/${encodeURIComponent(selectedDomain.value)}`, {
        method: 'DELETE'
      })
      if (!res.ok) throw new Error('刪除失敗')
      
      showConfirmModal.value = false
      closeModal()
      await fetchDomains()
    } catch (e) {
      alert(e.message)
    }
  }
  showConfirmModal.value = true
}

// 批量刪除
function confirmBatchDelete() {
  const count = selectedItems.value.size
  if (count === 0) {
    alert('請先選擇要刪除的網域')
    return
  }
  
  confirmMessage.value = `確定要刪除選中的 ${count} 個網域嗎？`
  confirmAction.value = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/domains/batch-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domains: Array.from(selectedItems.value) })
      })
      if (!res.ok) throw new Error('刪除失敗')
      
      showConfirmModal.value = false
      selectedItems.value.clear()
      multiSelectMode.value = false
      await fetchDomains()
    } catch (e) {
      alert(e.message)
    }
  }
  showConfirmModal.value = true
}

// 開啟編輯彈窗
function openEditModal() {
  editDomain.value = selectedDomain.value
  showEditModal.value = true
}

// 開啟備註彈窗
function openNoteModal() {
  editNote.value = detailData.value?.note || ''
  showNoteModal.value = true
}

// 退出多選模式
function exitMultiSelect() {
  multiSelectMode.value = false
  selectedItems.value.clear()
}

// 格式化時間
function formatTime(isoStr) {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  return d.toLocaleTimeString('zh-TW')
}

// 格式化日期
function formatDate(isoStr) {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  return d.toLocaleDateString('zh-TW')
}

// 格式化日期時間
function formatDateTime(isoStr) {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  return d.toLocaleString('zh-TW')
}

// 截斷備註
function truncateNote(note, maxLen = 20) {
  if (!note) return ''
  return note.length > maxLen ? note.slice(0, maxLen) + '...' : note
}

// 獲取狀態類
function getStatusType(item) {
  if (!item.status || item.status === '待檢測') return 'pending'
  if (item.status === '空解析') return 'empty'
  if (item.polluted) return 'error'
  return 'normal'
}

// 獲取狀態文字
function getStatusText(item) {
  if (!item.status || item.status === '待檢測') return '待檢測'
  if (item.status === '空解析') return '空解析'
  if (item.polluted) return '異常'
  return '正常'
}

// 從 URL 提取網域
function extractDomainFromUrl(url) {
  try {
    const urlObj = new URL(url)
    return urlObj.hostname
  } catch {
    return null
  }
}

// 檢查網域是否在列表中
function isDomainInList(domain) {
  return domains.value.some(d => d.domain === domain)
}

// 獲取網域狀態信息
function getDomainStatusInfo(domain) {
  const found = domains.value.find(d => d.domain === domain)
  if (!found) return null
  return {
    status: found.status,
    polluted: found.polluted,
    type: getStatusType(found),
    text: getStatusText(found)
  }
}

// 快速添加網域
async function quickAddDomain(domain) {
  if (!domain || isDomainInList(domain)) return
  
  try {
    const res = await fetch(`${API_BASE}/api/domains`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain })
    })
    if (res.ok) {
      await fetchDomains()
    }
  } catch {}
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
  fetchDomains()
  timer = setInterval(fetchDomains, 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="app">
    <!-- 標題 -->
    <header class="header">
      <div class="header-content">
        <div class="logo">
          <svg class="logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="10"/>
            <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
          <div>
            <h1>DNS RPZ 檢測</h1>
            <p>台灣網域可用性即時監控</p>
          </div>
        </div>
      </div>
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
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">監控網域</div>
          </div>
          <div class="stat-card stat-normal">
            <div class="stat-value">{{ stats.normal }}</div>
            <div class="stat-label">正常</div>
          </div>
          <div class="stat-card stat-error">
            <div class="stat-value">{{ stats.abnormal }}</div>
            <div class="stat-label">異常</div>
          </div>
          <div class="stat-card stat-empty">
            <div class="stat-value">{{ stats.empty }}</div>
            <div class="stat-label">空解析</div>
          </div>
          <div class="stat-card stat-reported">
            <div class="stat-value">{{ stats.reported }}</div>
            <div class="stat-label">已上報</div>
          </div>
        </div>

        <!-- 工具列 -->
        <div class="toolbar">
          <div class="toolbar-left">
            <!-- 搜尋框 -->
            <div class="search-field">
              <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <path d="M21 21l-4.35-4.35"/>
              </svg>
              <input
                v-model="searchQuery"
                type="text"
                placeholder="搜尋網域..."
                class="search-input"
              />
            </div>
            
            <!-- 自定義下拉選單 - 上報狀態 -->
            <div class="custom-select" :class="{ open: reportedDropdownOpen }">
              <div class="select-trigger" @click.stop="reportedDropdownOpen = !reportedDropdownOpen; pollutedDropdownOpen = false; sortDropdownOpen = false">
                <span>{{ getOptionLabel(reportedOptions, reportedFilter) }}</span>
                <svg class="select-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M6 9l6 6 6-6"/>
                </svg>
              </div>
              <div class="select-dropdown">
                <div 
                  v-for="opt in reportedOptions" 
                  :key="opt.value" 
                  class="select-option"
                  :class="{ selected: reportedFilter === opt.value }"
                  @click="reportedFilter = opt.value; reportedDropdownOpen = false"
                >
                  {{ opt.label }}
                </div>
              </div>
            </div>
            
            <!-- 自定義下拉選單 - 污染狀態 -->
            <div class="custom-select" :class="{ open: pollutedDropdownOpen }">
              <div class="select-trigger" @click.stop="pollutedDropdownOpen = !pollutedDropdownOpen; reportedDropdownOpen = false; sortDropdownOpen = false">
                <span>{{ getOptionLabel(pollutedOptions, pollutedFilter) }}</span>
                <svg class="select-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M6 9l6 6 6-6"/>
                </svg>
              </div>
              <div class="select-dropdown">
                <div 
                  v-for="opt in pollutedOptions" 
                  :key="opt.value" 
                  class="select-option"
                  :class="{ selected: pollutedFilter === opt.value }"
                  @click="pollutedFilter = opt.value; pollutedDropdownOpen = false"
                >
                  {{ opt.label }}
                </div>
              </div>
            </div>
            
            <!-- 自定義下拉選單 - 排序 -->
            <div class="custom-select" :class="{ open: sortDropdownOpen }">
              <div class="select-trigger" @click.stop="sortDropdownOpen = !sortDropdownOpen; reportedDropdownOpen = false; pollutedDropdownOpen = false">
                <span>{{ getOptionLabel(sortOptions, sortOrder) }}</span>
                <svg class="select-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M6 9l6 6 6-6"/>
                </svg>
              </div>
              <div class="select-dropdown">
                <div 
                  v-for="opt in sortOptions" 
                  :key="opt.value" 
                  class="select-option"
                  :class="{ selected: sortOrder === opt.value }"
                  @click="sortOrder = opt.value; sortDropdownOpen = false"
                >
                  {{ opt.label }}
                </div>
              </div>
            </div>
          </div>
          
          <div class="toolbar-right">
            <template v-if="multiSelectMode">
              <button class="btn btn-outlined" @click="toggleSelectAll">
                {{ allSelected ? '取消全選' : '全選' }}
              </button>
              <button class="btn btn-error" @click="confirmBatchDelete">
                刪除 ({{ selectedItems.size }})
              </button>
              <button class="btn btn-text" @click="exitMultiSelect">
                取消
              </button>
            </template>
            <template v-else>
              <button class="btn btn-outlined" @click="multiSelectMode = true">
                多選
              </button>
              <button class="btn btn-filled" @click="showAddModal = true">
                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 5v14M5 12h14"/>
                </svg>
                新增網域
              </button>
            </template>
          </div>
        </div>

        <!-- 顯示結果數量 -->
        <div class="result-info">
          <span class="result-count">顯示 {{ filteredDomains.length }} / {{ domains.length }} 個網域</span>
          <span v-if="lastUpdate" class="last-update">最後更新: {{ lastUpdate }}</span>
        </div>

        <!-- 空狀態 -->
        <div v-if="domains.length === 0" class="empty-state">
          <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="10"/>
            <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
          <p class="empty-title">尚無監控網域</p>
          <p class="empty-desc">點擊「新增網域」按鈕開始</p>
        </div>

        <!-- 網域列表 -->
        <div v-else class="domain-list">
          <div
            v-for="item in filteredDomains"
            :key="item.domain"
            class="domain-card"
            :class="{ selected: selectedItems.has(item.domain) }"
            @click="fetchDetail(item.domain)"
          >
            <!-- 多選框 -->
            <div v-if="multiSelectMode" class="checkbox" :class="{ checked: selectedItems.has(item.domain) }">
              <svg v-if="selectedItems.has(item.domain)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                <path d="M20 6L9 17l-5-5"/>
              </svg>
            </div>
            
            <div class="status-indicator" :class="getStatusType(item)"></div>
            <div class="domain-content">
              <div class="domain-name">{{ item.domain }}</div>
              <div class="domain-meta">
                <span v-if="item.note" class="domain-note">{{ truncateNote(item.note) }}</span>
                <span v-if="item.reported" class="tag tag-reported">已上報</span>
              </div>
            </div>
            <div class="status-chip" :class="getStatusType(item)">
              {{ getStatusText(item) }}
            </div>
          </div>
        </div>
      </template>
    </main>

    <!-- 新增網域彈窗 -->
    <div v-if="showAddModal" class="modal-overlay modal-z1" @click.self="showAddModal = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h2>新增網域</h2>
          <button class="icon-btn" @click="showAddModal = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="text-field">
            <input
              v-model="newDomain"
              type="text"
              placeholder=" "
              class="text-input"
              @keyup.enter="addDomain"
            />
            <label class="text-label">網域或 URL</label>
          </div>
          <p class="helper-text">例如：example.com 或 https://example.com/path</p>
        </div>
        <div class="modal-actions">
          <button class="btn btn-text" @click="showAddModal = false">取消</button>
          <button class="btn btn-filled" @click="addDomain">新增</button>
        </div>
      </div>
    </div>

    <!-- 確認彈窗 -->
    <div v-if="showConfirmModal" class="modal-overlay modal-z2" @click.self="showConfirmModal = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h2>確認刪除</h2>
          <button class="icon-btn" @click="showConfirmModal = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <p class="confirm-text">{{ confirmMessage }}</p>
        </div>
        <div class="modal-actions">
          <button class="btn btn-text" @click="showConfirmModal = false">取消</button>
          <button class="btn btn-error" @click="confirmAction">確認刪除</button>
        </div>
      </div>
    </div>

    <!-- 修改網域彈窗 -->
    <div v-if="showEditModal" class="modal-overlay modal-z2" @click.self="showEditModal = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h2>修改網域</h2>
          <button class="icon-btn" @click="showEditModal = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="text-field">
            <input
              v-model="editDomain"
              type="text"
              placeholder=" "
              class="text-input"
              @keyup.enter="updateDomainName"
            />
            <label class="text-label">新網域</label>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-text" @click="showEditModal = false">取消</button>
          <button class="btn btn-filled" @click="updateDomainName">儲存</button>
        </div>
      </div>
    </div>

    <!-- 編輯備註彈窗 -->
    <div v-if="showNoteModal" class="modal-overlay modal-z2" @click.self="showNoteModal = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h2>編輯備註</h2>
          <button class="icon-btn" @click="showNoteModal = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="text-field">
            <textarea
              v-model="editNote"
              placeholder=" "
              class="text-input textarea"
              rows="3"
            ></textarea>
            <label class="text-label">備註內容</label>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-text" @click="showNoteModal = false">取消</button>
          <button class="btn btn-filled" @click="updateNote">儲存</button>
        </div>
      </div>
    </div>

    <!-- 詳情彈窗 -->
    <div v-if="selectedDomain && !multiSelectMode" class="modal-overlay modal-z1" @click.self="closeModal">
      <div class="modal modal-lg">
        <div class="modal-header">
          <h2 class="domain-title">{{ selectedDomain }}</h2>
          <div class="header-actions">
            <button class="icon-btn" @click="copyToClipboard(selectedDomain)" title="複製">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2"/>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
            </button>
            <button class="icon-btn" @click="openDomain(selectedDomain)" title="開啟">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                <polyline points="15,3 21,3 21,9"/>
                <line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
            </button>
            <button class="icon-btn" @click="closeModal">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>

        <div class="modal-body">
          <div v-if="detailLoading" class="loading">
            <div class="spinner"></div>
          </div>

          <template v-else-if="detailData">
            <!-- 狀態顯示 -->
            <div class="section">
              <div class="status-display" :class="getStatusType(detailData)">
                <svg v-if="isNormalStatus(detailData.status)" class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <path d="M20 6L9 17l-5-5"/>
                </svg>
                <svg v-else class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
                <span>{{ detailData.status || '待檢測' }}</span>
              </div>
            </div>

            <!-- 操作按鈕 -->
            <div class="section">
              <div class="section-title">操作</div>
              <div class="action-row">
                <button class="btn btn-outlined btn-sm" @click="openEditModal">
                  <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                  修改
                </button>
                <button class="btn btn-outlined btn-sm" @click="openNoteModal">
                  <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14,2 14,8 20,8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                  </svg>
                  備註
                </button>
                <button class="btn btn-sm" :class="detailData.reported ? 'btn-tonal-warning' : 'btn-tonal'" @click="toggleReported">
                  <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/>
                    <line x1="4" y1="22" x2="4" y2="15"/>
                  </svg>
                  {{ detailData.reported ? '取消上報' : '已上報' }}
                </button>
                <button class="btn btn-error btn-sm" @click="confirmDeleteDomain">
                  <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3,6 5,6 21,6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                  刪除
                </button>
              </div>
            </div>

            <!-- 網域資訊 -->
            <div class="section">
              <div class="section-title">網域資訊</div>
              <div class="info-row">
                <div class="info-item">
                  <span class="info-label">導入時間</span>
                  <span class="info-value">{{ formatDate(detailData.created_at) }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">檢測時間</span>
                  <span class="info-value">{{ detailData.last_probe_at ? formatDateTime(detailData.last_probe_at) : '尚未檢測' }}</span>
                </div>
                <div class="info-item info-full">
                  <span class="info-label">備註</span>
                  <span class="info-value">{{ detailData.note || '無' }}</span>
                </div>
              </div>
            </div>

            <!-- 異常原因 -->
            <div v-if="detailData.reasons && detailData.reasons.length > 0" class="section">
              <div class="section-title">異常原因</div>
              <div class="chip-row">
                <span v-for="reason in detailData.reasons" :key="reason" class="chip chip-error">
                  {{ reason }}
                </span>
              </div>
            </div>

            <!-- 基準 IP -->
            <div v-if="detailData.baseline" class="section">
              <div class="section-title">基準 IP (Google / Cloudflare)</div>
              <div class="code-box">
                <div v-if="detailData.baseline.ips.length === 0" class="code-empty">無結果</div>
                <div v-for="ip in detailData.baseline.ips" :key="ip" class="code-item">{{ ip }}</div>
              </div>
            </div>

            <!-- 台灣解析器結果 -->
            <div v-if="detailData.tw" class="section">
              <div class="section-title">台灣 DNS 解析結果</div>
              <div v-for="r in detailData.tw" :key="r.resolver" class="resolver-card">
                <div class="resolver-header">
                  <div>
                    <div class="resolver-name">{{ r.name }}</div>
                    <div class="resolver-ip">{{ r.resolver }}</div>
                  </div>
                  <span class="chip" :class="'chip-' + getCategoryClass(r.category)">{{ r.category }}</span>
                </div>
                <div class="resolver-ips">
                  <span v-if="r.ips.length === 0" class="ip-tag ip-error">{{ r.msg || '無結果' }}</span>
                  <span v-for="ip in r.ips" :key="ip" class="ip-tag" :class="'ip-' + getIpClass(ip, detailData.baseline?.ips, r.category)">
                    {{ ip }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 網域跳轉追蹤 -->
            <div v-if="detailData.redirect_trace" class="section">
              <div class="section-title">網域跳轉追蹤</div>
              <div class="trace-box">
                <div v-if="detailData.redirect_trace.error" class="trace-error">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                  </svg>
                  {{ detailData.redirect_trace.error }}
                </div>
                
                <div v-if="detailData.redirect_trace.chain.length > 0" class="trace-chain">
                  <div v-for="(step, idx) in detailData.redirect_trace.chain" :key="idx" class="trace-step">
                    <span class="step-num">{{ idx + 1 }}</span>
                    <span class="step-code" :class="'code-' + getStatusClass(step.status)">{{ step.status || '失敗' }}</span>
                    <div class="step-domain-info">
                      <span class="step-url">{{ step.url }}</span>
                      <div v-if="extractDomainFromUrl(step.url)" class="step-domain-status">
                        <template v-if="getDomainStatusInfo(extractDomainFromUrl(step.url))">
                          <span class="domain-chip" :class="'chip-' + getDomainStatusInfo(extractDomainFromUrl(step.url)).type">
                            {{ getDomainStatusInfo(extractDomainFromUrl(step.url)).text }}
                          </span>
                        </template>
                        <template v-else>
                          <button class="add-domain-btn" @click.stop="quickAddDomain(extractDomainFromUrl(step.url))" title="加入監控">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <path d="M12 5v14M5 12h14"/>
                            </svg>
                          </button>
                        </template>
                      </div>
                    </div>
                    <div class="step-actions">
                      <button class="icon-btn-sm" @click.stop="copyToClipboard(step.url)" title="複製">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <rect x="9" y="9" width="13" height="13" rx="2"/>
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                        </svg>
                      </button>
                      <button class="icon-btn-sm" @click.stop="openUrl(step.url)" title="開啟">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                          <polyline points="15,3 21,3 21,9"/>
                          <line x1="10" y1="14" x2="21" y2="3"/>
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>

                <div v-if="detailData.redirect_trace.final_domain" class="trace-final">
                  <span class="final-label">最終網域:</span>
                  <span class="final-domain">{{ detailData.redirect_trace.final_domain }}</span>
                  <span v-if="detailData.redirect_trace.success" class="chip chip-normal">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>
                    可達
                  </span>
                  <span v-else class="chip chip-error">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                    無法連線
                  </span>
                </div>
                
                <div v-if="detailData.redirect_trace.chain.length === 0 && !detailData.redirect_trace.error" class="trace-empty">
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
