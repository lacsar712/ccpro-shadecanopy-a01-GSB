<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const list = ref([])
const zones = ref([])
const error = ref('')
const conflict = ref(null)
const success = ref('')
const filterZoneId = ref('')
const filterDirection = ref('')

function localInputValue(d = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const form = reactive({
  zoneId: '',
  direction: 'open',
  extent: 80,
  operatedAt: localInputValue(),
  operatorName: '',
  notes: '',
})

const directionLabel = { open: '拉开', close: '收拢' }
const statusLabel = { idle: '空闲', growing: '在种', fallow: '休耕' }

const selectedZone = computed(
  () => zones.value.find((z) => z.id === Number(form.zoneId)) || null
)
const needNotes = computed(() => selectedZone.value?.status === 'fallow')
const zoneBlocked = computed(() => selectedZone.value?.status === 'idle')

function resetForm() {
  form.zoneId = zones.value[0]?.id || ''
  form.direction = 'open'
  form.extent = 80
  form.operatedAt = localInputValue()
  form.operatorName = ''
  form.notes = ''
}

async function loadZones() {
  const { data } = await api.get('/zones/')
  zones.value = data.results || data
  if (!form.zoneId && zones.value.length) form.zoneId = zones.value[0].id
}

async function load() {
  error.value = ''
  try {
    const params = {}
    if (filterZoneId.value) params.zoneId = filterZoneId.value
    if (filterDirection.value) params.direction = filterDirection.value
    const { data } = await api.get('/shade-travels/', { params })
    list.value = data.results || data
  } catch {
    error.value = '加载遮阳行程失败'
  }
}

async function save() {
  error.value = ''
  conflict.value = null
  success.value = ''
  if (!form.zoneId) {
    error.value = '请选择分区'
    return
  }
  if (zoneBlocked.value) {
    error.value = '空闲分区禁止登记遮阳行程'
    return
  }
  if (form.extent < 1 || form.extent > 100) {
    error.value = '幅度须为 1～100 的整数'
    return
  }
  if (needNotes.value && !form.notes.trim()) {
    error.value = '休耕分区登记行程必须填写备注'
    return
  }
  if (!form.operatorName.trim()) {
    error.value = '请填写操作人姓名'
    return
  }
  const payload = {
    zoneId: Number(form.zoneId),
    direction: form.direction,
    extent: form.extent,
    operatedAt: new Date(form.operatedAt).toISOString(),
    operatorName: form.operatorName,
    notes: form.notes,
  }
  try {
    await api.post('/shade-travels/', payload)
    success.value =
      form.direction === 'open' && form.extent > 60
        ? '行程已登记，并已同事务联动写入一条气候记录（PAR 120）'
        : '行程已登记'
    resetForm()
    await load()
  } catch (e) {
    const data = e.response?.data
    if (e.response?.status === 409 && data?.conflictTravelId) {
      conflict.value = data.conflictTravelId
    } else {
      error.value = JSON.stringify(data || '保存失败')
    }
  }
}

async function remove(id) {
  if (!confirm('确认删除该遮阳行程？（联动气候记录不会自动删除）')) return
  await api.delete(`/shade-travels/${id}/`)
  await load()
}

onMounted(async () => {
  await loadZones()
  await load()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>遮阳行程</h1>
        <p>同分区操作时刻前后 15 分钟互斥；拉开且幅度 &gt; 60 时同事务联动一条气候记录</p>
      </div>
      <div class="actions">
        <select v-model="filterZoneId" @change="load">
          <option value="">全部分区</option>
          <option v-for="z in zones" :key="z.id" :value="z.id">
            {{ z.greenhouseName }} / {{ z.zoneCode }}
          </option>
        </select>
        <select v-model="filterDirection" @change="load">
          <option value="">全部方向</option>
          <option value="open">拉开</option>
          <option value="close">收拢</option>
        </select>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">登记行程</h3>
      <div class="form-grid">
        <label>
          分区
          <select v-model="form.zoneId">
            <option v-for="z in zones" :key="z.id" :value="z.id">
              {{ z.greenhouseName }} / {{ z.zoneCode }}（{{ statusLabel[z.status] || z.status }}）
            </option>
          </select>
        </label>
        <label>
          方向
          <select v-model="form.direction">
            <option value="open">拉开</option>
            <option value="close">收拢</option>
          </select>
        </label>
        <label>幅度（1～100）
          <input v-model.number="form.extent" type="number" min="1" max="100" step="1" />
        </label>
        <label>操作时刻<input v-model="form.operatedAt" type="datetime-local" /></label>
        <label>操作人姓名<input v-model="form.operatorName" maxlength="80" /></label>
        <label>
          备注
          <input v-model="form.notes" :placeholder="needNotes ? '休耕分区必填' : '选填'" />
        </label>
      </div>
      <p v-if="zoneBlocked" class="error">该分区为空闲状态，禁止登记行程。</p>
      <p v-else-if="needNotes" class="hint" style="margin-top:8px">休耕分区允许登记，但备注必填。</p>
      <p v-if="form.direction === 'open' && form.extent > 60" class="hint" style="margin-top:8px">
        将联动写入气候记录：采样时刻等于操作时刻，PAR 默认 120 µmol（&lt; 200）。
      </p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="conflict" class="error">
        409 冲突：同分区操作时刻前后 15 分钟内已有行程，已有行程编号 #{{ conflict }}。
      </p>
      <p v-if="success" style="color:var(--leaf);margin:8px 0">{{ success }}</p>
      <div class="actions" style="margin-top:12px">
        <button class="btn" @click="save">登记</button>
        <button class="btn ghost" @click="resetForm">清空</button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>操作时刻</th>
            <th>温室/分区</th>
            <th>方向</th>
            <th>幅度</th>
            <th>操作人</th>
            <th>备注</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list" :key="row.id">
            <td>{{ new Date(row.operatedAt).toLocaleString() }}</td>
            <td>{{ row.greenhouseName }} / {{ row.zoneCode }}</td>
            <td>
              <span class="badge" :class="row.direction">
                {{ directionLabel[row.direction] || row.direction }}
              </span>
            </td>
            <td>{{ row.extent }}</td>
            <td>{{ row.operatorName }}</td>
            <td>{{ row.notes || '—' }}</td>
            <td class="actions">
              <button class="btn danger" @click="remove(row.id)">删除</button>
            </td>
          </tr>
          <tr v-if="!list.length">
            <td colspan="7" style="color:var(--muted)">暂无行程记录</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
