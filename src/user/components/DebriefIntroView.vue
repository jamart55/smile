<script setup>
/**
 * DebriefIntroView — Plays the pre-parent debrief video.
 */
import { ref } from 'vue'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const api = useViewAPI()
const videoEl = ref(null)
const videoEnded = ref(false)

function playVideo() {
  if (videoEl.value) {
    videoEl.value.play()
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
    <div class="flex flex-col items-center justify-center h-full p-4">
      <video
        ref="videoEl"
        :src="api.getPublicUrl('videos/debrief/debrief-intro.mp4')"
        class="max-w-full max-h-[80%] object-contain rounded"
        @ended="videoEnded = true"
        @canplay="playVideo"
        playsinline
      />
      <Button
        v-if="videoEnded"
        variant="default"
        size="lg"
        class="mt-4"
        @click="api.goNextView()"
      >
        Continue
      </Button>
    </div>
  </ConstrainedTaskWindow>
</template>
