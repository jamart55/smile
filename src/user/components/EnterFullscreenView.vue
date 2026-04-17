<script setup>
/**
 * EnterFullscreenView — Prompts parent to enter fullscreen before trials begin.
 * Clicking the button enters fullscreen, records the recording_start_ts
 * (for OWLET alignment), and advances to the trial view.
 */
import { useFullscreen } from '@vueuse/core'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const api = useViewAPI()
const { enter: enterFullscreen } = useFullscreen()

async function startTrials() {
  // Record the timestamp right before trials begin.
  // OWLET uses this to compute: trial_offset = trial_start_ts - recording_start_ts
  api.persist.recording_start_ts = Date.now()

  try {
    await enterFullscreen()
  } catch (e) {
    console.warn('Fullscreen request failed:', e)
  }
  api.goNextView()
}
</script>

<template>
  <ConstrainedTaskWindow
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
      <Button variant="default" size="lg" @click="startTrials">
        Enter Full Screen &amp; Start
      </Button>
    </div>
  </ConstrainedTaskWindow>
</template>
