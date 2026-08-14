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

// pilot-02: single layout (quad or diam) per participant, randomly assigned in
// design.js. Each condition has its own 8 trial videos (filenames carry
// object + target AOI) and reuses 3 AG clips across the 8 slots — one AG
// appears twice, matching the AG that's duplicated inside that condition's
// calibration video (quad: inversion, diam: rainbow).
const TRIAL_FILES = {
  quad: ['01_car_UL', '02_apple_UR', '03_train_BR', '04_dog_UL', '05_cup_BL', '06_car_UR', '07_bike_BL', '08_shoes_BR'],
  diam: ['01_car_B', '02_apple_T', '03_car_R', '04_bottle_B', '05_dog_L', '06_train_T', '07_bike_L', '08_shoes_R'],
}
const AG_ORDER = {
  quad: ['rainbow', 'blob', 'inversion', 'rainbow', 'blob', 'inversion', 'rainbow', 'blob'],
  diam: ['inversion', 'blob', 'rainbow', 'inversion', 'blob', 'rainbow', 'inversion', 'blob'],
}

let layout = api.getConditionByName('layout')
if (!layout) {
  // Should be assigned in design.js at welcome; falling back so a session
  // isn't lost to a white screen (TRIAL_FILES[undefined].map() would throw).
  console.error('[TrialView] layout condition missing, defaulting to quad')
  if (!api.persist.isDefined('video_errors')) api.persist.video_errors = []
  api.persist.video_errors.push({ ts: Date.now(), step: 'init', phase: 'layout', msg: 'layout condition undefined' })
  layout = 'quad'
}

api.steps.append([
  {
    id: '00',
    kind: 'calib',
    layout,
    name: `${layout}-calib`,
    trial: `videos/trials/pilot02/calib/${layout}-calib.mp4`,
    attention: null,
  },
  ...TRIAL_FILES[layout].map((file, i) => ({
    id: file.slice(0, 2),
    kind: 'trial',
    layout,
    name: file,
    trial: `videos/trials/pilot02/${layout}/${file}.mp4`,
    attention: `videos/trials/pilot02/ag/${AG_ORDER[layout][i]}.mp4`,
  })),
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
