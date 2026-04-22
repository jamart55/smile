<script setup>
/**
 * FullscreenTestView — test view to validate browser fullscreen
 * within SMILE's constrained layout.
 *
 * Flow:
 * 1. Shows a slide image in the normal constrained SMILE window
 * 2. User clicks "Enter Fullscreen & Play Videos"
 * 3. Goes fullscreen, plays trial video, then attention-getter video
 * 4. Exits fullscreen and returns to constrained view
 */

import { ref, nextTick } from 'vue'
import { useFullscreen } from '@vueuse/core'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const startImg = '/images/intro/start-img.png'
const threeItemsImg = '/images/intro/3-items.jpeg'
const trialVideoSrc = '/videos/trials/02_bl-quad-cup.mp4'
const attentionVideoSrc = '/videos/trials/02_attention.mp4'

const api = useViewAPI()

const phase = ref('slide') // 'slide' | 'trial' | 'attention' | 'done'
const trialVideo = ref(null)
const attentionVideo = ref(null)

const { isFullscreen, enter: enterFullscreen, exit: exitFullscreen } = useFullscreen()

async function startFullscreenVideos() {
  try {
    await enterFullscreen()
  } catch (e) {
    // Fullscreen may fail silently on some browsers — continue anyway
    console.warn('Fullscreen request failed:', e)
  }
  phase.value = 'trial'
  await nextTick()
  if (trialVideo.value) {
    trialVideo.value.play()
  }
}

function onTrialEnded() {
  phase.value = 'attention'
  nextTick(() => {
    if (attentionVideo.value) {
      attentionVideo.value.play()
    }
  })
}

async function onAttentionEnded() {
  phase.value = 'done'
  if (isFullscreen.value) {
    await exitFullscreen()
  }
}

async function exitAndContinue() {
  if (isFullscreen.value) {
    await exitFullscreen()
  }
  api.goNextView()
}
</script>

<template>
  <!-- Phase: slide image (normal constrained view) -->
  <ConstrainedTaskWindow
    v-if="phase === 'slide'"
    variant="ghost"
    :responsiveUI="api.config.responsiveUI"
    :width="api.config.windowsizerRequest.width"
    :height="api.config.windowsizerRequest.height"
  >
    <div class="flex flex-col items-center justify-center h-full p-4 gap-4">
      <div class="flex gap-4 flex-1 min-h-0 items-center justify-center">
        <img :src="startImg" alt="Start" class="max-h-full max-w-[45%] object-contain" />
        <img :src="threeItemsImg" alt="3 items" class="max-h-full max-w-[45%] object-contain" />
      </div>
      <Button variant="default" size="lg" @click="startFullscreenVideos">
        Enter Fullscreen &amp; Play Videos
      </Button>
    </div>
  </ConstrainedTaskWindow>

  <!-- Phase: fullscreen video playback (trial then attention-getter) -->
  <div
    v-if="phase === 'trial' || phase === 'attention'"
    class="fixed inset-0 bg-black flex items-center justify-center z-50"
  >
    <video
      v-if="phase === 'trial'"
      ref="trialVideo"
      :src="trialVideoSrc"
      class="max-w-full max-h-full"
      @ended="onTrialEnded"
      playsinline
    />
    <video
      v-if="phase === 'attention'"
      ref="attentionVideo"
      :src="attentionVideoSrc"
      class="max-w-full max-h-full"
      @ended="onAttentionEnded"
      playsinline
    />
  </div>

  <!-- Phase: done — back to constrained view -->
  <ConstrainedTaskWindow
    v-if="phase === 'done'"
    variant="ghost"
    :responsiveUI="api.config.responsiveUI"
    :width="api.config.windowsizerRequest.width"
    :height="api.config.windowsizerRequest.height"
  >
    <div class="flex flex-col items-center justify-center h-full p-4">
      <h1 class="text-3xl font-bold mb-4">Fullscreen Test Complete</h1>
      <p class="text-muted-foreground mb-2">
        Fullscreen entered: <strong>{{ isFullscreen ? 'Yes' : 'No (exited)' }}</strong>
      </p>
      <p class="text-muted-foreground mb-6">
        Videos played successfully. You are back in the constrained SMILE window.
      </p>
      <div class="flex gap-4">
        <Button variant="outline" @click="phase = 'slide'">Try Again</Button>
        <Button variant="default" @click="exitAndContinue">Continue</Button>
      </div>
    </div>
  </ConstrainedTaskWindow>
</template>
