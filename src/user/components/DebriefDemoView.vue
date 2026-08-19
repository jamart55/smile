<script setup>
import { reactive, computed } from 'vue'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { Input } from '@/uikit/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/uikit/components/ui/select'
import { ConstrainedPage } from '@/uikit/layouts'

const api = useViewAPI()

if (!api.persist.isDefined('debriefDemo')) {
  api.persist.debriefDemo = reactive({
    childDob: '',
    childGender: '',
    childLanguage: '',
    childLanguageOther: '',
    childRace: '',
    childRaceOther: '',
  })
}

const form = api.persist.debriefDemo

const dobRegex = /^\d{2}\/\d{2}\/\d{4}$/
const dobError = computed(() => form.childDob && !dobRegex.test(form.childDob))
const complete = computed(() => form.childDob && dobRegex.test(form.childDob) && form.childGender)

function finish() {
  api.recordPageData(api.persist.debriefDemo)
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
      <div class="border border-border text-left bg-muted p-6 rounded-lg space-y-5 w-full overflow-y-auto max-h-full">
        <!-- DOB -->
        <div>
          <label class="block text-md font-semibold mb-2">
            Child's date of birth (MM/DD/YYYY) <span class="text-red-500">*</span>
          </label>
          <Input v-model="form.childDob" placeholder="MM/DD/YYYY" class="bg-background text-base" />
          <p v-if="dobError" class="text-sm text-red-500 mt-1">Please use MM/DD/YYYY format.</p>
        </div>

        <!-- Sex -->
        <div>
          <label class="block text-md font-semibold mb-2">
            Child's sex assigned at birth <span class="text-red-500">*</span>
          </label>
          <Select v-model="form.childGender">
            <SelectTrigger class="w-full bg-background text-base">
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="male">Male</SelectItem>
              <SelectItem value="female">Female</SelectItem>
              <SelectItem value="prefer-not-to-say">Prefer not to say</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- Language -->
        <div>
          <label class="block text-md font-semibold mb-2">Primary language at home</label>
          <Select v-model="form.childLanguage">
            <SelectTrigger class="w-full bg-background text-base">
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="english">English</SelectItem>
              <SelectItem value="spanish">Spanish</SelectItem>
              <SelectItem value="mandarin">Mandarin</SelectItem>
              <SelectItem value="other">Other</SelectItem>
            </SelectContent>
          </Select>
          <Input
            v-if="form.childLanguage === 'other'"
            v-model="form.childLanguageOther"
            placeholder="Please specify"
            class="mt-2 bg-background text-base"
          />
        </div>

        <!-- Race -->
        <div>
          <label class="block text-md font-semibold mb-2">Child's racial or ethnic identity</label>
          <Select v-model="form.childRace">
            <SelectTrigger class="w-full bg-background text-base">
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="white">White, Caucasian, or European American</SelectItem>
              <SelectItem value="hispanic">Hispanic or Latino/a</SelectItem>
              <SelectItem value="black">Black or African American</SelectItem>
              <SelectItem value="native-american">Native American, American Indian, or Alaska Native</SelectItem>
              <SelectItem value="mena">Middle Eastern or North African</SelectItem>
              <SelectItem value="asian">South, Southeast Asian, East Asian, or Asian American</SelectItem>
              <SelectItem value="pacific-islander">Native Hawaiian or other Pacific Islander</SelectItem>
              <SelectItem value="biracial">Biracial, multiracial, or mixed race</SelectItem>
              <SelectItem value="other">Other</SelectItem>
            </SelectContent>
          </Select>
          <Input
            v-if="form.childRace === 'other'"
            v-model="form.childRaceOther"
            placeholder="Please specify"
            class="mt-2 bg-background text-base"
          />
        </div>

        <hr class="border-border my-4" />
        <div class="flex justify-end">
          <Button variant="default" :disabled="!complete" @click="finish">Submit &amp; Continue</Button>
        </div>
      </div>
    </div>
  </ConstrainedPage>
</template>
