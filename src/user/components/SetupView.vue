<script setup>
/**
 * SetupView — Plays 3 setup/calibration videos in sequence.
 * Each auto-advances after ending.
 */
import { ref, nextTick } from 'vue'
import useViewAPI from '@/core/composables/useViewAPI'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const api = useViewAPI()

const videoEl = ref(null)

api.steps.append([
  { id: 'setup-01', src: 'videos/setup/01_setup-vid.mp4' },
  { id: 'setup-02', src: 'videos/setup/02_setup-vid.mp4' },
  { id: 'setup-03', src: 'videos/setup/03_setup-vid.mp4' },
])

function playVideo() {
  if (videoEl.value) {
    videoEl.value.play()
  }
}

function onVideoEnded() {
  if (api.isLastStep()) {
    api.goNextView()
  } else {
    api.goNextStep()
    nextTick(() => playVideo())
  }
}
</script>

<template>
  <ConstrainedTaskWindow
    variant="ghost"
    :responsiveUI="api.config.responsiveUI"
    :width="api.config.windowsizerRequest.width"
    :height="api.config.windowsizerRequest.height"
  >
    <div class="flex items-center justify-center h-full bg-black">
      <video
        ref="videoEl"
        :key="api.stepData.id"
        :src="api.getPublicUrl(api.stepData.src)"
        class="max-w-full max-h-full"
        @ended="onVideoEnded"
        @canplay="playVideo"
        playsinline
      />
    </div>
  </ConstrainedTaskWindow>
</template>
