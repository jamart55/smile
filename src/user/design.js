/**
 * @file design.js
 * @description Disjunctive Syllogism Pilot — SMILE + PANDA
 * Eye-tracking study for children with video stimuli.
 */

import { processQuery, initService } from '@/core/utils/utils'

// Built-in views
import ThanksView from '@/builtins/thanks/ThanksView.vue'
import WithdrawView from '@/builtins/withdraw/WithdrawView.vue'

// Study views
import IntroView from '@/user/components/IntroView.vue'
import SoundcheckView from '@/user/components/SoundcheckView.vue'
import ConsentView from '@/user/components/ConsentView.vue'
import SetupView from '@/user/components/SetupView.vue'
import EnterFullscreenView from '@/user/components/EnterFullscreenView.vue'
import TrialView from '@/user/components/TrialView.vue'
import DebriefIntroView from '@/user/components/DebriefIntroView.vue'
import DebriefDemoView from '@/user/components/DebriefDemoView.vue'
import DebriefTechView from '@/user/components/DebriefTechView.vue'

// PANDA views
import ParentFormView from '@/user/components/panda/ParentFormView.vue'
import UploadVideoView from '@/user/components/panda/UploadVideoView.vue'

// API and Timeline
import useAPI from '@/core/composables/useAPI'
const api = useAPI()

import Timeline from '@/core/timeline/Timeline'
const timeline = new Timeline(api)

// Runtime configuration
api.setRuntimeConfig('allowRepeats', false)
api.setRuntimeConfig('colorMode', 'light')
api.setRuntimeConfig('responsiveUI', true)
api.setRuntimeConfig('windowsizerRequest', { width: 800, height: 600 })
api.setRuntimeConfig('windowsizerAggressive', false)
api.setRuntimeConfig('anonymousMode', false)
api.setRuntimeConfig('labURL', 'https://gureckislab.org')
api.setRuntimeConfig('brandLogoFn', 'universitylogo.png')
api.setRuntimeConfig('maxWrites', 1000)
api.setRuntimeConfig('minWriteInterval', 2000)
api.setRuntimeConfig('autoSave', true)

// ─── Timeline ───────────────────────────────────────────────

// Welcome (anonymous)
timeline.pushSeqView({
  path: '/welcome',
  name: 'welcome_anonymous',
  component: IntroView,
  meta: {
    prev: undefined,
    next: 'soundcheck',
    allowAlways: true,
    requiresConsent: false,
  },
  beforeEnter: () => {
    api.getBrowserFingerprint()
  },
})

// Welcome (referred from recruitment service)
timeline.pushSeqView({
  path: '/welcome/:service',
  name: 'welcome_referred',
  component: IntroView,
  meta: {
    prev: undefined,
    next: 'soundcheck',
    allowAlways: true,
    requiresConsent: false,
  },
  beforeEnter: (to) => {
    if (initService(to.params.service) === false) return false
    processQuery(to.query, to.params.service)
    api.getBrowserFingerprint()
  },
})

// 2. Soundcheck
timeline.pushSeqView({
  name: 'soundcheck',
  component: SoundcheckView,
  meta: { requiresConsent: false },
})

// 3. Consent (Rachel video + after-Rachel + consent slides + signature)
timeline.pushSeqView({
  name: 'consent',
  component: ConsentView,
  meta: {
    requiresConsent: false,
    setConsented: true,
  },
})

// 4. Setup (3 calibration videos)
timeline.pushSeqView({
  name: 'setup',
  component: SetupView,
})

// 5. Enter fullscreen prompt
timeline.pushSeqView({
  name: 'enter_fullscreen',
  component: EnterFullscreenView,
})

// 6. Trials (8 trial+attention-getter pairs in fullscreen)
timeline.pushSeqView({
  name: 'trials',
  component: TrialView,
})

// 7. Debrief intro video (pre-parent)
timeline.pushSeqView({
  name: 'debrief_intro',
  component: DebriefIntroView,
})

// 8. Child demographics
timeline.pushSeqView({
  name: 'debrief_demo',
  component: DebriefDemoView,
})

// 9. Technical questions
timeline.pushSeqView({
  name: 'debrief_tech',
  component: DebriefTechView,
})

// 10. PANDA parent form (privacy consent + signature)
timeline.pushSeqView({
  name: 'parentform',
  component: ParentFormView,
  meta: { setDone: true },
})

// 11. Upload video instructions
timeline.pushSeqView({
  name: 'uploadvideo',
  component: UploadVideoView,
  meta: { resetApp: api.getConfig('allowRepeats') },
})

// 12. Thanks
timeline.pushSeqView({
  name: 'thanks',
  component: ThanksView,
  meta: {
    requiresDone: true,
    resetApp: api.getConfig('allowRepeats'),
  },
})

// Withdraw page
timeline.registerView({
  name: 'withdraw',
  meta: {
    requiresWithdraw: true,
    resetApp: api.getConfig('allowRepeats'),
  },
  component: WithdrawView,
})

timeline.build()

export default timeline
