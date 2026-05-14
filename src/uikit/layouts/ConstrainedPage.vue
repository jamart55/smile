<script setup>
import { computed } from 'vue'

const props = defineProps({
  class: {
    type: String,
    default: '',
  },
  responsiveUI: {
    type: Boolean,
    default: true,
    description: 'Whether to use responsive layout behavior',
  },
  width: {
    type: Number,
    default: 800,
    description: 'Width of the page in pixels',
  },
  height: {
    type: Number,
    default: 600,
    description: 'Height of the page in pixels',
  },
})

const containerClasses = computed(() => {
  const baseClasses = 'select-none flex flex-col'

  return [baseClasses, props.class].filter(Boolean).join(' ')
})

const containerStyle = computed(() => {
  if (!props.responsiveUI) {
    return {
      width: props.width + 'px',
      minWidth: props.width + 'px',
      height: props.height + 'px',
      minHeight: props.height + 'px',
    }
  } else {
    const ratio = props.width / props.height
    return {
      width: `min(96vw, calc(92vh * ${ratio}))`,
      height: `min(92vh, calc(96vw / ${ratio}))`,
      marginLeft: 'auto',
      marginRight: 'auto',
    }
  }
})
</script>

<template>
  <div class="flex justify-center">
    <div :class="containerClasses" :style="containerStyle">
      <slot />
    </div>
  </div>
</template>
