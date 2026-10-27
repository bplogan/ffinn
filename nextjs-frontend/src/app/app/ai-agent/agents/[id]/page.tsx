'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import Breadcrumb from '@/components/ui/Breadcrumb'
import ChatWorkspace from '@/components/ai-agent/chat/ChatWorkspace'
import AgentEditorModal from '@/components/ai-agent/AgentEditorModal'
import { aiAgentsApi, aiProvidersApi } from '@/lib/api'
import type { AIAgentConfig, AIProvider } from '@/types'

export default function AgentPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [editorOpen, setEditorOpen] = useState(false)

  const { data: agent, isLoading, isError } = useQuery<AIAgentConfig>({
    queryKey: ['ai-agent-config', id],
    queryFn: () => aiAgentsApi.get(id) as Promise<AIAgentConfig>,
  })
  const { data: providers } = useQuery<AIProvider[]>({
    queryKey: ['ai-providers'],
    queryFn: () => aiProvidersApi.list() as Promise<AIProvider[]>,
  })

  // The build agent lives on the Generate page; this route is for assistants.
  useEffect(() => {
    if (agent && agent.kind !== 'assistant') router.replace(`/app/ai-agent/run?config=${agent.id}`)
  }, [agent, router])

  if (isLoading) return <LoadingSpinner fullPage />
  if (isError || !agent) {
    return (
      <div className="card p-8 text-center text-sm text-gray-500">
        This agent could not be found. <button className="text-brand-600 hover:underline" onClick={() => router.push('/app/ai-agent/agents')}>Back to agents</button>
      </div>
    )
  }
  if (agent.kind !== 'assistant') return <LoadingSpinner fullPage />

  return (
    <div className="space-y-3">
      <Breadcrumb crumbs={[{ label: 'AI Agent', href: '/app/ai-agent' }, { label: 'Agents', href: '/app/ai-agent/agents' }, { label: agent.name ?? 'Agent' }]} />
      <ChatWorkspace
        agent={agent}
        provider={providers?.find(p => p.id === agent.provider_id)}
        onEditAgent={() => setEditorOpen(true)}
      />
      <AgentEditorModal open={editorOpen} onClose={() => setEditorOpen(false)} agent={agent} />
    </div>
  )
}
