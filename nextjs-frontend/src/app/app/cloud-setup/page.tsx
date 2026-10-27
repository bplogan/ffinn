'use client'
import { useEffect, useState, useRef } from 'react'
import { useForm } from 'react-hook-form'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { cloudSetupApi } from '@/lib/api'
import type { CloudSetupProgress } from '@/types'
import {
  CLOUD_PROVIDERS,
  buildCloudCredentials,
  buildCloudProvisionPayload,
  cloudAuthDefaultValues,
  cloudProvisionDefaultValues,
  getCloudProvider,
} from '@/lib/cloudProviderConfig'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { Select, TextArea } from '@/components/ui/Input'
import Badge from '@/components/ui/Badge'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Cloud, Github, Settings, CheckCircle, Circle } from 'lucide-react'
import toast from 'react-hot-toast'

interface GithubSetupFormValues {
  owner: string
  repository: string
  branch: string
}

const STEPS = [
  { key: 'cloud_auth', label: 'Cloud credentials', icon: Cloud },
  { key: 'cloud_provision', label: 'Provision resources', icon: Cloud },
  { key: 'app_settings', label: 'App settings', icon: Settings },
  { key: 'github_auth', label: 'GitHub token', icon: Github },
  { key: 'github_setup', label: 'Repository setup', icon: Github },
  { key: 'complete', label: 'Complete', icon: CheckCircle },
]

