'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

export default function AIAgentLayout({ children }: { children: React.ReactNode }) {
  const { isHost, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !isHost) {
      router.replace('/app/dashboard')
    }
  }, [isHost, isLoading, router])

  if (isLoading) return <LoadingSpinner fullPage label="Loading…" />
  if (!isHost) return null

  return children
}
