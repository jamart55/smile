/**
 * @file design.js
 * @description Fullscreen test — welcome → fullscreen test → thanks
 */

import { processQuery, initService } from '@/core/utils/utils'

import ThanksView from '@/builtins/thanks/ThanksView.vue'
import WithdrawView from '@/builtins/withdraw/WithdrawView.vue'
import IntroView from '@/user/components/IntroView.vue'
import FullscreenTestView from '@/user/components/FullscreenTestView.vue'

import useAPI from '@/core/composables/useAPI'
const api = useAPI()

import Timeline from '@/core/timeline/Timeline'
const timeline = new Timeline(api)

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

timeline.pushSeqView({
  path: '/welcome',
  name: 'welcome_anonymous',
  component: IntroView,
  meta: {
    prev: undefined,
    next: 'fullscreen_test',
    allowAlways: true,
    requiresConsent: false,
  },
  beforeEnter: () => {
    api.getBrowserFingerprint()
  },
})

timeline.pushSeqView({
  path: '/welcome/:service',
  name: 'welcome_referred',
  component: IntroView,
  meta: {
    prev: undefined,
    next: 'fullscreen_test',
    allowAlways: true,
    requiresConsent: false,
  },
  beforeEnter: (to) => {
    if (initService(to.params.service) === false) return false
    processQuery(to.query, to.params.service)
    api.getBrowserFingerprint()
  },
})

timeline.pushSeqView({
  name: 'fullscreen_test',
  component: FullscreenTestView,
  meta: {
    requiresConsent: false,
    setDone: true,
  },
})

timeline.pushSeqView({
  name: 'thanks',
  component: ThanksView,
  meta: {
    requiresDone: true,
    resetApp: api.getConfig('allowRepeats'),
  },
})

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
