'use client'
import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { notificationsApi } from '@/lib/api'
import type { NotificationConfiguration } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { Select } from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { MessageSquare, Bell, Send } from 'lucide-react'
import toast from 'react-hot-toast'

const emptyConfig: Partial<NotificationConfiguration> = {
  smsEnabled: false,
  pushEnabled: false,
  pushProvider: 'firebase',
}

export default function NotificationsAdminPage() {
  const qc = useQueryClient()
  const [form, setForm] = useState<Partial<NotificationConfiguration>>(emptyConfig)
  const [twilioAuthToken, setTwilioAuthToken] = useState('')
  const [firebaseJson, setFirebaseJson] = useState('')
  const [testPhone, setTestPhone] = useState('')
  const [testFcmToken, setTestFcmToken] = useState('')
  const [testIdentity, setTestIdentity] = useState('')

  const { data, isLoading } = useQuery<NotificationConfiguration>({
    queryKey: ['notification-config'],
    queryFn: () => notificationsApi.getConfig() as Promise<NotificationConfiguration>,
  })

  useEffect(() => {
    if (data) {
      setForm({
        smsEnabled: data.smsEnabled,
        twilioAccountSid: data.twilioAccountSid,
        twilioFromNumber: data.twilioFromNumber,
        pushEnabled: data.pushEnabled,
        pushProvider: data.pushProvider || 'firebase',
        firebaseProjectId: data.firebaseProjectId,
        twilioNotifyServiceSid: data.twilioNotifyServiceSid,
        hasTwilioAuthToken: data.hasTwilioAuthToken,
        hasFirebaseCredentials: data.hasFirebaseCredentials,
      })
    }
  }, [data])

  const saveMut = useMutation({
    mutationFn: () => notificationsApi.updateConfig({
      smsEnabled: form.smsEnabled,
      twilioAccountSid: form.twilioAccountSid,
      twilioAuthToken: twilioAuthToken || undefined,
      twilioFromNumber: form.twilioFromNumber,
      pushEnabled: form.pushEnabled,
      pushProvider: form.pushProvider,
      firebaseProjectId: form.firebaseProjectId,
      firebaseCredentialsJson: firebaseJson || undefined,
      twilioNotifyServiceSid: form.twilioNotifyServiceSid,
    }),
    onSuccess: () => {
      toast.success('Notification settings saved')
      setTwilioAuthToken('')
      setFirebaseJson('')
      qc.invalidateQueries({ queryKey: ['notification-config'] })
    },
    onError: (e: Error) => toast.error(e.message || 'Failed to save'),
  })

  const testSmsMut = useMutation({
    mutationFn: () => notificationsApi.testSms({ to: testPhone }),
    onSuccess: () => toast.success('Test SMS sent'),
    onError: (e: Error) => toast.error(e.message || 'SMS test failed'),
  })

  const testPushMut = useMutation({
    mutationFn: () => notificationsApi.testPush({
      deviceToken: form.pushProvider === 'firebase' ? testFcmToken : undefined,
      identity: form.pushProvider === 'twilio' ? testIdentity : undefined,
    }),
    onSuccess: () => toast.success('Test push sent'),
    onError: (e: Error) => toast.error(e.message || 'Push test failed'),
  })

  if (isLoading) return <LoadingSpinner fullPage />

  return (
    <div className="space-y-6 max-w-3xl">
      <PageHeader
        title="Notifications"
        subtitle="Configure Twilio SMS and push notifications (Firebase or Twilio Notify) for your tenant"
      />

      {/* SMS */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <MessageSquare size={18} className="text-brand-500" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">SMS (Twilio)</h2>
        </div>
        <label className="flex items-center justify-between gap-4">
          <span className="text-sm text-gray-600 dark:text-gray-400">Enable SMS</span>
          <input
            type="checkbox"
            checked={!!form.smsEnabled}
            onChange={e => setForm(f => ({ ...f, smsEnabled: e.target.checked }))}
            className="h-4 w-4 rounded border-gray-300"
          />
        </label>
        <Input
          label="Twilio Account SID"
          value={form.twilioAccountSid || ''}
          onChange={e => setForm(f => ({ ...f, twilioAccountSid: e.target.value }))}
          placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        />
        <Input
          label="Twilio Auth Token"
          type="password"
          value={twilioAuthToken}
          onChange={e => setTwilioAuthToken(e.target.value)}
          placeholder={form.hasTwilioAuthToken ? '••••••••  (leave blank to keep existing)' : 'Your auth token'}
        />
        <Input
          label="From Number"
          value={form.twilioFromNumber || ''}
          onChange={e => setForm(f => ({ ...f, twilioFromNumber: e.target.value }))}
          placeholder="+15551234567"
          hint="E.164 format — your Twilio phone number or messaging service sender"
        />
        <div className="flex gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
          <Input
            label="Test phone number"
            value={testPhone}
            onChange={e => setTestPhone(e.target.value)}
            placeholder="+15559876543"
            className="flex-1"
          />
          <div className="flex items-end">
            <Button
              variant="secondary"
              icon={<Send size={14} />}
              onClick={() => testSmsMut.mutate()}
              loading={testSmsMut.isPending}
              disabled={!testPhone}
            >
              Send test SMS
            </Button>
          </div>
        </div>
      </div>

      {/* Push */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Bell size={18} className="text-brand-500" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Push notifications</h2>
        </div>
        <label className="flex items-center justify-between gap-4">
          <span className="text-sm text-gray-600 dark:text-gray-400">Enable push</span>
          <input
            type="checkbox"
            checked={!!form.pushEnabled}
            onChange={e => setForm(f => ({ ...f, pushEnabled: e.target.checked }))}
            className="h-4 w-4 rounded border-gray-300"
          />
        </label>
        <Select
          label="Push provider"
          value={form.pushProvider || 'firebase'}
          onChange={e => setForm(f => ({ ...f, pushProvider: e.target.value as 'firebase' | 'twilio' }))}
        >
          <option value="firebase">Firebase Cloud Messaging (iOS, Android, Web)</option>
          <option value="twilio">Twilio Notify</option>
        </Select>

        {form.pushProvider === 'firebase' ? (
          <>
            <Input
              label="Firebase Project ID"
              value={form.firebaseProjectId || ''}
              onChange={e => setForm(f => ({ ...f, firebaseProjectId: e.target.value }))}
              placeholder="my-app-project"
            />
            <div>
              <label className="label">Service Account JSON</label>
              <textarea
                className="input-field min-h-[120px] font-mono text-xs"
                value={firebaseJson}
                onChange={e => setFirebaseJson(e.target.value)}
                placeholder={
                  form.hasFirebaseCredentials
                    ? 'Leave blank to keep existing credentials…'
                    : 'Paste the full JSON from Firebase Console → Project settings → Service accounts'
                }
              />
              <p className="text-xs text-gray-500 mt-1">Stored encrypted. Required for iOS, Android, and web push via FCM.</p>
            </div>
            <div className="flex gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
              <Input
                label="Test FCM device token"
                value={testFcmToken}
                onChange={e => setTestFcmToken(e.target.value)}
                placeholder="Device registration token from your mobile/web app"
                className="flex-1"
              />
              <div className="flex items-end">
                <Button
                  variant="secondary"
                  icon={<Send size={14} />}
                  onClick={() => testPushMut.mutate()}
                  loading={testPushMut.isPending}
                  disabled={!testFcmToken}
                >
                  Send test push
                </Button>
              </div>
            </div>
          </>
        ) : (
          <>
            <p className="text-xs text-gray-500">
              Twilio Notify uses the same Account SID and Auth Token as SMS above. Create a Notify Service in the Twilio Console.
            </p>
            <Input
              label="Twilio Notify Service SID"
              value={form.twilioNotifyServiceSid || ''}
              onChange={e => setForm(f => ({ ...f, twilioNotifyServiceSid: e.target.value }))}
              placeholder="ISxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            />
            <div className="flex gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
              <Input
                label="Test Notify identity"
                value={testIdentity}
                onChange={e => setTestIdentity(e.target.value)}
                placeholder="user-identity-with-registered-binding"
                hint="A Twilio Notify identity that already has an FCM/APN binding"
                className="flex-1"
              />
              <div className="flex items-end">
                <Button
                  variant="secondary"
                  icon={<Send size={14} />}
                  onClick={() => testPushMut.mutate()}
                  loading={testPushMut.isPending}
                  disabled={!testIdentity}
                >
                  Send test push
                </Button>
              </div>
            </div>
          </>
        )}
      </div>

      <Button onClick={() => saveMut.mutate()} loading={saveMut.isPending}>
        Save notification settings
      </Button>
    </div>
  )
}
