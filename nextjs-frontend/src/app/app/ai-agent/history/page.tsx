'use client'
import { useQuery } from '@tanstack/react-query'
import { aiGenerationsApi } from '@/lib/api'
import type { AIGeneration, PagedResult } from '@/types'
import { useState } from 'react'
import PageHeader from '@/components/ui/PageHeader'
import Breadcrumb from '@/components/ui/Breadcrumb'
import Badge from '@/components/ui/Badge'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import { History, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import Link from 'next/link'

const PAGE_SIZE = 25

import { getUserStatusLabel, statusBadgeVariant } from '@/lib/generationStatus'

export default function AIHistoryPage() {
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery<PagedResult<AIGeneration>>({
    queryKey: ['ai-history', page, search],
    queryFn: () => aiGenerationsApi.list({ page: page + 1, page_size: PAGE_SIZE, filter: search }) as Promise<PagedResult<AIGeneration>>,
  })

  const items = data?.items ?? []
  const totalCount = data?.total_count ?? data?.totalCount ?? 0
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  return (
    <div className="space-y-4">
      <Breadcrumb crumbs={[{ label: 'AI Agent', href: '/app/ai-agent' }, { label: 'History' }]} />
      <PageHeader title="Generation History" subtitle="Review all AI code generation requests" />

      <div className="card overflow-hidden">
        <div className="p-4 border-b border-gray-100 dark:border-gray-700">
          <input value={search} onChange={e => { setSearch(e.target.value); setPage(0) }}
            placeholder="Search features or prompts…"
            className="input-field max-w-sm" />
        </div>

        {isLoading ? <LoadingSpinner className="my-8" /> : !items.length
          ? <EmptyState icon={<History size={32} />} title="No generations yet" description="Submit your first code generation request to get started" />
          : (
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Feature</th>
                    <th>Prompt</th>
                    <th>Model</th>
                    <th>Tokens</th>
                    <th>Status</th>
                    <th>PR</th>
                    <th>Date</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(h => (
                    <tr key={h.id}>
                      <td className="font-medium whitespace-nowrap">{h.feature_name ?? '—'}</td>
                      <td className="max-w-xs truncate text-gray-600 dark:text-gray-400 text-sm">{h.user_prompt}</td>
                      <td className="text-xs text-gray-500 whitespace-nowrap">{h.ai_model ?? '—'}</td>
                      <td>{h.tokens_used != null ? h.tokens_used.toLocaleString() : '—'}</td>
                      <td>
                        <Badge variant={statusBadgeVariant(h.status)}>{getUserStatusLabel(h.status)}</Badge>
                      </td>
                      <td>
                        {(h.pr_url ?? h.pull_request_url) ? (
                          <a href={(h.pr_url ?? h.pull_request_url)!} target="_blank" rel="noopener noreferrer"
                            className="flex items-center gap-1 text-xs text-brand-500 hover:underline">
                            PR #{h.pr_number ?? h.pull_request_number}
                            <ExternalLink size={11} />
                          </a>
                        ) : '—'}
                      </td>
                      <td className="text-sm text-gray-500 whitespace-nowrap">
                        {h.created_at ? formatDistanceToNow(new Date(h.created_at), { addSuffix: true }) : '—'}
                      </td>
                      <td>
                        <Link
                          href={`/app/ai-agent/run?gen=${h.id}${h.config_id ? `&config=${h.config_id}` : ''}`}
                          className="text-xs text-brand-500 hover:underline whitespace-nowrap"
                        >
                          Manage
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

        {totalPages > 1 && (
          <div className="p-4 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between">
            <p className="text-sm text-gray-500">Total: {totalCount.toLocaleString()} records</p>
            <div className="flex items-center gap-2">
              <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40">
                <ChevronLeft size={16} />
              </button>
              <span className="text-sm">{page + 1} / {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
                className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40">
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
