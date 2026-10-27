'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

export default function CloudSetupLayout({ children }: { children: React.ReactNode }) {
  const { isHost, isLoading, hasRole, hasPermission } = useAuth()
  const router = useRouter()
  // Host-level sign-ups are host users too, so also require the permission the API checks
  const allowed = isHost && (hasRole('Admin') || hasPermission('CloudSetup.View'))

  useEffect(() => {
    if (!isLoading && !allowed) {
      router.replace('/app/dashboard')
    }
  }, [allowed, isLoading, router])

  if (isLoading) return <LoadingSpinner fullPage label="Loading…" />
  if (!allowed) return null

  return children
}
