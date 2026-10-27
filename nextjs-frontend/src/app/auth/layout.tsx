import type { Metadata } from 'next'
import AuthShell from './AuthShell'

// Sign-in and account screens carry no content worth indexing.
export const metadata: Metadata = {
  title: 'Sign in',
  robots: { index: false, follow: false },
}

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <AuthShell>{children}</AuthShell>
}
