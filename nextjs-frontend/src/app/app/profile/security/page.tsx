'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { authApi } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import Breadcrumb from '@/components/ui/Breadcrumb'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import Badge from '@/components/ui/Badge'
import { Shield, ShieldCheck, ShieldOff, Copy } from 'lucide-react'
import toast from 'react-hot-toast'
import { useForm } from 'react-hook-form'

export default function SecurityPage() {
  const qc = useQueryClient()
  const [showSetup, setShowSetup] = useState(false)
  const [setupData, setSetupData] = useState<{ sharedKey?: string; qrCodeUri?: string; recoveryCodes?: string[] } | null>(null)
  const [showDisable, setShowDisable] = useState(false)
  const { register: regSetup, handleSubmit: hsSetup, reset: resetSetup, formState: { errors: errSetup } } = useForm<{ code: string }>()
  const { register: regDisable, handleSubmit: hsDisable, reset: resetDisable } = useForm<{ code: string }>()

  const { data: status, isLoading } = useQuery<{ isEnabled: boolean; hasAuthenticator: boolean }>({
    queryKey: ['2fa-status'],
    queryFn: () => authApi.getTwoFactorStatus() as Promise<{ isEnabled: boolean; hasAuthenticator: boolean }>,
  })

  const generateMut = useMutation({
    mutationFn: () => authApi.generateTwoFactor(),
    onSuccess: (d) => { setSetupData(d as typeof setupData); setShowSetup(true) },
    onError: () => toast.error('Failed to generate 2FA'),
  })

  const enableMut = useMutation({
    mutationFn: (d: { code: string }) => authApi.enableTwoFactor(d),
    onSuccess: (d) => {
      toast.success('Two-factor authentication enabled')
      setSetupData(prev => ({ ...prev, recoveryCodes: (d as { recoveryCodes?: string[] }).recoveryCodes }))
      qc.invalidateQueries({ queryKey: ['2fa-status'] })
      resetSetup()
    },
    onError: () => toast.error('Invalid code — try again'),
  })

  const disableMut = useMutation({
    mutationFn: (d: { code: string }) => authApi.disableTwoFactor(d),
    onSuccess: () => {
      toast.success('Two-factor authentication disabled')
      setShowDisable(false); resetDisable()
      qc.invalidateQueries({ queryKey: ['2fa-status'] })
    },
    onError: () => toast.error('Invalid code'),
  })

  return (
    <div className="space-y-4 max-w-xl">
      <Breadcrumb crumbs={[{ label: 'Profile', href: '/app/profile' }, { label: 'Security' }]} />
      <PageHeader title="Security Settings" subtitle="Manage two-factor authentication and account security" />

      <div className="card p-6">
        <div className="flex items-start gap-4">
          <div className={`p-3 rounded-xl ${status?.isEnabled ? 'bg-success-50 dark:bg-success-900/20' : 'bg-gray-100 dark:bg-gray-800'}`}>
            {status?.isEnabled ? <ShieldCheck size={24} className="text-success-600" /> : <Shield size={24} className="text-gray-400" />}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-gray-900 dark:text-white">Two-factor authentication</h3>
              {status?.isEnabled ? <Badge variant="success">Enabled</Badge> : <Badge variant="gray">Disabled</Badge>}
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              {status?.isEnabled
                ? 'Your account is protected with two-factor authentication.'
                : 'Add an extra layer of security to your account by requiring a verification code in addition to your password.'}
            </p>
            {isLoading ? null : status?.isEnabled ? (
              <Button variant="danger" icon={<ShieldOff size={15} />} onClick={() => setShowDisable(true)}>Disable 2FA</Button>
            ) : (
              <Button icon={<ShieldCheck size={15} />} onClick={() => generateMut.mutate()} loading={generateMut.isPending}>
                Enable 2FA
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Setup modal */}
      <Modal open={showSetup} onClose={() => setShowSetup(false)} title="Set up authenticator app">
        <div className="space-y-5">
          {!setupData?.recoveryCodes ? (
            <>
              <p className="text-sm text-gray-600 dark:text-gray-400">Scan the QR code with your authenticator app (Google Authenticator, Authy, etc.)</p>
              {setupData?.qrCodeUri && (
                <div className="flex justify-center">
                  <img src={setupData.qrCodeUri} alt="QR Code" className="w-48 h-48" />
                </div>
              )}
              {setupData?.sharedKey && (
                <div className="flex items-center gap-2 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <code className="flex-1 text-xs font-mono text-gray-700 dark:text-gray-300">{setupData.sharedKey}</code>
                  <button onClick={() => { navigator.clipboard.writeText(setupData!.sharedKey!); toast.success('Copied') }}>
                    <Copy size={14} className="text-gray-400 hover:text-gray-600" />
                  </button>
                </div>
              )}
              <form onSubmit={hsSetup(d => enableMut.mutate(d))} className="space-y-3">
                <Input {...regSetup('code', { required: 'Code required', minLength: { value: 6, message: 'Must be 6 digits' } })}
                  label="Verification code" placeholder="000000" maxLength={6} error={errSetup.code?.message} />
                <div className="flex gap-2 justify-end">
                  <Button variant="secondary" type="button" onClick={() => setShowSetup(false)}>Cancel</Button>
                  <Button type="submit" loading={enableMut.isPending}>Verify & Enable</Button>
                </div>
              </form>
            </>
          ) : (
            <>
              <p className="text-sm font-medium text-success-600 dark:text-success-400">Two-factor authentication enabled!</p>
              <p className="text-sm text-gray-600 dark:text-gray-400">Save these recovery codes somewhere safe. Each code can only be used once.</p>
              <div className="grid grid-cols-2 gap-2 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                {setupData.recoveryCodes.map(c => <code key={c} className="text-xs font-mono text-gray-700 dark:text-gray-300">{c}</code>)}
              </div>
              <Button onClick={() => setShowSetup(false)}>Done</Button>
            </>
          )}
        </div>
      </Modal>

      {/* Disable modal */}
      <Modal open={showDisable} onClose={() => setShowDisable(false)} title="Disable two-factor authentication">
        <form onSubmit={hsDisable(d => disableMut.mutate(d))} className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">Enter your current authenticator code to confirm.</p>
          <Input {...regDisable('code', { required: true })} label="Verification code" placeholder="000000" maxLength={6} />
          <div className="flex gap-2 justify-end">
            <Button variant="secondary" type="button" onClick={() => setShowDisable(false)}>Cancel</Button>
            <Button variant="danger" type="submit" loading={disableMut.isPending}>Disable 2FA</Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
