import type { Metadata } from 'next'
import AppShell from './AppShell'

// The signed-in portal is private; keep it out of search results.
export const metadata: Metadata = {
  title: 'Portal',
  robots: { index: false, follow: false },
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>
}
