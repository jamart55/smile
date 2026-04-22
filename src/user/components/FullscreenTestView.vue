<script setup>
import { ref, computed } from 'vue'
import { useFullscreen } from '@vueuse/core'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const api = useViewAPI()
const { enter: enterFullscreen, exit: exitFullscreen, isFullscreen } = useFullscreen()

const phase = ref('slide') // 'slide' | 'trial' | 'attention' | 'done'

const trialSrc = api.getPublicUrl('videos/trials/02_bl-quad-cup.mp4')
const attentionSrc = api.getPublicUrl('videos/trials/02_attention.mp4')

const currentVideoSrc = computed(() =>
  phase.value === 'trial' ? trialSrc : attentionSrc
)

async function startFullscreenVideos() {
  try {
    await enterFullscreen()
  } catch (e) {
    console.warn('Fullscreen request failed:', e)
  }
  phase.value = 'trial'
}

function onVideoEnded() {
  if (phase.value === 'trial') {
    phase.value = 'attention'
  } else {
    exitFullscreen().catch(() => {})
    phase.value = 'done'
  }
}
</script>

<template>
  <!-- Slide: enter fullscreen prompt (matches EnterFullscreenView) -->
  <ConstrainedTaskWindow
    v-if="phase === 'slide'"
    variant="ghost"
    :responsiveUI="api.config.responsiveUI"
    :width="api.config.windowsizerRequest.width"
    :height="api.config.windowsizerRequest.height"
  >
    <div class="flex flex-col items-center justify-center h-full p-6 text-center">
      <h1 class="text-3xl font-bold mb-4">Ready to begin!</h1>
      <p class="text-lg text-muted-foreground mb-2">
        The videos are about to start.
      </p>
      <p class="text-lg text-muted-foreground mb-8">
        Please click the button below to enter full screen mode.
      </p>
      <Button variant="default" size="lg" @click="startFullscreenVideos">
        Enter Full Screen &amp; Start
      </Button>
    </div>
  </ConstrainedTaskWindow>

  <!-- Fullscreen video playback -->
  <div
    v-if="phase === 'trial' || phase === 'attention'"
    class="fixed inset-0 bg-black flex items-center justify-center z-50"
  >
    <video
      :key="phase"
      :src="currentVideoSrc"
      class="max-w-full max-h-full"
      autoplay
      playsinline
      @ended="onVideoEnded"
    />
  </div>

  <!-- Done screen -->
  <ConstrainedTaskWindow
    v-if="phase === 'done'"
    variant="ghost"
    :responsiveUI="api.config.responsiveUI"
    :width="api.config.windowsizerRequest.width"
    :height="api.config.windowsizerRequest.height"
  >
    <div class="flex flex-col items-center justify-center h-full p-6 text-center">
      <h1 class="text-4xl font-bold mb-4">Yay! It worked!</h1>
      <p class="text-muted-foreground mb-8">
        Fullscreen entered: <strong>{{ isFullscreen ? 'Yes' : 'No (exited)' }}</strong>
      </p>
      <div class="flex gap-4">
        <Button variant="outline" @click="phase = 'slide'">Try Again</Button>
        <Button variant="default" @click="api.goNextView()">Continue</Button>
      </div>
    </div>
  </ConstrainedTaskWindow>
</template>
