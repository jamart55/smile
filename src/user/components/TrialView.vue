<script setup>
/**
 * TrialView — Core eye-tracking trial view.
 * Plays 8 trial videos, each followed by an attention-getter video.
 * Runs in fullscreen (entered by EnterFullscreenView).
 *
 * Records absolute timestamps (Date.now()) for OWLET compatibility:
 *   - trial_start_ts / trial_end_ts / trial_duration_ms
 *   - attention_start_ts / attention_end_ts / attention_duration_ms
 *
 * Also records view-level trials_block_start_ts / trials_block_end_ts.
 */
import { ref, nextTick } from 'vue'
import { useFullscreen } from '@vueuse/core'
import useViewAPI from '@/core/composables/useViewAPI'

const api = useViewAPI()
const { exit: exitFullscreen } = useFullscreen()

const videoEl = ref(null)
const phase = ref('trial') // 'trial' | 'attention'

api.steps.append([
  { id: '01', name: 'ul-quad-car', trial: 'videos/trials/01_ul-quad-car.mp4', attention: 'videos/trials/01_attention.mp4' },
  { id: '02', name: 'bl-quad-cup', trial: 'videos/trials/02_bl-quad-cup.mp4', attention: 'videos/trials/02_attention.mp4' },
  { id: '03', name: 'br-quad-train', trial: 'videos/trials/03_br-quad-train.mp4', attention: 'videos/trials/03_attention.mp4' },
  { id: '04', name: 'ul-quad-apple', trial: 'videos/trials/04_ul-quad-apple.mp4', attention: 'videos/trials/04_attention.mp4' },
  { id: '05', name: 'up-diam-car', trial: 'videos/trials/05_up-diam-car.mp4', attention: 'videos/trials/05_attention.mp4' },
  { id: '06', name: 'down-diam-dog', trial: 'videos/trials/06_down-diam-dog.mp4', attention: 'videos/trials/06_attention.mp4' },
  { id: '07', name: 'r-lr-shoes', trial: 'videos/trials/07_r-lr-shoes.mp4', attention: 'videos/trials/07_attention.mp4' },
  { id: '08', name: 'l-lr-train', trial: 'videos/trials/08_l-lr-train.mp4', attention: 'videos/trials/08_attention.mp4' },
])

// Record block-level start timestamp
if (!api.persist.isDefined('trials_block_start_ts')) {
  api.persist.trials_block_start_ts = Date.now()
}

function currentVideoSrc() {
  if (phase.value === 'trial') {
    return api.getPublicUrl(api.stepData.trial)
  }
  return api.getPublicUrl(api.stepData.attention)
}

function playVideo() {
  if (videoEl.value) {
    videoEl.value.play()
  }
}

function onVideoPlay() {
  // Record absolute timestamp when video actually starts playing
  if (phase.value === 'trial') {
    api.stepData.trial_start_ts = Date.now()
  } else {
    api.stepData.attention_start_ts = Date.now()
  }
}

function onVideoEnded() {
  if (phase.value === 'trial') {
    // Record absolute end timestamp and duration for trial
    api.stepData.trial_end_ts = Date.now()
    api.stepData.trial_duration_ms = api.stepData.trial_end_ts - api.stepData.trial_start_ts

    // Switch to attention-getter
    phase.value = 'attention'
    nextTick(() => playVideo())
  } else {
    // Record absolute end timestamp and duration for attention-getter
    api.stepData.attention_end_ts = Date.now()
    api.stepData.attention_duration_ms = api.stepData.attention_end_ts - api.stepData.attention_start_ts
    api.recordStep()

    if (api.isLastStep()) {
      // Record block-level end timestamp
      api.persist.trials_block_end_ts = Date.now()
      api.saveData(true)
      exitFullscreen().catch(() => {})
      api.goNextView()
    } else {
      api.goNextStep()
      phase.value = 'trial'
      nextTick(() => playVideo())
    }
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-white flex items-center justify-center z-50">
    <video
      ref="videoEl"
      :key="api.stepData.id + '-' + phase"
      :src="currentVideoSrc()"
      class="max-w-full max-h-full"
      @play="onVideoPlay"
      @ended="onVideoEnded"
      @canplay="playVideo"
      playsinline
    />
  </div>
</template>
