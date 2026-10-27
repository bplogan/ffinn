import type { Metadata } from 'next'
import HomePage from '@/components/marketing/HomePage'
import { FAQ } from '@/components/marketing/content'
import { GITHUB_URL, SITE_DESCRIPTION, SITE_NAME, SITE_TITLE, SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: { absolute: SITE_TITLE },
  alternates: { canonical: '/' },
}

/** Structured data so search engines can show ffinn as free, open-source software. */
const jsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'WebSite',
      '@id': `${SITE_URL}/#website`,
      url: SITE_URL,
      name: SITE_NAME,
      description: SITE_DESCRIPTION,
      inLanguage: 'en',
    },
    {
      '@type': 'Organization',
      '@id': `${SITE_URL}/#organization`,
      name: SITE_NAME,
      url: SITE_URL,
      logo: `${SITE_URL}/ffinn-logo.png`,
      sameAs: [GITHUB_URL],
    },
    {
      '@type': 'SoftwareApplication',
      '@id': `${SITE_URL}/#software`,
      name: SITE_NAME,
      description: SITE_DESCRIPTION,
      url: SITE_URL,
      applicationCategory: 'DeveloperApplication',
      applicationSubCategory: 'SaaS framework',
      operatingSystem: 'Linux, macOS, Windows (Docker)',
      license: 'https://opensource.org/licenses/MIT',
      isAccessibleForFree: true,
      offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
      publisher: { '@id': `${SITE_URL}/#organization` },
      featureList: [
        'Multi-tenant architecture',
        'JWT auth, 2FA, SSO and role-based permissions',
        'Stripe and PayPal subscription billing',
        'AI build agent that generates code and pull requests',
        'Chat assistants with file upload using your own AI keys',
        'Supports OpenAI, Anthropic Claude, Google Gemini, Azure OpenAI, GitHub Models and Ollama',
      ],
    },
    {
      '@type': 'SoftwareSourceCode',
      name: SITE_NAME,
      codeRepository: GITHUB_URL,
      programmingLanguage: ['Python', 'TypeScript'],
      runtimePlatform: ['FastAPI', 'Next.js'],
      license: 'https://opensource.org/licenses/MIT',
      targetProduct: { '@id': `${SITE_URL}/#software` },
    },
    {
      '@type': 'FAQPage',
      '@id': `${SITE_URL}/#faq`,
      mainEntity: FAQ.map(f => ({
        '@type': 'Question',
        name: f.q,
        acceptedAnswer: { '@type': 'Answer', text: f.a },
      })),
    },
  ],
}

export default function RootPage() {
  return (
    <>
      <script
        type="application/ld+json"
        // Static, server-built object; no user input reaches this string.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, '\\u003c') }}
      />
      <HomePage />
    </>
  )
}
