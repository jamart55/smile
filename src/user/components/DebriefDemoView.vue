<script setup>
/**
 * DebriefDemoView — Child demographics form.
 * Collects: DOB, gender, language, race, how-found, comments.
 */
import { reactive, computed } from 'vue'
import useViewAPI from '@/core/composables/useViewAPI'
import { Button } from '@/uikit/components/ui/button'
import { Input } from '@/uikit/components/ui/input'
import { Textarea } from '@/uikit/components/ui/textarea'
import { Checkbox } from '@/uikit/components/ui/checkbox'
import { Label } from '@/uikit/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/uikit/components/ui/select'
import { ConstrainedPage, TitleTwoCol } from '@/uikit/layouts'

const api = useViewAPI()

if (!api.persist.isDefined('debriefDemo')) {
  api.persist.debriefDemo = reactive({
    childDob: '',
    childGender: '',
    childGenderOther: '',
    childLanguage: '',
    childLanguageOther: '',
    childRace: '',
    childRaceOther: '',
    howFound: {
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
    howFoundOther: '',
    comments: '',
  })
}

const form = api.persist.debriefDemo

const complete = computed(() => form.childDob && form.childGender)

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
    <TitleTwoCol leftFirst leftWidth="w-1/3" :responsiveUI="api.config.responsiveUI">
      <template #title>
        <h3 class="text-3xl font-bold mb-4">About Your Child</h3>
        <p class="text-lg mb-8">Please answer a few questions about your child.</p>
      </template>

      <template #left>
        <div class="text-left text-muted-foreground">
          <p class="text-md font-light">
            This information helps us better understand our participants and is kept confidential.
          </p>
        </div>
      </template>

      <template #right>
        <div class="border border-border text-left bg-muted p-6 rounded-lg space-y-5">
          <!-- DOB -->
          <div>
            <label class="block text-md font-semibold mb-2">
              Child's date of birth (MM/DD/YYYY) <span class="text-red-500">*</span>
            </label>
            <Input v-model="form.childDob" placeholder="MM/DD/YYYY" class="bg-background text-base" />
          </div>

          <!-- Gender -->
          <div>
            <label class="block text-md font-semibold mb-2">
              Child's gender identity <span class="text-red-500">*</span>
            </label>
            <Select v-model="form.childGender">
              <SelectTrigger class="w-full bg-background text-base">
                <SelectValue placeholder="Select" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="male">Male</SelectItem>
                <SelectItem value="female">Female</SelectItem>
                <SelectItem value="prefer-not-to-say">Prefer not to say</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
            <Input
              v-if="form.childGender === 'other'"
              v-model="form.childGenderOther"
              placeholder="Please specify"
              class="mt-2 bg-background text-base"
            />
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

          <!-- How found us -->
          <div>
            <label class="block text-md font-semibold mb-2">How did you find us? (check all that apply)</label>
            <div class="space-y-2">
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.facebookAd" id="fbad" /><Label for="fbad">Facebook Ad</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.facebookPost" id="fbpost" /><Label for="fbpost">Facebook Post</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.twitter" id="tw" /><Label for="tw">Twitter</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.instagram" id="ig" /><Label for="ig">Instagram</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.podcastAd" id="pod" /><Label for="pod">Podcast Ad</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.reddit" id="red" /><Label for="red">Reddit</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.parentingForum" id="pf" /><Label for="pf">Other parenting forum</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.kidconcepts" id="kc" /><Label for="kc">www.kidconcepts.org</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.directEmail" id="de" /><Label for="de">Direct email or personal contact</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.childrensMuseum" id="cm" /><Label for="cm">Children's Museum of Manhattan</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.googleAd" id="ga" /><Label for="ga">Google Ad</Label></div>
              <div class="flex items-center gap-2"><Checkbox v-model:checked="form.howFound.other" id="oth" /><Label for="oth">Other</Label></div>
              <Input
                v-if="form.howFound.other"
                v-model="form.howFoundOther"
                placeholder="Please specify"
                class="bg-background text-base"
              />
            </div>
          </div>

          <!-- Comments -->
          <div>
            <label class="block text-md font-semibold mb-2">Questions or comments</label>
            <Textarea
              v-model="form.comments"
              placeholder="Optional"
              class="w-full bg-background text-base resize-vertical"
              rows="3"
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
