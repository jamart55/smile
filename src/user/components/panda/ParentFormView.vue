<script setup>
import { reactive, computed, ref } from 'vue'

import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { Checkbox } from '@/uikit/components/ui/checkbox'
import { Label } from '@/uikit/components/ui/label'
import { Input } from '@/uikit/components/ui/input'
import { Textarea } from '@/uikit/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/uikit/components/ui/select'
import { ConstrainedPage } from '@/uikit/layouts'
import { VueSignaturePad } from 'vue-signature-pad'

const api = useViewAPI()

if (!api.persist.isDefined('parentForm')) {
  api.persist.parentForm = reactive({
    videoConsent: '',
    signature: null,
    howFoundUs: {
      facebookAd: false,
      facebookPost: false,
      twitter: false,
      instagram: false,
      podcastAd: false,
      reddit: false,
      parentingForum: false,
      kidconcepts: false,
      directEmail: false,
      childrensMuseum: false,
      googleAd: false,
      other: false,
    },
    howFoundUsOther: '',
    comments: '',
  })
}

const signaturePad = ref(null)
const showValidationError = ref(false)

const complete = computed(() => {
  return api.persist.parentForm.videoConsent !== '' && api.persist.parentForm.signature !== null
})

function clearSignature() {
  if (signaturePad.value) {
    signaturePad.value.clearSignature()
    api.persist.parentForm.signature = null
  }
}

function saveSignature() {
  if (signaturePad.value) {
    const { isEmpty, data } = signaturePad.value.saveSignature()
    if (!isEmpty) {
      api.persist.parentForm.signature = data
    }
  }
}

function autofill() {
  api.persist.parentForm.videoConsent = 'panda'
  api.persist.parentForm.signature = 'data:image/png;base64,AUTOFILL'
  api.persist.parentForm.howFoundUs.facebookAd = true
  api.persist.parentForm.comments = 'Test comment'
}

api.setAutofill(autofill)

function finish() {
  if (!complete.value) {
    showValidationError.value = true
    return
  }
  api.recordPageData(api.persist.parentForm)
  api.saveData(true)
  api.goNextView()
}
</script>

<template>
  <ConstrainedPage
    :responsiveUI="api.config.responsiveUI"
    :width="api.config.windowsizerRequest.width"
    :height="api.config.windowsizerRequest.height"
  >
    <div class="flex items-center justify-center h-full p-3">
      <div class="border border-border text-left bg-muted p-6 rounded-lg w-full overflow-y-auto max-h-full">
        <!-- Video Privacy Consent -->
        <div class="mb-6">
          <label class="block text-md font-semibold text-foreground mb-3">Video Privacy Consent</label>
          <p class="text-sm text-muted-foreground mb-3">
            How would you like your child's video recording to be used?
          </p>
          <Select v-model="api.persist.parentForm.videoConsent">
            <SelectTrigger class="w-full bg-background text-base">
              <SelectValue placeholder="Select a privacy option" />
            </SelectTrigger>
            <SelectContent class="w-[var(--reka-select-trigger-width)] max-w-[var(--reka-select-trigger-width)]">
              <SelectItem value="panda" class="whitespace-normal">
                I prefer for my video to remain accessible only to PANDA researchers and never shared with other researchers.
              </SelectItem>
              <SelectItem value="public" class="whitespace-normal">
                I give permission to show video excerpts and images from recordings of this session for scientific presentations and informational/educational purposes, but never for commercial purposes.
              </SelectItem>
            </SelectContent>
          </Select>
          <p v-if="showValidationError && !api.persist.parentForm.videoConsent" class="text-xs text-red-500 mt-1">
            Please select a privacy option.
          </p>
        </div>

        <!-- Digital Signature -->
        <div class="mb-6">
          <label class="block text-md font-semibold text-foreground mb-3">
            Digital Signature <span class="text-red-500">*</span>
          </label>
          <p class="text-sm text-muted-foreground mb-3">Please sign in the box below, then click "Save Signature" to confirm.</p>
          <div class="border border-border rounded-md bg-background p-1">
            <VueSignaturePad ref="signaturePad" width="100%" height="90px" :options="{ penColor: '#000' }" />
          </div>
          <div class="flex gap-2 mt-2">
            <Button variant="outline" size="sm" @click="clearSignature">Clear</Button>
            <Button variant="outline" size="sm" @click="saveSignature">Save Signature</Button>
          </div>
          <p v-if="api.persist.parentForm.signature" class="text-xs text-green-600 mt-1">Signature saved</p>
          <p v-else-if="showValidationError" class="text-xs text-red-500 mt-1">
            Please sign above and click "Save Signature" before continuing.
          </p>
        </div>

        <!-- How Did You Find Us -->
        <div class="mb-6">
          <label class="block text-md font-semibold text-foreground mb-3">
            How did you find out about this study?
            <span class="font-normal text-muted-foreground">(check all that apply)</span>
          </label>
          <div class="grid grid-cols-2 gap-x-6 gap-y-2">
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.facebookAd" id="pfFbAd" /><Label for="pfFbAd">Facebook Ad</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.facebookPost" id="pfFbPost" /><Label for="pfFbPost">Facebook Post</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.twitter" id="pfTw" /><Label for="pfTw">Twitter</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.instagram" id="pfIg" /><Label for="pfIg">Instagram</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.podcastAd" id="pfPod" /><Label for="pfPod">Podcast Ad</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.reddit" id="pfRed" /><Label for="pfRed">Reddit</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.parentingForum" id="pfPf" /><Label for="pfPf">Other parenting forum</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.kidconcepts" id="pfKc" /><Label for="pfKc">www.kidconcepts.org</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.directEmail" id="pfDe" /><Label for="pfDe">Direct email or personal contact</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.childrensMuseum" id="pfCm" /><Label for="pfCm">Children's Museum of Manhattan</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.googleAd" id="pfGa" /><Label for="pfGa">Google Ad</Label></div>
            <div class="flex items-center gap-2"><Checkbox v-model:checked="api.persist.parentForm.howFoundUs.other" id="pfOth" /><Label for="pfOth">Other</Label></div>
            <Input
              v-if="api.persist.parentForm.howFoundUs.other"
              v-model="api.persist.parentForm.howFoundUsOther"
              placeholder="Please specify"
              class="bg-background text-base"
            />
          </div>
        </div>

        <!-- Comments -->
        <div class="mb-6">
          <label class="block text-md font-semibold text-foreground mb-2">
            Any additional comments?
            <span class="font-normal text-muted-foreground">(optional)</span>
          </label>
          <Textarea
            v-model="api.persist.parentForm.comments"
            placeholder="Please share any thoughts or feedback"
            class="w-full bg-background text-base resize-vertical"
            rows="4"
          />
        </div>

        <hr class="border-border my-6" />
        <div class="flex justify-end">
          <Button variant="default" @click="finish()">Submit and Continue</Button>
        </div>
      </div>
    </div>
  </ConstrainedPage>
</template>
