<script setup>
/**
 * TrialView — Core eye-tracking trial view.
 * Plays 8 trial videos, each followed by an attention-getter video, plus 2
 * calibration videos (before trial 01 and 05) with no attention-getter.
 * Runs in fullscreen (entered by EnterFullscreenView).
 *
 * Records absolute timestamps (Date.now()) for OWLET compatibility:
 *   - trial_start_ts / trial_end_ts / trial_duration_ms
 *   - attention_start_ts / attention_end_ts / attention_duration_ms
 *
 * Also records view-level trials_block_start_ts / trials_block_end_ts, and
 * fullscreen_events (timestamped enter/exit) for detecting non-fullscreen sessions.
 */
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useFullscreen } from '@vueuse/core'
import useViewAPI from '@/core/composables/useViewAPI'

const api = useViewAPI()
const { exit: exitFullscreen } = useFullscreen()

const videoEl = ref(null)
const phase = ref('trial') // 'trial' | 'attention'

// Track fullscreen exits (e.g. Esc mid-trial) — analysis uses this to flag
// sessions where the video wasn't actually filling the screen for AOI math.
if (!api.persist.isDefined('fullscreen_events')) {
  api.persist.fullscreen_events = []
}
function onFullscreenChange() {
  api.persist.fullscreen_events.push({
    ts: Date.now(),
    fullscreen: document.fullscreenElement != null,
  })
}
onMounted(() => document.addEventListener('fullscreenchange', onFullscreenChange))
onUnmounted(() => document.removeEventListener('fullscreenchange', onFullscreenChange))

api.steps.append([
  { id: '100', kind: 'calib', layout: 'quadrant',  name: 'quad-calib',  trial: 'videos/trials/100_quad_calibration_beep.mp4', attention: null },
  { id: '01', kind: 'trial', layout: 'quadrant', name: 'ul-quad-car', trial: 'videos/trials/01_ul-quad-car.mp4', attention: 'videos/trials/01_attention.mp4' },
  { id: '02', kind: 'trial', layout: 'quadrant', name: 'bl-quad-cup', trial: 'videos/trials/02_bl-quad-cup.mp4', attention: 'videos/trials/02_attention.mp4' },
  { id: '03', kind: 'trial', layout: 'quadrant', name: 'br-quad-train', trial: 'videos/trials/03_br-quad-train.mp4', attention: 'videos/trials/03_attention.mp4' },
  { id: '04', kind: 'trial', layout: 'quadrant', name: 'ul-quad-apple', trial: 'videos/trials/04_ul-quad-apple.mp4', attention: 'videos/trials/04_attention.mp4' },
  { id: '101', kind: 'calib', layout: 'diamond',   name: 'diam-calib',  trial: 'videos/trials/101_diamond_calibration.mp4', attention: null },
  { id: '05', kind: 'trial', layout: 'diamond', name: 'up-diam-car', trial: 'videos/trials/05_up-diam-car.mp4', attention: 'videos/trials/05_attention.mp4' },
  { id: '06', kind: 'trial', layout: 'diamond', name: 'down-diam-dog', trial: 'videos/trials/06_down-diam-dog.mp4', attention: 'videos/trials/06_attention.mp4' },
  { id: '07', kind: 'trial', layout: 'leftright', name: 'r-lr-shoes', trial: 'videos/trials/07_r-lr-shoes.mp4', attention: 'videos/trials/07_attention.mp4' },
  { id: '08', kind: 'trial', layout: 'leftright', name: 'l-lr-train', trial: 'videos/trials/08_l-lr-train.mp4', attention: 'videos/trials/08_attention.mp4' },
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

// A video that fails to load fires neither 'canplay' nor 'ended', so without this the view
// sits on a white screen forever with no console output and the session is lost -- the exact
// symptom of the HEVC calibration videos Chrome could not decode.
if (!api.persist.isDefined('video_errors')) {
  api.persist.video_errors = []
}
function onVideoError() {
  const err = videoEl.value?.error
  const msg = `${currentVideoSrc()} — code=${err?.code} ${err?.message ?? ''}`
  console.error('[TrialView] video failed:', msg)
  api.persist.video_errors.push({ ts: Date.now(), step: api.stepData.id, phase: phase.value, msg })
  api.stepData[phase.value === 'trial' ? 'trial_error' : 'attention_error'] = msg
  // Both phases record exactly once here: onVideoEnded's recordStep is never reached on the
  // path that errored, so this does not double-record the step.
  api.recordStep()
  advanceAfterStep()
}

function advanceAfterStep() {
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

function onVideoEnded() {
  if (phase.value === 'trial') {
    // Record absolute end timestamp and duration for trial
    api.stepData.trial_end_ts = Date.now()
    api.stepData.trial_duration_ms = api.stepData.trial_end_ts - api.stepData.trial_start_ts

    if (api.stepData.attention == null) {
      // Calibration steps have no attention-getter — skip straight to the next step.
      api.recordStep()
      advanceAfterStep()
    } else {
      // Switch to attention-getter
      phase.value = 'attention'
      nextTick(() => playVideo())
    }
  } else {
    // Record absolute end timestamp and duration for attention-getter
    api.stepData.attention_end_ts = Date.now()
    api.stepData.attention_duration_ms = api.stepData.attention_end_ts - api.stepData.attention_start_ts
    api.recordStep()

    advanceAfterStep()
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-white flex items-center justify-center z-50">
    <video
      ref="videoEl"
      :key="api.stepData.id + '-' + phase"
      :src="currentVideoSrc()"
      class="w-full h-full object-contain"
      @play="onVideoPlay"
      @ended="onVideoEnded"
      @canplay="playVideo"
      @error="onVideoError"
      playsinline
    />
  </div>
</template>
