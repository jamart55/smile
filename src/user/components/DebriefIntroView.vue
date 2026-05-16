<script setup>
import { ref } from 'vue'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const api = useViewAPI()
const videoEl = ref(null)
const videoEnded = ref(false)

function playVideo() {
  if (videoEl.value) videoEl.value.play()
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
          :src="api.getPublicUrl('videos/debrief/debrief-intro.mp4')"
          class="max-w-full max-h-full object-contain"
          @ended="videoEnded = true"
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
