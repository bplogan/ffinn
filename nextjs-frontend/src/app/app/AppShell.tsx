'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

/** Signed-in portal chrome, on the public site's paper/ink tokens (`.site`). */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace('/auth/login')
  }, [isAuthenticated, isLoading, router])

  if (isLoading) return <div className="site min-h-screen"><LoadingSpinner fullPage label="Loading…" /></div>
  if (!isAuthenticated) return null

  return (
    <div className="site flex h-screen overflow-hidden antialiased">
      <a href="#main" className="sr-only-focusable fixed left-4 top-4 z-[60] rounded-full bg-ink px-4 py-2 text-sm text-canvas">
        Skip to content
      </a>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main id="main" className="flex-1 overflow-y-auto">
          <div className="px-4 py-6 md:px-8 md:py-8 max-w-[1440px] mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
