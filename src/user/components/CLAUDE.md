# DS pilot — study view conventions

Study-specific guidance for views under `smile/src/user/`. Framework API reference is in `smile/src/user/CLAUDE.md` (upstream SMILE docs).

## Layout components (`@/uikit/layouts`)

| Layout | Use when |
|---|---|
| `ConstrainedTaskWindow` | Video/image/task content that should fill the fixed study frame (800×600). Use `variant="ghost"` for light gray card, `"game"` for green, `"outline"` for bordered. |
| `ConstrainedPage` | Form-heavy views (surveys, debriefs). Same fixed frame, less decorative. |
| `TitleTwoCol` | Two-column layouts with an optional title slot. Avoid in this study — removed from all debrief/form views in favor of centered full-width forms. |

All views pass `:responsiveUI="api.config.responsiveUI"`, `:width="api.config.windowsizerRequest.width"`, `:height="api.config.windowsizerRequest.height"` to their layout component. Do not hardcode dimensions.

`variant="ghost"` applies `bg-muted px-8 py-5`. The padding is what makes the light-gray card visible against PANDA's white background — do not remove it.

These layouts do **not** use `min-h-screen`. The app runs inside a PANDA iframe; `min-h-screen` references the browser viewport rather than PANDA's card and causes layout issues.

For views with media + optional Continue button, use this pattern so media maximally fills the frame:

```html
<div class="flex flex-col h-full w-full">
  <div class="flex-1 min-h-0 flex items-center justify-center">
    <video class="max-w-full max-h-full object-contain" ... />
  </div>
  <div class="flex justify-center py-3 flex-shrink-0">
    <Button v-if="ready">Continue</Button>
  </div>
</div>
```

`w-full` on the outer div is required. `ConstrainedTaskWindow` uses `items-center` on the gray box, which shrinks children to content width without it — the inner `flex items-center justify-center` then has no room to center the video.

After `api.goNextStep()` in a video view, always use `nextTick(() => videoEl.value.play())` — the new step's `<video>` ref isn't mounted until after the tick.

## Autofill for dev testing

Every form view should implement `api.setAutofill(fn)` so the dev-mode autofill button populates fields. This is the fastest way to test form flows without manually entering data.

## Study view summary

| View | File | Notes |
|---|---|---|
| welcome | `design.js` (uses IntroView) | Entry point; runs fingerprint/service init |
| soundcheck | `SoundcheckView.vue` | Auto-plays audio; emojis grayed until sound ends |
| consent | `ConsentView.vue` | Videos → consent slides → consent-07-vid ends → signature appears inline below video |
| setup | `SetupView.vue` | 2 calibration videos; last video shows Continue button |
| enter_fullscreen | `EnterFullscreenView.vue` | Records `recording_start_ts` + screen dims to Firestore |
| trials | `TrialView.vue` | 8 trial+attention-getter pairs in fullscreen |
| debrief_intro | `DebriefIntroView.vue` | Brief video before parent questionnaires |
| debrief_demo | `DebriefDemoView.vue` | Child DOB (MM/DD/YYYY validated), gender, language, race |
| debrief_tech | `DebriefTechView.vue` | Device, screen distance, seating |
| parentform | `ParentFormView.vue` | Video privacy consent + signature + how-found (12 options) |
| uploadvideo | `panda/UploadVideoView.vue` | Autoplay instructions video, auto-advances on end |

`api.goToView('name')` jumps directly and bypasses the router's sequential-access guards; `api.goNextView()` / `api.goPrevView()` respect timeline order.
