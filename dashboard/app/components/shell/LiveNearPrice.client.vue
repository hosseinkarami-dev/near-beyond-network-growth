<script setup lang="ts">
import { ArrowDownRight, ArrowUpRight } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

type BinanceTicker = { e?: string, s?: string, c?: string, P?: string, E?: number }
type ConnectionState = 'connecting' | 'live' | 'polling' | 'reconnecting'

const STREAM_URLS = [
  'wss://stream.binance.com:443/ws/nearusdt@ticker',
  'wss://data-stream.binance.vision/ws/nearusdt@ticker',
]
const REST_URL = 'https://data-api.binance.vision/api/v3/ticker/24hr?symbol=NEARUSDT'
const price = ref<number | null>(null)
const change24h = ref<number | null>(null)
const state = ref<ConnectionState>('connecting')
const motion = ref<'up' | 'down' | ''>('')

let socket: WebSocket | null = null
let retryTimer: ReturnType<typeof setTimeout> | undefined
let motionTimer: ReturnType<typeof setTimeout> | undefined
let connectionTimer: ReturnType<typeof setTimeout> | undefined
let pollingTimer: ReturnType<typeof setInterval> | undefined
let retryDelay = 1200
let streamIndex = 0
let disposed = false

const formattedPrice = computed(() => price.value == null
  ? '—'
  : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: price.value < 1 ? 5 : 4 }).format(price.value))
const formattedChange = computed(() => change24h.value == null
  ? null
  : `${change24h.value > 0 ? '+' : ''}${change24h.value.toFixed(2)}%`)
const freshnessLabel = computed(() => ({ live: 'Live', polling: 'Polling', connecting: 'Connecting', reconnecting: 'Retrying' })[state.value])

function applyTicker(ticker: BinanceTicker, source: 'stream' | 'poll' = 'stream') {
  const nextPrice = Number(ticker.c)
  const nextChange = Number(ticker.P)
  if (!Number.isFinite(nextPrice) || nextPrice <= 0) return

  const previous = price.value
  price.value = nextPrice
  if (Number.isFinite(nextChange)) change24h.value = nextChange
  state.value = source === 'stream' ? 'live' : 'polling'
  retryDelay = 1200
  if (source === 'stream' && pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = undefined
  }

  if (previous != null && previous !== nextPrice) {
    motion.value = nextPrice > previous ? 'up' : 'down'
    if (motionTimer) clearTimeout(motionTimer)
    motionTimer = setTimeout(() => { motion.value = '' }, 700)
  }
}

function scheduleReconnect() {
  if (disposed || retryTimer) return
  state.value = 'reconnecting'
  retryTimer = setTimeout(() => {
    retryTimer = undefined
    connect()
  }, retryDelay)
  retryDelay = Math.min(Math.round(retryDelay * 1.8), 30000)
}

function connect() {
  if (disposed) return
  state.value = price.value == null ? 'connecting' : 'reconnecting'
  try {
    socket = new WebSocket(STREAM_URLS[streamIndex % STREAM_URLS.length]!)
    connectionTimer = setTimeout(() => socket?.close(), 8000)
    socket.onopen = () => {
      if (connectionTimer) clearTimeout(connectionTimer)
      connectionTimer = setTimeout(() => socket?.close(), 8000)
      retryDelay = 1200
    }
    socket.onmessage = (event) => {
      if (connectionTimer) {
        clearTimeout(connectionTimer)
        connectionTimer = undefined
      }
      try {
        applyTicker(JSON.parse(event.data) as BinanceTicker)
      } catch {
        // Ignore malformed stream messages and keep the connection open.
      }
    }
    socket.onerror = () => socket?.close()
    socket.onclose = () => {
      if (connectionTimer) {
        clearTimeout(connectionTimer)
        connectionTimer = undefined
      }
      socket = null
      streamIndex = (streamIndex + 1) % STREAM_URLS.length
      startRestFallback()
      scheduleReconnect()
    }
  } catch {
    streamIndex = (streamIndex + 1) % STREAM_URLS.length
    startRestFallback()
    scheduleReconnect()
  }
}

async function pollBinanceTicker() {
  try {
    const response = await fetch(REST_URL, { cache: 'no-store', signal: AbortSignal.timeout(4500) })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    applyTicker(await response.json() as BinanceTicker, 'poll')
  } catch {
    if (state.value !== 'live') state.value = 'reconnecting'
  }
}

function startRestFallback() {
  if (disposed || pollingTimer) return
  state.value = 'polling'
  void pollBinanceTicker()
  pollingTimer = setInterval(() => { void pollBinanceTicker() }, 5000)
}

async function loadFallback() {
  try {
    const response = await fetch('/data/analytics/tokenomics/snapshot.json', { cache: 'no-cache' })
    if (!response.ok) return
    const document = await response.json()
    const current = Number(document?.metrics?.near_price?.value)
    const dailyChange = Number(document?.metrics?.change_24h)
    if (price.value == null && Number.isFinite(current) && current > 0) price.value = current
    if (change24h.value == null && Number.isFinite(dailyChange)) change24h.value = dailyChange
  } catch {
    // The stream remains the primary source; keep the card in its connecting state.
  }
}

onMounted(() => {
  void loadFallback()
  connect()
})

onBeforeUnmount(() => {
  disposed = true
  if (retryTimer) clearTimeout(retryTimer)
  if (motionTimer) clearTimeout(motionTimer)
  if (connectionTimer) clearTimeout(connectionTimer)
  if (pollingTimer) clearInterval(pollingTimer)
  if (socket) {
    socket.onclose = null
    socket.onerror = null
    socket.close()
    socket = null
  }
})
</script>

<template>
  <section class="live-price-card" :class="[`live-price-${state}`, motion ? `price-flash-${motion}` : '']" aria-label="Live NEAR price in USDT">
    <div class="live-price-top">
      <div class="live-price-title"><span class="live-price-token">N</span><span>NEAR <small>/ USDT</small></span></div>
      <span class="live-price-state" :title="state === 'polling' ? 'Live WebSocket is unavailable; updating from Binance REST every 5 seconds.' : 'Binance Spot market data connection status'"><i /><span>{{ freshnessLabel }}</span></span>
    </div>
    <div class="live-price-main">
      <Transition name="price-tick" mode="out-in"><strong :key="formattedPrice">{{ formattedPrice }}</strong></Transition>
      <span v-if="formattedChange" class="live-price-change" :class="change24h! >= 0 ? 'change-positive' : 'change-negative'">
        <ArrowUpRight v-if="change24h! >= 0" :size="12" />
        <ArrowDownRight v-else :size="12" />
        {{ formattedChange }} <small>24h</small>
      </span>
      <span v-else class="live-price-change-placeholder">Waiting for ticker…</span>
    </div>
  </section>
</template>
