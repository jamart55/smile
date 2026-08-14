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

// pilot-02: condition isn't known yet at setup time, so preload both layouts' videos.
const TRIAL_VIDEOS = [
  'videos/trials/pilot02/calib/quad-calib.mp4',
  'videos/trials/pilot02/calib/diam-calib.mp4',
  'videos/trials/pilot02/quad/01_car_UL.mp4',
  'videos/trials/pilot02/quad/02_apple_UR.mp4',
  'videos/trials/pilot02/quad/03_train_BR.mp4',
  'videos/trials/pilot02/quad/04_dog_UL.mp4',
  'videos/trials/pilot02/quad/05_cup_BL.mp4',
  'videos/trials/pilot02/quad/06_car_UR.mp4',
  'videos/trials/pilot02/quad/07_bike_BL.mp4',
  'videos/trials/pilot02/quad/08_shoes_BR.mp4',
  'videos/trials/pilot02/diam/01_car_B.mp4',
  'videos/trials/pilot02/diam/02_apple_T.mp4',
  'videos/trials/pilot02/diam/03_car_R.mp4',
  'videos/trials/pilot02/diam/04_bottle_B.mp4',
  'videos/trials/pilot02/diam/05_dog_L.mp4',
  'videos/trials/pilot02/diam/06_train_T.mp4',
  'videos/trials/pilot02/diam/07_bike_L.mp4',
  'videos/trials/pilot02/diam/08_shoes_R.mp4',
  'videos/trials/pilot02/ag/rainbow.mp4',
  'videos/trials/pilot02/ag/inversion.mp4',
  'videos/trials/pilot02/ag/blob.mp4',
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
