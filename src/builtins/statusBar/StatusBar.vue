<script setup>
import { ref } from 'vue'
import useSmileStore from '@/core/stores/smilestore'
import appconfig from '@/core/config'
import useAPI from '@/core/composables/useAPI'
import { Button } from '@/uikit/components/ui/button'

const smilestore = useSmileStore()
const api = useAPI()

const showreportissuemodal = ref(false)
function toggleReport() {
  showreportissuemodal.value = !showreportissuemodal.value
}
</script>

<template>
  <!-- Main navigation bar with study info and action buttons -->
  <div class="flex flex-row items-stretch relative px-5" role="navigation" aria-label="main navigation">
    <!-- Left section: Brand logo and study information -->
    <div class="flex items-stretch flex-shrink-0 min-h-[3.25rem]">
      <a class="flex items-center pt-3" :href="appconfig.labURL" target="_new" v-if="!appconfig.anonymousMode">
        <img :src="api.getStaticUrl(appconfig.brandLogoFn)" width="90" class="dark-aware-img" />
      </a>
      <div class="flex items-center pt-1">
        <p class="text-xs text-left pl-2.5 text-muted-foreground pt-2 @[600px]:block hidden font-mono">
          Study: {{ smilestore.config.codeName }}<br />Version: {{ smilestore.config.github.lastCommitHash
          }}{{
            appconfig.mode === 'testing' || appconfig.mode === 'development' || appconfig.mode === 'presentation'
              ? '-' + appconfig.mode
              : ''
          }}<br />
          <template v-if="smilestore.getShortId != 'N/A'"> User ID: {{ smilestore.getShortId }} </template>
        </p>
      </div>
    </div>

    <!-- Right section: Action buttons -->
    <div id="infobar" class="flex-grow flex-shrink-0 flex items-stretch z-10">
      <div class="flex justify-end ml-auto items-stretch">
        <div class="flex items-center pt-1" v-if="!appconfig.anonymousMode">
          <div class="flex gap-2">
            <Button variant="warning-light" size="xs" @click="toggleReport()" v-if="false">
              <i-fa6-solid-hand />
              Report issue
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>

</template>
