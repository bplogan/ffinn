'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

/**
 * Admin section layout — guards all /app/admin/** routes so that only users
 * with the "Admin" role can access them.  The parent AppLayout already
 * ensures the user is authenticated; this layer adds the role check.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { isLoading, hasRole } = useAuth()
  const router = useRouter()
  const isAdmin = hasRole('Admin')

  useEffect(() => {
    if (!isLoading && !isAdmin) {
      router.replace('/app/dashboard')
    }
  }, [isLoading, isAdmin, router])

  if (isLoading) return <LoadingSpinner fullPage label="Checking permissions…" />
  if (!isAdmin) return null

  return <>{children}</>
}
