<script setup>
import { ref } from 'vue'

const props = defineProps({
  loading: Boolean
})

const emit = defineEmits(['search'])

const domain = ref('')

const onSubmit = () => {
  if (domain.value) {
    // Basic cleanup for display
    let cleaned = domain.value.trim().toLowerCase()
    
    // Remove protocol
    if (cleaned.startsWith('http://')) cleaned = cleaned.slice(7)
    else if (cleaned.startsWith('https://')) cleaned = cleaned.slice(8)
    
    // Remove path/query
    const pathIdx = cleaned.indexOf('/')
    if (pathIdx !== -1) cleaned = cleaned.slice(0, pathIdx)
    
    // Update input value
    domain.value = cleaned
    
    emit('search', cleaned)
  }
}
</script>

<template>
  <div class="form-container">
    <div class="input-group">
      <input 
        v-model="domain" 
        @keyup.enter="onSubmit"
        type="text" 
        placeholder="输入域名，例如 example.com"
        :disabled="loading"
        autofocus
      />
      <button @click="onSubmit" :disabled="loading || !domain">
        <span v-if="loading">查询中...</span>
        <span v-else>查询监测</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.form-container {
  background: var(--surface-color);
  padding: 1.5rem;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  margin-bottom: 2rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.input-group {
  display: flex;
  gap: 1rem;
}

input {
  flex: 1;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  color: var(--text-main);
  font-size: 1rem;
  transition: all 0.2s;
}

input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

button {
  padding: 0 1.5rem;
  background: var(--primary-color);
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 1rem;
  transition: opacity 0.2s;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
