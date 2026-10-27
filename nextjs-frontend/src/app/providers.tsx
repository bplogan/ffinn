'use client'
import { ThemeProvider } from 'next-themes'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from '@/contexts/AuthContext'
import { useState } from 'react'

export default function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } }))
  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
      <QueryClientProvider client={qc}>
        <AuthProvider>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              // Ink toasts in both themes, matching the portal's dark surfaces
              style: { borderRadius: '14px', background: '#131519', color: '#f2f2ee', fontSize: '14px', border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 20px 50px -20px rgba(0,0,0,0.5)' },
              success: { iconTheme: { primary: '#4ade80', secondary: '#131519' } },
              error:   { iconTheme: { primary: '#f87171', secondary: '#131519' } },
            }}
          />
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
