<script setup>
import { ref, onMounted } from 'vue'

import useViewAPI from '@/core/composables/useViewAPI'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const api = useViewAPI()
const videoEl = ref(null)
const videoEnded = ref(false)

onMounted(() => {
  api.saveData(true)
})

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
    <div class="flex flex-col items-center justify-center h-full bg-transparent">
      <video
        v-if="!videoEnded"
        ref="videoEl"
        :src="api.getPublicUrl('videos/debrief/upload-vid.mp4')"
        class="max-w-full max-h-full"
        @canplay="playVideo"
        @ended="videoEnded = true"
        playsinline
      />
      <div v-else class="text-center p-8">
        <h1 class="text-3xl font-bold mb-4">Thanks for your contribution to science!</h1>
        <p class="text-lg text-muted-foreground">Your data have been successfully recorded. You may now close this window.</p>
      </div>
    </div>
  </ConstrainedTaskWindow>
</template>
