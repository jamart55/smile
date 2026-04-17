<script setup>
/**
 * ConsentView — Multi-step consent flow:
 * 1. Rachel intro video
 * 2. After-Rachel video
 * 3. Consent slides 001-006 (images)
 * 4. Consent slide 007 video (signature explanation)
 * 5. Signature capture
 */
import { ref, nextTick, computed } from 'vue'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { ConstrainedTaskWindow } from '@/uikit/layouts'
import { VueSignaturePad } from 'vue-signature-pad'

const api = useViewAPI()

const videoEl = ref(null)
const signaturePad = ref(null)

api.steps.append([
  { id: 'rachel-vid', type: 'video', src: 'videos/intro/rachel-vid.mp4' },
  { id: 'after-rachel', type: 'video', src: 'videos/intro/after-rachel.mp4' },
  { id: 'consent-01', type: 'image', src: 'images/consent/pilot-slides.001.jpeg' },
  { id: 'consent-02', type: 'image', src: 'images/consent/pilot-slides.002.jpeg' },
  { id: 'consent-03', type: 'image', src: 'images/consent/pilot-slides.003.jpeg' },
  { id: 'consent-04', type: 'image', src: 'images/consent/pilot-slides.004.jpeg' },
  { id: 'consent-05', type: 'image', src: 'images/consent/pilot-slides.005.jpeg' },
  { id: 'consent-06', type: 'image', src: 'images/consent/pilot-slides.006.jpeg' },
  { id: 'consent-07-vid', type: 'video', src: 'videos/intro/consent-sig-vid.mp4' },
  { id: 'signature', type: 'signature' },
])

const videoReady = ref(false)

function onVideoEnded() {
  videoReady.value = true
}

function playVideo() {
  if (videoEl.value) {
    videoEl.value.play()
  }
}

function next() {
  videoReady.value = false
  if (api.stepData.id === 'signature') {
    // Save signature and finish
    saveSignature()
    return
  }
  if (api.isLastStep()) {
    api.goNextView()
  } else {
    api.goNextStep()
    nextTick(() => {
      if (api.stepData.type === 'video' && videoEl.value) {
        videoEl.value.play()
      }
    })
  }
}

if (!api.persist.isDefined('consentSignature')) {
  api.persist.consentSignature = null
}

const signatureSaved = computed(() => api.persist.consentSignature !== null)

function clearSignature() {
  if (signaturePad.value) {
    signaturePad.value.clearSignature()
    api.persist.consentSignature = null
  }
}

function saveSignature() {
  if (signaturePad.value) {
    const { isEmpty, data } = signaturePad.value.saveSignature()
    if (!isEmpty) {
      api.persist.consentSignature = data
      api.recordPageData({ consentSignature: data })
      api.saveData(true)
      api.goNextView()
    }
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
      <!-- Video steps -->
      <template v-if="api.stepData.type === 'video'">
        <video
          ref="videoEl"
          :key="api.stepData.id"
          :src="api.getPublicUrl(api.stepData.src)"
          class="max-w-full max-h-[75%] object-contain rounded"
          @ended="onVideoEnded"
          @canplay="playVideo"
          playsinline
        />
        <Button
          v-if="videoReady"
          variant="default"
          size="lg"
          class="mt-4"
          @click="next"
        >
          Continue
        </Button>
      </template>

      <!-- Image steps -->
      <template v-if="api.stepData.type === 'image'">
        <img
          :key="api.stepData.id"
          :src="api.getPublicUrl(api.stepData.src)"
          alt="Consent"
          class="max-w-full max-h-[80%] object-contain mb-4"
        />
        <Button variant="default" size="lg" @click="next">Continue</Button>
      </template>

      <!-- Signature step -->
      <template v-if="api.stepData.type === 'signature'">
        <h2 class="text-2xl font-bold mb-4">Please sign below to consent</h2>
        <div class="border border-border rounded-md bg-white p-1 w-full max-w-lg">
          <VueSignaturePad
            ref="signaturePad"
            width="100%"
            height="200px"
            :options="{ penColor: '#000' }"
          />
        </div>
        <div class="flex gap-2 mt-3">
          <Button variant="outline" size="sm" @click="clearSignature">Clear</Button>
          <Button variant="default" size="sm" @click="saveSignature">
            Sign &amp; Continue
          </Button>
        </div>
        <p v-if="signatureSaved" class="text-xs text-green-600 mt-1">Signature saved</p>
      </template>
    </div>
  </ConstrainedTaskWindow>
</template>
