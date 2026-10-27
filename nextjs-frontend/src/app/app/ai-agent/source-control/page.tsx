'use client'
import { useForm } from 'react-hook-form'
import { useQuery, useMutation } from '@tanstack/react-query'
import { aiSourceControlApi, aiAgentsApi } from '@/lib/api'
import type { AIAgentConfig, PagedResult } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Breadcrumb from '@/components/ui/Breadcrumb'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { Select } from '@/components/ui/Input'
import Badge from '@/components/ui/Badge'
import { Save, GitBranch, Github, Bot } from 'lucide-react'
import toast from 'react-hot-toast'
import { useEffect, useMemo, useRef } from 'react'
import Link from 'next/link'

interface SourceControlConfig {
  provider: string; repoUrl: string; branch: string; accessToken: string; autoSync: boolean; syncPath: string
}

export default function SourceControlPage() {
  const { data: settings, isLoading: settingsLoading } = useQuery<Record<string, string | null>>({
    queryKey: ['ai-source-control-config'],
    queryFn: () => aiSourceControlApi.get() as Promise<Record<string, string | null>>,
  })

  const { data: agentsRaw, isLoading: agentsLoading } = useQuery<PagedResult<AIAgentConfig>>({
    queryKey: ['ai-agent-configs'],
    queryFn: () => aiAgentsApi.list({ page: 1, page_size: 100 }) as Promise<PagedResult<AIAgentConfig>>,
  })
  const agents = useMemo(
    () => (agentsRaw?.items ?? []).filter(a => a.repository_url),
    [agentsRaw?.items],
  )
  const fallbackAgent = agents[0]

  const { register, handleSubmit, reset, formState: { errors, isDirty } } = useForm<SourceControlConfig>({
    defaultValues: { provider: 'github', branch: 'main', autoSync: false, syncPath: '/' }
  })

  const formInitializedRef = useRef(false)

  useEffect(() => {
    if (settingsLoading || agentsLoading || formInitializedRef.current) return

    const tenantRepo = settings?.['SourceControl.RepoUrl']?.trim()
    if (tenantRepo && settings) {
      reset({
        provider: settings['SourceControl.Provider'] ?? 'github',
        repoUrl: tenantRepo,
        branch: settings['SourceControl.Branch'] ?? 'main',
        accessToken: settings['SourceControl.AccessToken'] ?? '',
        autoSync: settings['SourceControl.AutoSync'] === 'true',
        syncPath: settings['SourceControl.SyncPath'] ?? '/',
      })
      formInitializedRef.current = true
      return
    }

    if (fallbackAgent?.repository_url) {
      reset({
        provider: fallbackAgent.source_control_type ?? fallbackAgent.source_control_provider ?? 'github',
        repoUrl: fallbackAgent.repository_url,
        branch: 'main',
        accessToken: '',
        autoSync: false,
        syncPath: '/',
      })
      formInitializedRef.current = true
    }
  }, [
    settings,
    fallbackAgent?.id,
    fallbackAgent?.repository_url,
    settingsLoading,
    agentsLoading,
    reset,
  ])

  const saveMut = useMutation({
    mutationFn: (d: SourceControlConfig) => aiSourceControlApi.save({
      provider:     d.provider,
      repo_url:     d.repoUrl,
      branch:       d.branch,
      ...(d.accessToken ? { access_token: d.accessToken } : {}),
      auto_sync:    d.autoSync,
      sync_path:    d.syncPath,
    }),
    onSuccess: () => toast.success('Source control settings saved'),
    onError: () => toast.error('Save failed'),
  })

  const isLoading = settingsLoading || agentsLoading

  return (
    <div className="space-y-4">
      <Breadcrumb crumbs={[{ label: 'AI Agent', href: '/app/ai-agent' }, { label: 'Source Control' }]} />
      <PageHeader title="Source Control" subtitle="Connect a Git repository to sync agent configurations" />

      {agents.length > 0 && (
        <div className="card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Bot size={15} className="text-brand-500" />
            Connected via agent setup
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Repositories linked during the setup wizard are stored on each agent.
          </p>
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {agents.map(a => (
              <div key={a.id} className="py-3 flex flex-wrap items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 dark:text-white">{a.name ?? a.id}</p>
                  <p className="text-xs text-gray-500 flex items-center gap-1 truncate">
                    <GitBranch size={12} className="flex-shrink-0" />
                    {a.repository_url}
                  </p>
                </div>
                <Badge variant="success">{a.source_control_type ?? a.source_control_provider ?? 'github'}</Badge>
                <Link href="/app/ai-agent/builder" className="text-xs text-brand-500 hover:underline">
                  Manage
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card p-6 max-w-xl space-y-5">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Tenant defaults</h2>
        {isLoading ? (
          <div className="py-4 text-center text-gray-400">Loading…</div>
        ) : (
          <form onSubmit={handleSubmit(d => saveMut.mutate(d))} className="space-y-5">
            <Select {...register('provider')} label="Git provider">
              <option value="github">GitHub</option>
              <option value="gitlab">GitLab</option>
              <option value="bitbucket">Bitbucket</option>
              <option value="azure-devops">Azure DevOps</option>
            </Select>

            <Input {...register('repoUrl', { required: 'Repository URL is required' })}
              label="Repository URL" placeholder="https://github.com/org/repo"
              error={errors.repoUrl?.message}
              leftIcon={<Github size={15} className="text-gray-400" />} />

            <div className="grid grid-cols-2 gap-4">
              <Input {...register('branch')} label="Branch" placeholder="main"
                leftIcon={<GitBranch size={15} className="text-gray-400" />} />
              <Input {...register('syncPath')} label="Sync path" placeholder="/" />
            </div>

            <Input {...register('accessToken')} label="Access token" type="password"
              placeholder="Leave blank to keep existing token"
              hint="Personal access token with repo permissions. Leave blank to preserve the currently saved token." />

            <div className="flex items-center gap-2">
              <input type="checkbox" id="autoSync" {...register('autoSync')}
                className="rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
              <label htmlFor="autoSync" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Auto-sync on push
              </label>
            </div>

            <Button type="submit" icon={<Save size={15} />} loading={saveMut.isPending} disabled={!isDirty}>
              Save settings
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}
