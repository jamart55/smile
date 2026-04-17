<script setup>
/**
 * IntroView — Shows start image, then 3-items instructions image.
 * Uses steps to sequence through the two slides.
 */
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { ConstrainedTaskWindow } from '@/uikit/layouts'

const api = useViewAPI()

api.steps.append([
  { id: 'start' },
  { id: 'three-items' },
])

function next() {
  if (api.isLastStep()) {
    api.goNextView()
  } else {
    api.goNextStep()
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
      <img
        v-if="api.stepData.id === 'start'"
        :src="api.getPublicUrl('images/intro/start-img.png')"
        alt="Start"
        class="max-w-full max-h-[80%] object-contain mb-6"
      />
      <img
        v-else
        :src="api.getPublicUrl('images/intro/3-items.jpeg')"
        alt="Instructions"
        class="max-w-full max-h-[80%] object-contain mb-6"
      />
      <Button variant="default" size="lg" @click="next">Continue</Button>
    </div>
  </ConstrainedTaskWindow>
</template>
