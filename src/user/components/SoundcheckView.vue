<script setup>
import { ref } from 'vue'
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

function playAudio() {
  if (audioEl.value) audioEl.value.play()
}

function onAudioEnded() {
  phase.value = 'choose'
}

function selectAnimal(animal) {
  selected.value = animal.id
  api.recordPageData({ soundcheck_response: animal.id, soundcheck_correct: animal.id === 'dog' })
  phase.value = 'result'
}

function finish() {
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
      <!-- Listen/Choose phase — combined -->
      <div v-if="phase !== 'result'" class="text-center">
        <h2 class="text-2xl font-bold mb-4">Sound Check</h2>
        <p class="text-muted-foreground mb-6">
          This is a sound check. If you don't hear any sound, our audio must not be working
          properly on your computer. Please exit and email discoveriesinaction@gmail.com for help.
        </p>
        <video
          ref="audioEl"
          :src="api.getPublicUrl('videos/intro/soundcheck_dog.mp4')"
          class="hidden"
          @canplay="playAudio"
          @ended="onAudioEnded"
          playsinline
        />
        <p class="text-lg font-semibold mb-4">Which animal did you hear?</p>
        <div class="flex flex-row gap-6 justify-center">
          <button
            v-for="animal in animals"
            :key="animal.id"
            class="flex flex-col items-center justify-center p-4 border-2 border-border rounded-lg transition-colors"
            :class="phase === 'choose'
              ? 'hover:border-primary hover:bg-muted cursor-pointer'
              : 'opacity-40 cursor-not-allowed'"
            :disabled="phase !== 'choose'"
            @click="phase === 'choose' && selectAnimal(animal)"
          >
            <span class="text-8xl mb-1">{{ animal.emoji }}</span>
            <span class="text-base font-semibold">{{ animal.label }}</span>
          </button>
        </div>
      </div>

      <!-- Result phase -->
      <div v-if="phase === 'result'" class="text-center">
        <h2 class="text-2xl font-bold mb-4">
          {{ selected === 'dog' ? 'Correct!' : "That's not quite right." }}
        </h2>
        <p v-if="selected !== 'dog'" class="text-muted-foreground mb-6">
          The sound was a dog. Please make sure your audio is working.
        </p>
        <Button variant="default" size="lg" @click="finish">Continue</Button>
      </div>
    </div>
  </ConstrainedTaskWindow>
</template>
