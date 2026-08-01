<script setup>
import { ref, nextTick, onMounted } from 'vue'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const api = useViewAPI()

const videoEl = ref(null)
const videoEnded = ref(false)

api.steps.append([
  { id: 'setup-01', src: 'videos/setup/01_setup-vid.mp4' },
  { id: 'setup-02', src: 'videos/setup/02_setup-vid.mp4' },
])

const TRIAL_VIDEOS = [
  'videos/trials/100_quad_calibration_beep.mp4',
  'videos/trials/01_ul-quad-car.mp4',   'videos/trials/01_attention.mp4',
  'videos/trials/02_bl-quad-cup.mp4',   'videos/trials/02_attention.mp4',
  'videos/trials/03_br-quad-train.mp4', 'videos/trials/03_attention.mp4',
  'videos/trials/04_ul-quad-apple.mp4', 'videos/trials/04_attention.mp4',
  'videos/trials/101_diamond_calibration.mp4',
  'videos/trials/05_up-diam-car.mp4',   'videos/trials/05_attention.mp4',
  'videos/trials/06_down-diam-dog.mp4', 'videos/trials/06_attention.mp4',
  'videos/trials/07_r-lr-shoes.mp4',    'videos/trials/07_attention.mp4',
  'videos/trials/08_l-lr-train.mp4',    'videos/trials/08_attention.mp4',
]

// Hold refs so GC doesn't collect before videos finish buffering
const _preloadEls = []

onMounted(() => {
  for (const path of TRIAL_VIDEOS) {
    const v = document.createElement('video')
    v.preload = 'auto'
    v.src = api.getPublicUrl(path)
    _preloadEls.push(v)
  }
})

function playVideo() {
  if (videoEl.value) {
    videoEl.value.play()
  }
}

function onVideoEnded() {
  if (api.isLastStep()) {
    videoEnded.value = true
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
    <div class="flex flex-col h-full w-full">
      <div class="flex-1 min-h-0 flex items-center justify-center">
        <video
          ref="videoEl"
          :key="api.stepData.id"
          :src="api.getPublicUrl(api.stepData.src)"
          class="max-w-full max-h-full object-contain"
          @ended="onVideoEnded"
          @canplay="playVideo"
          playsinline
        />
      </div>
      <div class="flex justify-center py-3 flex-shrink-0" style="min-height: 52px;">
        <Button v-if="videoEnded" variant="default" size="lg" @click="api.goNextView()">
          Continue
        </Button>
      </div>
    </div>
  </ConstrainedTaskWindow>
</template>
