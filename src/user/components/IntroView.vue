<script setup>
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
    <div class="flex flex-col h-full">
      <div class="flex-1 min-h-0 flex items-center justify-center">
        <img
          v-if="api.stepData.id === 'start'"
          :src="api.getPublicUrl('images/intro/start-img.png')"
          alt="Start"
          class="max-w-full max-h-full object-contain"
        />
        <img
          v-else
          :src="api.getPublicUrl('images/intro/3-items.jpeg')"
          alt="Instructions"
          class="max-w-full max-h-full object-contain"
        />
      </div>
      <div class="flex justify-center py-3 flex-shrink-0">
        <Button variant="default" size="lg" @click="next">Continue</Button>
      </div>
    </div>
  </ConstrainedTaskWindow>
</template>