export default function CloudSetupPage() {
  const qc = useQueryClient()
  const [activeStep, setActiveStep] = useState(1)

  const { data: progress, isLoading, isError, refetch } = useQuery<CloudSetupProgress>({
    queryKey: ['cloud-setup'],
    queryFn: () => cloudSetupApi.progress(),
  })

  const startMut = useMutation({
    mutationFn: () => cloudSetupApi.start(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cloud-setup'] }),
    onError: () => toast.error('Could not start cloud setup'),
  })

  const startedRef = useRef(false)
  useEffect(() => {
    if (!isLoading && !progress && !startMut.isPending && !startedRef.current) {
      startedRef.current = true
      startMut.mutate()
    }
  }, [isLoading, progress, startMut.isPending]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (progress?.current_step) setActiveStep(progress.current_step)
  }, [progress?.current_step])

  const cloudAuthForm = useForm<Record<string, string>>({
    defaultValues: cloudAuthDefaultValues(),
  })

  const selectedProvider = cloudAuthForm.watch('provider')
  const selectedProviderDef = getCloudProvider(selectedProvider)

  useEffect(() => {
    const def = getCloudProvider(selectedProvider)
    if (def?.credentialFields.some(f => f.key === 'region')) {
      cloudAuthForm.setValue('region', def.defaultRegion)
    }
  }, [selectedProvider]) // eslint-disable-line react-hooks/exhaustive-deps

  const provisionForm = useForm<Record<string, string>>({
    defaultValues: cloudProvisionDefaultValues(selectedProvider),
  })

  // Reset provision defaults when the authenticated provider changes
  useEffect(() => {
    const provider = progress?.cloud_provider ?? selectedProvider
    provisionForm.reset(cloudProvisionDefaultValues(provider))
  }, [progress?.cloud_provider, selectedProvider]) // eslint-disable-line react-hooks/exhaustive-deps

  const appSettingsForm = useForm({
    defaultValues: { app_url: '', database_url: '', jwt_secret: '' },
  })

  const githubAuthForm = useForm({ defaultValues: { token: '' } })
  const githubSetupForm = useForm<GithubSetupFormValues>({ defaultValues: { owner: '', repository: '', branch: 'main' } })

  const cloudAuthMut = useMutation({
    mutationFn: (d: Record<string, string>) =>
      cloudSetupApi.cloudAuthenticate({
        provider: d.provider,
        credentials: buildCloudCredentials(d.provider, d),
      }),
    onSuccess: () => { toast.success('Cloud credentials validated'); qc.invalidateQueries({ queryKey: ['cloud-setup'] }) },
    onError: () => toast.error('Cloud authentication failed'),
  })

  const provisionMut = useMutation({
    mutationFn: (d: Record<string, string>) => {
      const provider = progress?.cloud_provider ?? selectedProvider
      return cloudSetupApi.cloudProvision(buildCloudProvisionPayload(provider, d))
    },
    onSuccess: async () => {
      await cloudSetupApi.cloudProvisionStatus()
      toast.success('Provisioning started')
      qc.invalidateQueries({ queryKey: ['cloud-setup'] })
    },
    onError: () => toast.error('Provisioning failed'),
  })

  const appSettingsMut = useMutation({
    mutationFn: (d: Record<string, string>) => cloudSetupApi.saveAppSettings(d),
    onSuccess: () => { toast.success('Settings saved'); qc.invalidateQueries({ queryKey: ['cloud-setup'] }) },
    onError: () => toast.error('Failed to save settings'),
  })

  const githubAuthMut = useMutation({
    mutationFn: (d: { token: string }) => cloudSetupApi.githubAuthenticate(d),
    onSuccess: () => { toast.success('GitHub authenticated'); qc.invalidateQueries({ queryKey: ['cloud-setup'] }) },
    onError: () => toast.error('GitHub authentication failed'),
  })

  const githubSetupMut = useMutation({
    mutationFn: (d: GithubSetupFormValues) =>
      cloudSetupApi.githubSetup({ ...d, create_workflows: true }),
    onSuccess: () => { toast.success('Repository configured'); qc.invalidateQueries({ queryKey: ['cloud-setup'] }) },
    onError: () => toast.error('GitHub setup failed'),
  })

  const completeMut = useMutation({
    mutationFn: () => cloudSetupApi.complete(),
    onSuccess: () => { toast.success('Cloud setup complete!'); qc.invalidateQueries({ queryKey: ['cloud-setup'] }) },
  })

  if (isLoading) return <LoadingSpinner fullPage />
  if (isError || !progress) {
    return (
      <div className="space-y-4 text-center py-16">
        <p className="text-gray-500">Could not load cloud setup progress.</p>
        <Button onClick={() => { startedRef.current = false; refetch() }}>Retry</Button>
      </div>
    )
  }

  const completed = new Set(progress.steps_completed || [])
  const provisionProvider = getCloudProvider(progress.cloud_provider ?? selectedProvider)

  return (
    <div className="space-y-6 max-w-3xl">
      <PageHeader
        title="Cloud Setup Wizard"
        subtitle="Provision cloud infrastructure and connect GitHub CI/CD"
        actions={
          progress.status !== 'completed' ? (
            <Badge variant="warning">Step {progress.current_step} of {progress.total_steps}</Badge>
          ) : (
            <Badge variant="success">Completed</Badge>
          )
        }
      />

      <div className="card p-4">
        <ol className="space-y-2">
          {STEPS.map((step, i) => {
            const Icon = step.icon
            const done = completed.has(step.key)
            return (
              <li key={step.key} className="flex items-center gap-3 text-sm">
                {done ? <CheckCircle size={16} className="text-success-500" /> : <Circle size={16} className="text-gray-400" />}
                <Icon size={14} className="text-gray-500" />
                <span className={done ? 'text-gray-900 dark:text-white' : 'text-gray-500'}>{i + 1}. {step.label}</span>
              </li>
            )
          })}
        </ol>
      </div>

      {activeStep <= 1 && !completed.has('cloud_auth') && (
        <form onSubmit={cloudAuthForm.handleSubmit(d => cloudAuthMut.mutate(d))} className="card p-6 space-y-4">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200">1. Cloud credentials</h2>
          <Select {...cloudAuthForm.register('provider')} label="Provider">
            {CLOUD_PROVIDERS.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </Select>
          {selectedProviderDef?.credentialFields.map(field => (
            field.type === 'textarea' ? (
              <TextArea
                key={field.key}
                {...cloudAuthForm.register(field.key, { required: field.required })}
                label={field.label}
                rows={6}
                placeholder={field.placeholder}
                hint={field.hint}
                required={field.required}
                className="font-mono text-sm"
              />
            ) : (
              <Input
                key={field.key}
                {...cloudAuthForm.register(field.key, { required: field.required })}
                label={field.label}
                type={field.type ?? 'text'}
                placeholder={field.placeholder}
                hint={field.hint}
              />
            )
          ))}
          {selectedProvider === 'local' && (
            <p className="text-sm text-gray-500">Local development uses Docker Compose — no cloud credentials required.</p>
          )}
          <Button type="submit" loading={cloudAuthMut.isPending}>Validate credentials</Button>
        </form>
      )}

      {completed.has('cloud_auth') && !completed.has('cloud_provision') && (
        <form onSubmit={provisionForm.handleSubmit(d => provisionMut.mutate(d))} className="card p-6 space-y-4">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200">2. Provision resources</h2>
          {provisionProvider && (
            <p className="text-sm text-gray-500">
              Configuring resources for <span className="font-medium">{provisionProvider.label}</span>
            </p>
          )}
          {provisionProvider?.provisionFields.map(field => (
            <Input
              key={field.key}
              {...provisionForm.register(field.key, { required: field.required })}
              label={field.label}
              placeholder={field.placeholder}
              hint={field.hint}
            />
          ))}
          <Button type="submit" loading={provisionMut.isPending}>Start provisioning</Button>
        </form>
      )}

      {completed.has('cloud_provision') && !completed.has('app_settings') && (
        <form onSubmit={appSettingsForm.handleSubmit(d => appSettingsMut.mutate(d))} className="card p-6 space-y-4">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200">3. Application settings</h2>
          <Input {...appSettingsForm.register('app_url')} label="App URL" placeholder="https://app.example.com" />
          <Input {...appSettingsForm.register('database_url')} label="Database URL" type="password" />
          <Input {...appSettingsForm.register('jwt_secret')} label="JWT secret" type="password" />
          <Button type="submit" loading={appSettingsMut.isPending}>Save settings</Button>
        </form>
      )}

      {completed.has('app_settings') && !completed.has('github_auth') && (
        <form onSubmit={githubAuthForm.handleSubmit(d => githubAuthMut.mutate(d))} className="card p-6 space-y-4">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200">4. GitHub authentication</h2>
          <Input {...githubAuthForm.register('token', { required: true })} label="Personal access token" type="password" />
          <Button type="submit" loading={githubAuthMut.isPending}>Verify token</Button>
        </form>
      )}

      {completed.has('github_auth') && !completed.has('github_setup') && (
        <form onSubmit={githubSetupForm.handleSubmit(d => githubSetupMut.mutate(d))} className="card p-6 space-y-4">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200">5. Repository setup</h2>
          <Input {...githubSetupForm.register('owner', { required: true })} label="Owner" />
          <Input {...githubSetupForm.register('repository', { required: true })} label="Repository" />
          <Input {...githubSetupForm.register('branch')} label="Branch" />
          <Button type="submit" loading={githubSetupMut.isPending}>Configure repository</Button>
        </form>
      )}

      {completed.has('github_setup') && progress.status !== 'completed' && (
        <div className="card p-6">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200 mb-4">6. Finish setup</h2>
          <Button onClick={() => completeMut.mutate()} loading={completeMut.isPending}>Mark setup complete</Button>
        </div>
      )}

      {progress.status === 'completed' && (
        <div className="card p-6 border-success-200 bg-success-50 dark:bg-success-900/20">
          <p className="text-success-700 dark:text-success-300 font-medium">Cloud setup is complete.</p>
          {progress.completed_at && <p className="text-sm text-gray-500 mt-1">Finished {new Date(progress.completed_at).toLocaleString()}</p>}
        </div>
      )}
    </div>
  )
}
