<script setup>
import { ref, computed } from 'vue'

// 定義 toast 列表
const toasts = ref([])
let toastId = 0

// Toast 類型配置
const typeConfig = {
  success: {
    icon: 'M20 6L9 17l-5-5',
    class: 'toast-success'
  },
  error: {
    icon: 'M18 6L6 18M6 6l12 12',
    class: 'toast-error'
  },
  warning: {
    icon: 'M12 2L2 22h20L12 2zM12 9v6M12 17h.01',
    class: 'toast-warning'
  },
  info: {
    icon: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 9v4M12 17h.01',
    class: 'toast-info'
  }
}

// 添加 toast
function show(message, type = 'info', duration = 3000) {
  const id = ++toastId
  const toast = {
    id,
    message,
    type,
    config: typeConfig[type] || typeConfig.info,
    visible: true
  }
  
  toasts.value.push(toast)
  
  // 自動移除
  if (duration > 0) {
    setTimeout(() => {
      remove(id)
    }, duration)
  }
  
  return id
}

// 移除 toast
function remove(id) {
  const index = toasts.value.findIndex(t => t.id === id)
  if (index > -1) {
    toasts.value[index].visible = false
    setTimeout(() => {
      toasts.value.splice(index, 1)
    }, 300) // 等待動畫完成
  }
}

// 快捷方法
const success = (message, duration) => show(message, 'success', duration)
const error = (message, duration) => show(message, 'error', duration)
const warning = (message, duration) => show(message, 'warning', duration)
const info = (message, duration) => show(message, 'info', duration)

// 暴露方法供外部調用
defineExpose({
  show,
  success,
  error,
  warning,
  info,
  remove
})
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast"
          :class="[toast.config.class, { leaving: !toast.visible }]"
          @click="remove(toast.id)"
        >
          <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path :d="toast.config.icon"/>
          </svg>
          <span class="toast-message">{{ toast.message }}</span>
          <button class="toast-close" @click.stop="remove(toast.id)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: calc(100vw - 40px);
  pointer-events: none;
}

/* 移動端居中顯示 */
@media (max-width: 480px) {
  .toast-container {
    top: auto;
    bottom: 20px;
    right: 50%;
    transform: translateX(50%);
    width: calc(100vw - 32px);
    max-width: 400px;
  }
}

.toast {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--md-surface, #fff);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05);
  cursor: pointer;
  pointer-events: auto;
  min-width: 280px;
  max-width: 440px;
  backdrop-filter: blur(10px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.toast:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2), 0 0 0 1px rgba(0, 0, 0, 0.08);
}

.toast-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

.toast-message {
  flex: 1;
  font-size: 0.9375rem;
  font-weight: 500;
  line-height: 1.4;
  color: var(--md-on-surface, #1f1f1f);
}

.toast-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--md-on-surface-muted, #888);
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.toast-close svg {
  width: 16px;
  height: 16px;
}

.toast-close:hover {
  background: rgba(0, 0, 0, 0.08);
}

/* Toast 類型樣式 */
.toast-success {
  background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
  border-left: 4px solid #16a34a;
}

.toast-success .toast-icon {
  color: #16a34a;
}

.toast-error {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  border-left: 4px solid #dc2626;
}

.toast-error .toast-icon {
  color: #dc2626;
}

.toast-warning {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border-left: 4px solid #d97706;
}

.toast-warning .toast-icon {
  color: #d97706;
}

.toast-info {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  border-left: 4px solid #2563eb;
}

.toast-info .toast-icon {
  color: #2563eb;
}

/* 動畫 */
.toast-enter-active {
  animation: toast-in 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.toast-leave-active {
  animation: toast-out 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes toast-in {
  0% {
    opacity: 0;
    transform: translateX(100%) scale(0.8);
  }
  100% {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}

@keyframes toast-out {
  0% {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateX(100%) scale(0.8);
  }
}

/* 移動端動畫調整 */
@media (max-width: 480px) {
  @keyframes toast-in {
    0% {
      opacity: 0;
      transform: translateY(100%) scale(0.8);
    }
    100% {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  @keyframes toast-out {
    0% {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
    100% {
      opacity: 0;
      transform: translateY(100%) scale(0.8);
    }
  }

  .toast {
    min-width: auto;
    width: 100%;
    max-width: none;
  }
}
</style>
