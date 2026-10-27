/**
 * Plain-language help for the AI code generation flow (non-technical users).
 */

export type GenerationGuide = {
  title: string
  summary: string
  steps: string[]
}

export type ActionHelp = {
  title: string
  body: string
  whenToUse: string
}

const AUTOMATED_STEPS = [
  'You do not need to do anything right now.',
  'This page updates automatically — you can leave and come back.',
  'We will email nothing; check back here or watch the progress steps below.',
]

export function getGenerationGuide(status: string): GenerationGuide {
  switch (status) {
    case 'Queued':
    case 'Draft':
      return {
        title: 'Waiting to start',
        summary: 'Your request is in line. The AI will begin shortly.',
        steps: AUTOMATED_STEPS,
      }
    case 'Analyzing':
    case 'Generating':
      return {
        title: 'Writing your feature',
        summary: 'The AI is turning your description into working code. This usually takes a few minutes.',
        steps: AUTOMATED_STEPS,
      }
    case 'Validating':
    case 'AutoFixing':
      return {
        title: 'Quality check in progress',
        summary: 'We are checking the generated code for common issues and fixing them when possible.',
        steps: AUTOMATED_STEPS,
      }
    case 'Committing':
    case 'CreatingPr':
      return {
        title: 'Saving to GitHub',
        summary: 'Your new code is being saved to the repository and a pull request is being opened for review.',
        steps: [
          ...AUTOMATED_STEPS,
          'You do not need to open GitHub unless you want to — links will appear here when ready.',
        ],
      }
    case 'Building':
      return {
        title: 'Deploying to staging',
        summary: 'Automated tests are running and a safe preview environment is being prepared for you.',
        steps: AUTOMATED_STEPS,
      }
    case 'Staging':
    case 'Ready':
      return {
        title: 'Your turn — review in staging',
        summary:
          'The preview app is live in staging. This is where you check that everything works before real users see it.',
        steps: [
          'Click **Open staging app** and sign in if prompted (use the staging demo tenant if shown).',
          'Click through the screens related to your feature and confirm it behaves as expected.',
          'If it looks good, click **Release to production**.',
          'If something is wrong, click **Revert** to remove this feature from staging and close the change.',
        ],
      }
    case 'Releasing':
      return {
        title: 'Going live',
        summary: 'Your feature is being released to production. This may take several minutes.',
        steps: [
          'Please wait — do not start another release for the same feature.',
          'When finished, the status will change to **In production**.',
        ],
      }
    case 'Released':
      return {
        title: 'Live in production',
        summary: 'Your feature is now available to all users in the live app.',
        steps: [
          'Open your production site and spot-check the feature one more time.',
          'If you need to undo a production release, use **Revert release** (creates a rollback change).',
        ],
      }
    case 'Failed':
      return {
        title: 'Something went wrong',
        summary: 'The run stopped before completion. The error message above explains what happened.',
        steps: [
          'Read the red error note for a plain summary.',
          'Click **Try again** to rerun with the same description, or edit your request and submit a new one.',
        ],
      }
    case 'Cancelled':
      return {
        title: 'Cancelled',
        summary: 'This generation was marked cancelled in ffinn. GitHub or staging may still have leftover changes.',
        steps: ['Start a new request if you still need this feature.', 'Use **Revert** on an older run if code was already saved.'],
      }
    case 'Reverted':
      return {
        title: 'Reverted',
        summary: 'This feature was rolled back — the pull request was closed and staging was restored.',
        steps: ['Start a new request when you are ready to try again with a different description.'],
      }
    default:
      return {
        title: 'Working on your request',
        summary: 'Your code generation is in progress.',
        steps: AUTOMATED_STEPS,
      }
  }
}

export const GENERATION_PAGE_HELP = {
  title: 'How code generation works',
  body: [
    'Describe what you want in everyday language.',
    'We write the code, run checks, and deploy a **staging preview** you can test safely.',
    'You review in staging, then **release to production** when you are happy.',
  ],
}

export const PIPELINE_HELP = {
  title: 'Progress steps',
  body: [
    'These steps show where your request is in the pipeline.',
    'Green steps are finished. The highlighted step is happening now (or waiting on you).',
    'Review happens in **Review in staging** — not after production.',
  ],
}

export const ACTION_HELP: Record<string, ActionHelp> = {
  release: {
    title: 'Release to production',
    body: 'Merges your changes and deploys them to the live app that real users see.',
    whenToUse: 'Use this after you have tested in staging and everything looks correct.',
  },
  staging: {
    title: 'Deploy staging preview',
    body: 'Builds a temporary copy of the app with your new feature so you can test safely.',
    whenToUse: 'Use this if staging was not deployed automatically and you need a preview link.',
  },
  revert: {
    title: 'Revert',
    body: 'Closes the pull request, removes the feature branch, and restores staging to how it was before this change.',
    whenToUse: 'Use this when staging review shows the feature is not ready or not wanted.',
  },
  revertReleased: {
    title: 'Revert release',
    body: 'Starts a rollback of a production release (via a revert pull request).',
    whenToUse: 'Use this only after release if the live app needs to be undone.',
  },
  cancel: {
    title: 'Cancel',
    body: 'Marks this generation as cancelled in ffinn only. It does not remove code from GitHub or staging.',
    whenToUse: 'Use while work is still running if you want to stop waiting. Prefer **Revert** after staging is deployed.',
  },
  retry: {
    title: 'Try again',
    body: 'Starts a new run using the same description after a failure.',
    whenToUse: 'Use when something failed and you want another attempt without retyping everything.',
  },
  stagingApp: {
    title: 'Open staging app',
    body: 'A safe preview of your app with the new feature. Nothing here affects real users.',
    whenToUse: 'Use this during **Review in staging** to click through and verify your feature.',
  },
  pullRequest: {
    title: 'Pull request',
    body: 'A package of code changes on GitHub. Technical reviewers can comment here; you can ignore it if you only use staging.',
    whenToUse: 'Optional — most non-technical reviewers use the staging app instead.',
  },
}

export const FORM_FIELD_HELP = {
  agent: {
    title: 'Agent',
    body: 'Which AI setup to use (which repo and rules apply). Your admin usually configures one for you.',
  },
  audience: {
    title: 'Who is this for?',
    body: 'Tenant = your customer-facing app menus. Host = platform admin screens (like the default admin).',
  },
  featureName: {
    title: 'Feature name',
    body: 'A short label for this change — used in GitHub and staging so you can find it later.',
  },
  prompt: {
    title: 'What should we build?',
    body: 'Describe the feature like you would to a colleague: who uses it, what screens you need, and any important rules.',
  },
}
