<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const list = ref([])
const zones = ref([])
const error = ref('')
const conflict = ref(null)
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
  note: '',
})

const statusLabel = { idle: '空闲', growing: '在种', fallow: '休耕' }
const directionLabel = { open: '拉开', close: '收拢' }

const selectedZone = computed(
  () => zones.value.find((z) => z.id === Number(form.zoneId)) || null
)
const willLinkClimate = computed(
  () => form.direction === 'open' && Number(form.extent) > 60
)

function resetForm() {
  conflict.value = null
  form.zoneId = zones.value.find((z) => z.status !== 'idle')?.id || zones.value[0]?.id || ''
  form.direction = 'open'
  form.extent = 80
  form.operatedAt = localInputValue()
  form.operatorName = ''
  form.note = ''
}

async function loadZones() {
  const { data } = await api.get('/zones/')
  zones.value = data.results || data
  if (!form.zoneId) {
    form.zoneId = zones.value.find((z) => z.status !== 'idle')?.id || zones.value[0]?.id || ''
  }
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
  if (!form.zoneId) {
    error.value = '请选择分区'
    return
  }
  const extent = Number(form.extent)
  if (!Number.isInteger(extent) || extent < 1 || extent > 100) {
    error.value = '幅度须为 1～100 的整数'
    return
  }
  if (!form.operatorName.trim()) {
    error.value = '请填写操作人姓名'
    return
  }
  if (selectedZone.value?.status === 'idle') {
    error.value = '空闲分区禁止登记遮阳行程'
    return
  }
  if (selectedZone.value?.status === 'fallow' && !form.note.trim()) {
    error.value = '休耕分区登记遮阳行程时备注必填'
    return
  }
  const payload = {
    zoneId: Number(form.zoneId),
    direction: form.direction,
    extent,
    operatedAt: new Date(form.operatedAt).toISOString(),
    operatorName: form.operatorName.trim(),
    note: form.note.trim(),
  }
  try {
    await api.post('/shade-travels/', payload)
    resetForm()
    await load()
  } catch (e) {
    const data = e.response?.data
    if (e.response?.status === 409) {
      conflict.value = data
    } else {
      error.value = JSON.stringify(data || '保存失败')
    }
  }
}

async function remove(id) {
  if (!confirm('确认删除该遮阳行程？')) return
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
        <p>记录帘子拉开 / 收拢的幅度；同分区操作时刻前后 15 分钟内不得重复登记</p>
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
              {{ z.greenhouseName }} / {{ z.zoneCode }}（{{ statusLabel[z.status] }}）
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
        <label>幅度（1～100）<input v-model.number="form.extent" type="number" min="1" max="100" step="1" /></label>
        <label>操作时刻<input v-model="form.operatedAt" type="datetime-local" /></label>
        <label>操作人姓名<input v-model="form.operatorName" maxlength="80" placeholder="如：张师傅" /></label>
        <label>
          备注<span v-if="selectedZone?.status === 'fallow'" class="req">（休耕分区必填）</span>
          <input v-model="form.note" maxlength="255" :placeholder="selectedZone?.status === 'fallow' ? '休耕分区必须填写备注' : '选填'" />
        </label>
      </div>
      <p v-if="selectedZone?.status === 'idle'" class="error">该分区为空闲状态，禁止登记遮阳行程。</p>
      <p v-else-if="willLinkClimate" class="hint" style="color:var(--leaf-deep)">
        拉开幅度大于 60，保存时将以同一事务联动写入一条气候记录：采样时刻＝操作时刻，光合有效辐射 PAR 取默认值 120 µmol（&lt; 200）。
      </p>
      <div v-if="conflict" class="conflict-box">
        <strong>行程冲突（409）：</strong>同分区在操作时刻前后 15 分钟内已有行程
        <em>#{{ conflict.conflictTravelId }}</em>
        （{{ new Date(conflict.conflictOperatedAt).toLocaleString() }}），请调整操作时刻后重试。
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions" style="margin-top:12px">
        <button class="btn" @click="save">登记行程</button>
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
            <td><span class="badge" :class="row.direction">{{ directionLabel[row.direction] || row.direction }}</span></td>
            <td>{{ row.extent }}%</td>
            <td>{{ row.operatorName }}</td>
            <td>{{ row.note || '—' }}</td>
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

<style scoped>
.req {
  color: var(--danger);
}
.conflict-box {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f7e6e2;
  border: 1px solid #d8a398;
  color: var(--danger);
  font-size: 0.9rem;
}
.badge.open {
  background: #f3e4c8;
  color: var(--earth-deep);
}
.badge.close {
  background: #d9e8f0;
  color: #31505f;
}
</style>
