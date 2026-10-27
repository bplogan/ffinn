'use client'
import { useQuery } from '@tanstack/react-query'
import { aiAgentsApi, aiProvidersApi, aiGenerationsApi } from '@/lib/api'
import type { AIAgent, AIProvider, AIGeneration, PagedResult, AIAgentConfig } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Bot, Zap, History, ArrowRight, Wand2 } from 'lucide-react'
import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'
import { getUserStatusLabel, statusBadgeVariant } from '@/lib/generationStatus'
import AgentAvatar from '@/components/ai-agent/AgentAvatar'

export default function AIAgentDashboardPage() {
  const { data: agents, isLoading: agentsLoading } = useQuery<PagedResult<AIAgent>>({ queryKey: ['ai-agents'], queryFn: () => aiAgentsApi.list() as Promise<PagedResult<AIAgent>> })
  const { data: providers } = useQuery<AIProvider[]>({ queryKey: ['ai-providers'], queryFn: () => aiProvidersApi.list() as Promise<AIProvider[]> })
  const { data: history, isLoading: historyLoading } = useQuery<PagedResult<AIGeneration>>({ queryKey: ['ai-history'], queryFn: () => aiGenerationsApi.list({ page: 1, page_size: 5 }) as Promise<PagedResult<AIGeneration>> })

  const activeProviders = providers?.filter(p => p.is_active ?? p.isActive) ?? []
  const agentList = agents?.items ?? []

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Agent"
        subtitle="Build, manage and monitor your AI agents"
        actions={<Link href="/app/ai-agent/agents"><Button icon={<Wand2 size={16} />}>New Agent</Button></Link>}
      />

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Agents', value: agents?.totalCount ?? 0, icon: <Bot size={18} />, color: 'bg-purple-50 dark:bg-purple-900/20', iconColor: 'text-purple-600' },
          { label: 'Providers', value: providers?.length ?? 0, icon: <Zap size={18} />, color: 'bg-brand-50 dark:bg-brand-900/20', iconColor: 'text-brand-500' },
          { label: 'Active Providers', value: activeProviders.length, icon: <Zap size={18} />, color: 'bg-success-50 dark:bg-success-900/20', iconColor: 'text-success-600' },
          { label: 'Generations', value: history?.total_count ?? history?.totalCount ?? 0, icon: <History size={18} />, color: 'bg-warning-50 dark:bg-warning-900/20', iconColor: 'text-warning-600' },
        ].map(s => (
          <div key={s.label} className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-gray-500 dark:text-gray-400">{s.label}</span>
              <div className={`w-9 h-9 rounded-lg ${s.color} flex items-center justify-center`}>
                <span className={s.iconColor}>{s.icon}</span>
              </div>
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Agents */}
        <div className="card">
          <div className="p-5 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2"><Bot size={16} /> Agents</h2>
            <Link href="/app/ai-agent/agents" className="text-xs text-brand-500 hover:underline flex items-center gap-1">Manage <ArrowRight size={12} /></Link>
          </div>
          <div className="p-5">
            {agentsLoading ? <LoadingSpinner /> : agentList.length === 0 ? (
              <div className="text-center py-8">
                <Bot size={32} className="mx-auto mb-2 text-gray-300" />
                <p className="text-sm text-gray-500 mb-4">No agents yet</p>
                <Link href="/app/ai-agent/agents">
                  <Button size="sm" icon={<Wand2 size={13} />}>Open agents</Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {agentList.slice(0, 5).map(agent => (
                  <Link
                    key={agent.id}
                    href={(agent as AIAgentConfig).kind === 'assistant' ? `/app/ai-agent/agents/${agent.id}` : `/app/ai-agent/run?config=${agent.id}`}
                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  >
                    <AgentAvatar
                      name={agent.name}
                      avatar={(agent as AIAgentConfig).avatar}
                      kind={(agent as AIAgentConfig).kind === 'assistant' ? 'assistant' : 'build'}
                      size="sm"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{agent.name}</p>
                      <p className="text-xs text-gray-500 truncate">
                        {(agent as AIAgentConfig).kind === 'assistant'
                          ? ((agent as AIAgentConfig).description || 'Chat assistant')
                          : ((agent as AIAgentConfig).repository_url || 'Build agent — no repository connected')}
                      </p>
                    </div>
                    <Badge variant={agent.isActive ? 'success' : 'gray'}>{agent.isActive ? 'Active' : 'Inactive'}</Badge>
                  </Link>
                ))}
                {agentList.length > 5 && <Link href="/app/ai-agent/agents" className="block text-center text-xs text-brand-500 hover:underline pt-2">View all {agents?.totalCount}</Link>}
              </div>
            )}
          </div>
        </div>

        {/* Recent History */}
        <div className="card">
          <div className="p-5 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2"><History size={16} /> Recent Generations</h2>
            <Link href="/app/ai-agent/history" className="text-xs text-brand-500 hover:underline">View all</Link>
          </div>
          <div className="p-5">
            {historyLoading ? <LoadingSpinner /> : !history?.items?.length ? (
              <p className="text-center text-sm text-gray-400 py-8">No generations yet</p>
            ) : (
              <div className="space-y-3">
                {history.items.map(h => (
                  <div key={h.id} className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-lg bg-brand-50 dark:bg-brand-900/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Zap size={12} className="text-brand-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-700 dark:text-gray-300 truncate">{h.feature_name || h.user_prompt}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-gray-400">{h.created_at ? formatDistanceToNow(new Date(h.created_at), { addSuffix: true }) : ''}</span>
                        {h.tokens_used != null && <span className="text-xs text-gray-400">&bull; {h.tokens_used} tokens</span>}
                        <Badge variant={statusBadgeVariant(h.status)}>{getUserStatusLabel(h.status)}</Badge>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick nav */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { href: '/app/ai-agent/agents',         label: 'Agents',         icon: <Bot size={18} />,        desc: 'Build agent + your chat assistants' },
          { href: '/app/ai-agent/run',             label: 'Generate Code',  icon: <Zap size={18} />,        desc: 'Create a new code generation' },
          { href: '/app/ai-agent/providers',      label: 'Providers',      icon: <Zap size={18} />,        desc: 'Manage AI providers' },
          { href: '/app/ai-agent/source-control', label: 'Source Control', icon: <History size={18} />,    desc: 'GitHub / GitLab config' },
        ].map(item => (
          <Link key={item.href} href={item.href} className="card p-4 hover:border-brand-300 dark:hover:border-brand-600 transition-colors">
            <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-900/20 flex items-center justify-center mb-3 text-brand-500">
              {item.icon}
            </div>
            <p className="text-sm font-medium text-gray-900 dark:text-white">{item.label}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{item.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
