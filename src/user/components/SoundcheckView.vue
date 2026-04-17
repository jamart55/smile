<script setup>
/**
 * SoundcheckView — Plays a dog bark audio, then asks child to click
 * the matching animal. Uses steps: 'listen' then 'choose'.
 *
 * Note: The hotspot animal image is missing. Using text buttons as
 * placeholder until the image is provided.
 */
import { ref, nextTick } from 'vue'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const api = useViewAPI()

const audioEl = ref(null)
const phase = ref('listen') // 'listen' | 'choose' | 'result'
const selected = ref(null)

const animals = [
  { id: 'horse', label: 'Horse', emoji: '🐴' },
  { id: 'bird', label: 'Bird', emoji: '🐦' },
  { id: 'dog', label: 'Dog', emoji: '🐕' },
  { id: 'cow', label: 'Cow', emoji: '🐄' },
]

function onAudioEnded() {
  phase.value = 'choose'
}

function playAudio() {
  if (audioEl.value) {
    audioEl.value.play()
  }
}

function selectAnimal(animal) {
  selected.value = animal.id
  api.recordPageData({ soundcheck_response: animal.id, soundcheck_correct: animal.id === 'dog' })
  phase.value = 'result'
}

function finish() {
  if (selected.value !== 'dog') {
    // Failed soundcheck — could redirect to withdraw or show message
    // For now, allow them to continue
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
    <div class="flex flex-col items-center justify-center h-full p-6">
      <!-- Listen phase -->
      <div v-if="phase === 'listen'" class="text-center">
        <h2 class="text-2xl font-bold mb-4">Sound Check</h2>
        <p class="text-muted-foreground mb-6">
          This is a sound check. If you don't hear any sound, our audio must not be working
          properly on your computer. Please exit and email discoveriesinaction@gmail.com for help.
        </p>
        <video
          ref="audioEl"
          :src="api.getPublicUrl('videos/intro/soundcheck_dog.mp4')"
          class="hidden"
          @ended="onAudioEnded"
          playsinline
        />
        <Button variant="default" size="lg" @click="playAudio">
          Play Sound
        </Button>
      </div>

      <!-- Choose phase -->
      <div v-if="phase === 'choose'" class="text-center">
        <h2 class="text-2xl font-bold mb-4">Which animal did you hear?</h2>
        <p class="text-muted-foreground mb-6">Please click on the animal that matches the sound.</p>
        <div class="grid grid-cols-2 gap-4 max-w-md">
          <button
            v-for="animal in animals"
            :key="animal.id"
            class="flex flex-col items-center justify-center p-6 border-2 border-border rounded-lg hover:border-primary hover:bg-muted transition-colors cursor-pointer"
            @click="selectAnimal(animal)"
          >
            <span class="text-5xl mb-2">{{ animal.emoji }}</span>
            <span class="text-lg font-semibold">{{ animal.label }}</span>
          </button>
        </div>
      </div>

      <!-- Result phase -->
      <div v-if="phase === 'result'" class="text-center">
        <h2 class="text-2xl font-bold mb-4">
          {{ selected === 'dog' ? 'Correct!' : 'That\'s not quite right.' }}
        </h2>
        <p v-if="selected !== 'dog'" class="text-muted-foreground mb-6">
          The sound was a dog. Please make sure your audio is working.
        </p>
        <Button variant="default" size="lg" @click="finish">Continue</Button>
      </div>
    </div>
  </ConstrainedTaskWindow>
</template>
