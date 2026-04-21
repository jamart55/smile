<script setup>
import { ref, onMounted } from 'vue'

import useViewAPI from '@/core/composables/useViewAPI'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const api = useViewAPI()
const videoEl = ref(null)

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
    <div class="flex items-center justify-center h-full bg-black">
      <video
        ref="videoEl"
        :src="api.getPublicUrl('videos/debrief/upload-vid.mp4')"
        class="max-w-full max-h-full"
        @canplay="playVideo"
        @ended="api.goNextView()"
        playsinline
      />
    </div>
  </ConstrainedTaskWindow>
</template>
