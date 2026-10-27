/**
 * Plan selection, on the same chrome as the auth screens but full width.
 */
import type { Metadata } from 'next'
import AuthShell from '../auth/AuthShell'

export const metadata: Metadata = {
  title: 'Choose a plan',
  robots: { index: false, follow: false },
}

export default function SelectPlanLayout({ children }: { children: React.ReactNode }) {
  return <AuthShell wide>{children}</AuthShell>
}
