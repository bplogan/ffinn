import type { Metadata } from 'next'

const description =
  'Documentation for ffinn, the free open-source SaaS framework: quick start, multi-tenancy, ' +
  'authentication, billing, AI agents and chat assistants, deployment and contributing.'

export const metadata: Metadata = {
  title: 'Documentation',
  description,
  alternates: { canonical: '/docs' },
  openGraph: { title: 'ffinn Documentation', description, url: '/docs' },
  twitter: { title: 'ffinn Documentation', description },
}

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return children
}
