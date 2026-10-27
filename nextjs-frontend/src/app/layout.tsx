import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono, Instrument_Serif, Inter } from 'next/font/google'
import './globals.css'
import Providers from './providers'
import { GITHUB_URL, SITE_DESCRIPTION, SITE_KEYWORDS, SITE_NAME, SITE_TITLE, SITE_URL } from '@/lib/site'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap', preload: false })
// Public-site typefaces; the app keeps Inter. Only downloaded on pages that use them.
const geist = Geist({ subsets: ['latin'], variable: '--font-geist', display: 'swap', preload: false })
const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-geist-mono', display: 'swap', preload: false })
const serif = Instrument_Serif({ subsets: ['latin'], weight: '400', style: ['normal', 'italic'], variable: '--font-serif', display: 'swap', preload: false })

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { template: '%s | ffinn', default: SITE_TITLE },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  keywords: SITE_KEYWORDS,
  authors: [{ name: 'ffinn contributors', url: GITHUB_URL }],
  creator: 'ffinn contributors',
  publisher: 'ffinn',
  category: 'technology',
  // Canonicals are set per public page; private pages are noindex and get none.
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1, 'max-video-preview': -1 },
  },
  icons: {
    icon: [{ url: '/favicon.ico' }, { url: '/ffinn-icon.svg', type: 'image/svg+xml' }],
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: '/',
    siteName: SITE_NAME,
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
  twitter: {
    card: 'summary_large_image',
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
  other: {
    // Lets GitHub, Slack and others link the repo when the site is shared.
    'github:repo': GITHUB_URL,
  },
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f7f6f2' },
    { media: '(prefers-color-scheme: dark)', color: '#0a0b0d' },
  ],
  colorScheme: 'light dark',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${geist.variable} ${geistMono.variable} ${serif.variable} font-sans antialiased`} suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
