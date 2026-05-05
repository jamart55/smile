<script setup>
import { ref, onMounted } from 'vue'
import { useFullscreen } from '@vueuse/core'
import useViewAPI from '@/core/composables/useViewAPI'

const api = useViewAPI()
const { exit: exitFullscreen } = useFullscreen()

const STEPS = [
  { id: '01', name: 'ul-quad-car', trial: 'videos/trials/01_ul-quad-car.mp4', attention: 'videos/trials/01_attention.mp4' },
  { id: '02', name: 'bl-quad-cup', trial: 'videos/trials/02_bl-quad-cup.mp4', attention: 'videos/trials/02_attention.mp4' },
  { id: '03', name: 'br-quad-train', trial: 'videos/trials/03_br-quad-train.mp4', attention: 'videos/trials/03_attention.mp4' },
  { id: '04', name: 'ul-quad-apple', trial: 'videos/trials/04_ul-quad-apple.mp4', attention: 'videos/trials/04_attention.mp4' },
  { id: '05', name: 'up-diam-car', trial: 'videos/trials/05_up-diam-car.mp4', attention: 'videos/trials/05_attention.mp4' },
  { id: '06', name: 'down-diam-dog', trial: 'videos/trials/06_down-diam-dog.mp4', attention: 'videos/trials/06_attention.mp4' },
  { id: '07', name: 'r-lr-shoes', trial: 'videos/trials/07_r-lr-shoes.mp4', attention: 'videos/trials/07_attention.mp4' },
  { id: '08', name: 'l-lr-train', trial: 'videos/trials/08_l-lr-train.mp4', attention: 'videos/trials/08_attention.mp4' },
]

api.steps.append(STEPS)

if (!api.persist.isDefined('trials_block_start_ts')) {
  api.persist.trials_block_start_ts = Date.now()
}

// Flat sequence: [trial1, attn1, trial2, attn2, ...]
const allSrcs = STEPS.flatMap(s => [
  api.getPublicUrl(s.trial),
  api.getPublicUrl(s.attention),
])

// srcIndex: position in allSrcs for the currently-playing video
// even = trial phase, odd = attention phase
let srcIndex = 0

const videoA = ref(null)
const videoB = ref(null)
const activeBuffer = ref('A')

function activeVideo() { return activeBuffer.value === 'A' ? videoA.value : videoB.value }
function inactiveVideo() { return activeBuffer.value === 'A' ? videoB.value : videoA.value }
function isTrial(idx) { return idx % 2 === 0 }

// Called when current video starts playing — preload the next one into inactive buffer
function preloadNext() {
  const nextIdx = srcIndex + 1
  if (nextIdx < allSrcs.length) {
    const el = inactiveVideo()
    if (el) {
      el.src = allSrcs[nextIdx]
      el.load()
    }
  }
}

function onVideoPlay(buffer) {
  if (buffer !== activeBuffer.value) return
  if (isTrial(srcIndex)) {
    api.stepData.trial_start_ts = Date.now()
  } else {
    api.stepData.attention_start_ts = Date.now()
  }
  preloadNext()
}

function onVideoEnded(buffer) {
  if (buffer !== activeBuffer.value) return

  if (isTrial(srcIndex)) {
    api.stepData.trial_end_ts = Date.now()
    api.stepData.trial_duration_ms = api.stepData.trial_end_ts - api.stepData.trial_start_ts
  } else {
    api.stepData.attention_end_ts = Date.now()
    api.stepData.attention_duration_ms = api.stepData.attention_end_ts - api.stepData.attention_start_ts
    api.recordStep()
  }

  srcIndex++

  if (srcIndex >= allSrcs.length) {
    api.persist.trials_block_end_ts = Date.now()
    api.saveData(true)
    exitFullscreen().catch(() => {})
    api.goNextView()
    return
  }

  // Advance the api step index when moving into a new trial
  if (isTrial(srcIndex)) {
    api.goNextStep()
  }

  // Swap to the preloaded buffer and play immediately
  activeBuffer.value = activeBuffer.value === 'A' ? 'B' : 'A'
  activeVideo().play().catch(() => {})
}

// Fallback: if preloading finishes after the swap, start play from canplay
function onCanplay(buffer) {
  if (buffer !== activeBuffer.value) return
  activeVideo().play().catch(() => {})
}

onMounted(() => {
  if (videoA.value) {
    videoA.value.src = allSrcs[0]
    videoA.value.load()
  }
})
</script>

<template>
  <div class="fixed inset-0 bg-black z-50">
    <video
      ref="videoA"
      class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 max-w-full max-h-full"
      :class="{ 'opacity-0 pointer-events-none': activeBuffer !== 'A' }"
      @play="onVideoPlay('A')"
      @ended="onVideoEnded('A')"
      @canplay="onCanplay('A')"
      playsinline
    />
    <video
      ref="videoB"
      class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 max-w-full max-h-full"
      :class="{ 'opacity-0 pointer-events-none': activeBuffer !== 'B' }"
      @play="onVideoPlay('B')"
      @ended="onVideoEnded('B')"
      @canplay="onCanplay('B')"
      playsinline
    />
  </div>
</template>
