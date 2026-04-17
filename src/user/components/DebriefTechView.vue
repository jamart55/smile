<script setup>
/**
 * DebriefTechView — Technical questions about the study setup.
 * Device type, screen distance, seating arrangement.
 */
import { reactive, computed } from 'vue'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { Input } from '@/uikit/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/uikit/components/ui/select'
import { ConstrainedPage, TitleTwoCol } from '@/uikit/layouts'

const api = useViewAPI()

if (!api.persist.isDefined('debriefTech')) {
  api.persist.debriefTech = reactive({
    device: '',
    deviceOther: '',
    screenDistance: '',
    seatingArrangement: '',
    seatingOther: '',
  })
}

const form = api.persist.debriefTech

const complete = computed(() => form.device && form.screenDistance && form.seatingArrangement)

function finish() {
  api.recordPageData(api.persist.debriefTech)
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
    <TitleTwoCol leftFirst leftWidth="w-1/3" :responsiveUI="api.config.responsiveUI">
      <template #title>
        <h3 class="text-3xl font-bold mb-4">Technical Details</h3>
        <p class="text-lg mb-8">A few questions about your setup during the study.</p>
      </template>

      <template #left>
        <div class="text-left text-muted-foreground">
          <p class="text-md font-light">
            This helps us understand the viewing conditions during the study.
          </p>
        </div>
      </template>

      <template #right>
        <div class="border border-border text-left bg-muted p-6 rounded-lg space-y-5">
          <!-- Device -->
          <div>
            <label class="block text-md font-semibold mb-2">
              What type of device did you use? <span class="text-red-500">*</span>
            </label>
            <Select v-model="form.device">
              <SelectTrigger class="w-full bg-background text-base">
                <SelectValue placeholder="Select" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="laptop">Laptop</SelectItem>
                <SelectItem value="desktop">Desktop computer</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
            <Input
              v-if="form.device === 'other'"
              v-model="form.deviceOther"
              placeholder="Please specify"
              class="mt-2 bg-background text-base"
            />
          </div>

          <!-- Screen distance -->
          <div>
            <label class="block text-md font-semibold mb-2">
              How far was your child from the screen? <span class="text-red-500">*</span>
            </label>
            <Select v-model="form.screenDistance">
              <SelectTrigger class="w-full bg-background text-base">
                <SelectValue placeholder="Select" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="less-than-1ft">Less than one foot</SelectItem>
                <SelectItem value="1-to-2ft">One to two feet</SelectItem>
                <SelectItem value="over-2ft">Over two feet</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <!-- Seating -->
          <div>
            <label class="block text-md font-semibold mb-2">
              What seating arrangement was used? <span class="text-red-500">*</span>
            </label>
            <Select v-model="form.seatingArrangement">
              <SelectTrigger class="w-full bg-background text-base">
                <SelectValue placeholder="Select" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="highchair">Highchair</SelectItem>
                <SelectItem value="parents-lap">Sitting on a parent's lap</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
            <Input
              v-if="form.seatingArrangement === 'other'"
              v-model="form.seatingOther"
              placeholder="Please specify"
              class="mt-2 bg-background text-base"
            />
          </div>

          <hr class="border-border my-4" />
          <div class="flex justify-end">
            <Button variant="default" :disabled="!complete" @click="finish">Submit &amp; Continue</Button>
          </div>
        </div>
      </template>
    </TitleTwoCol>
  </ConstrainedPage>
</template>
