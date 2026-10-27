'use client'
import { useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { teamInvitationsApi } from '@/lib/api'
import { tokenStore } from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import Button from '@/components/ui/Button'
import toast from 'react-hot-toast'
import { Suspense } from 'react'
import { UserPlus } from 'lucide-react'
import { AuthStatus } from '../AuthShell'

function AcceptContent() {
  const params = useSearchParams()
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [info, setInfo] = useState<{ tenantName?: string; roleName?: string } | null>(null)
  const token = params.get('token')

  useEffect(() => {
    // Optionally preload invite info
    setInfo({ tenantName: 'Your Organization' })
  }, [])

  const accept = async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await teamInvitationsApi.accept(token) as { access_token?: string }
      if (res.access_token) tokenStore.set(res.access_token)
      toast.success('Invitation accepted!')
      router.push('/app/dashboard')
    } catch { toast.error('Failed to accept invitation') }
    finally { setLoading(false) }
  }

  return (
    <AuthStatus tone="info" icon={<UserPlus size={22} />} title="You're invited">
      <p>
        You have been invited to join {info?.tenantName || 'a workspace'}{info?.roleName ? ` as ${info.roleName}` : ''} on ffinn.
      </p>
      <Button onClick={accept} loading={loading} size="lg" className="w-full">Accept invitation</Button>
    </AuthStatus>
  )
}

export default function AcceptInvitationPage() {
  return <Suspense><AcceptContent /></Suspense>
}
