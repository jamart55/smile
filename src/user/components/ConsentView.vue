<script setup>
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
])

const videoReady = ref(false)
const sigVisible = ref(false)

function onVideoEnded() {
  if (api.stepData.id === 'consent-07-vid') {
    sigVisible.value = true
  } else {
    videoReady.value = true
  }
}

function playVideo() {
  if (videoEl.value) videoEl.value.play()
}

function next() {
  videoReady.value = false
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
    <div class="flex flex-col h-full">
      <!-- Video steps -->
      <template v-if="api.stepData.type === 'video'">
        <div class="flex-1 min-h-0 flex items-center justify-center">
          <video
            ref="videoEl"
            :key="api.stepData.id"
            :src="api.getPublicUrl(api.stepData.src)"
            class="max-w-full max-h-full object-contain"
            @ended="onVideoEnded"
            @canplay="playVideo"
            playsinline
          />
        </div>

        <!-- Signature appears below consent-07-vid when it ends -->
        <div v-if="sigVisible" class="flex-shrink-0 px-4 pb-3">
          <p class="text-sm text-muted-foreground mb-2">Please sign below, then click "Sign &amp; Continue".</p>
          <div class="border border-border rounded-md bg-white p-1 w-full">
            <VueSignaturePad
              ref="signaturePad"
              width="100%"
              height="160px"
              :options="{ penColor: '#000' }"
            />
          </div>
          <div class="flex gap-2 mt-2">
            <Button variant="outline" size="sm" @click="clearSignature">Clear</Button>
            <Button variant="default" size="sm" @click="saveSignature">Sign &amp; Continue</Button>
            <span v-if="signatureSaved" class="text-xs text-green-600 self-center ml-2">Signature saved</span>
          </div>
        </div>

        <div v-else class="flex justify-center py-3 flex-shrink-0" style="min-height: 52px;">
          <Button v-if="videoReady" variant="default" size="lg" @click="next">Continue</Button>
        </div>
      </template>

      <!-- Image steps -->
      <template v-if="api.stepData.type === 'image'">
        <div class="flex-1 min-h-0 flex items-center justify-center">
          <img
            :key="api.stepData.id"
            :src="api.getPublicUrl(api.stepData.src)"
            alt="Consent"
            class="max-w-full max-h-full object-contain"
          />
        </div>
        <div class="flex justify-center py-3 flex-shrink-0">
          <Button variant="default" size="lg" @click="next">Continue</Button>
        </div>
      </template>
    </div>
  </ConstrainedTaskWindow>
</template>
