<script setup>
import { ref, nextTick } from 'vue'
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
    <div class="flex flex-col h-full">
      <div class="flex-1 min-h-0 flex items-center justify-center">
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
      <div class="flex justify-center py-3 flex-shrink-0" style="min-height: 52px;">
        <Button v-if="videoEnded" variant="default" size="lg" @click="api.goNextView()">
          Continue
        </Button>
      </div>
    </div>
  </ConstrainedTaskWindow>
</template>
