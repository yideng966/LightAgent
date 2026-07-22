import { create } from 'zustand'

// Onboarding is config-driven: the wizard auto-opens whenever the chat model
// isn't configured yet, and stops appearing once it is — no persisted "seen"
// flag that could strand a user who skipped without finishing setup.
//
// `dismissedThisSession` is an in-memory guard so that skipping doesn't
// immediately re-open the wizard within the same run; it resets on relaunch,
// so an unconfigured app will guide the user again next time.

interface OnboardingState {
  // Whether the wizard overlay is currently visible.
  open: boolean
  // True if the user skipped/finished during THIS app session (not persisted).
  dismissedThisSession: boolean
  // Decide whether to auto-open on launch. Opens only when chat isn't
  // configured AND it wasn't dismissed earlier this session.
  maybeOpen: (chatConfigured: boolean) => void
  // Open manually (e.g. from a "setup guide" entry point later).
  openWizard: () => void
  // Finish/skip: close and don't auto-reopen this session.
  finish: () => void
  // Close without marking dismissed (rarely used; kept for symmetry).
  close: () => void
}

export const useOnboardingStore = create<OnboardingState>((set) => ({
  open: false,
  dismissedThisSession: false,

  maybeOpen: (chatConfigured) =>
    set((s) => {
      if (chatConfigured || s.dismissedThisSession) return { open: false }
      return { open: true }
    }),

  openWizard: () => set({ open: true }),

  finish: () => set({ open: false, dismissedThisSession: true }),

  close: () => set({ open: false }),
}))
