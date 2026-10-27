import type { Metadata } from 'next'

const description =
  'See how ffinn works: describe a feature in plain English and the AI build agent writes the code, ' +
  'opens a pull request, deploys to staging and ships to production — on a free, open-source SaaS foundation.'

export const metadata: Metadata = {
  title: 'How It Works',
  description,
  alternates: { canonical: '/how-it-works' },
  openGraph: { title: 'How ffinn works', description, url: '/how-it-works' },
  twitter: { title: 'How ffinn works', description },
}

export default function HowItWorksLayout({ children }: { children: React.ReactNode }) {
  return children
}
