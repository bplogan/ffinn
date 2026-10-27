'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { auditLogsApi } from '@/lib/api'
import type { AuditLog, PagedResult } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import { FileText, Search } from 'lucide-react'
import { format } from 'date-fns'

export default function AuditLogListPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 25

  const { data, isLoading } = useQuery<PagedResult<AuditLog>>({
    queryKey: ['audit-logs', search, page],
    queryFn: () => auditLogsApi.list({ page: page + 1, page_size: PAGE_SIZE }) as Promise<PagedResult<AuditLog>>,
  })

  return (
    <div className="space-y-6">
      <PageHeader title="Audit Logs" subtitle="Track all actions performed in the system" />

      <div className="card p-4">
        <div className="relative max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => { setSearch(e.target.value); setPage(0) }} placeholder="Search by user, action…" className="input-field pl-9" />
        </div>
      </div>

      <div className="card">
        {isLoading ? <LoadingSpinner fullPage /> : !data?.items?.length ? (
          <EmptyState icon={<FileText size={40} />} title="No audit logs" />
        ) : (
          <div className="table-container">
            <table className="table">
              <thead><tr><th>Time</th><th>User</th><th>Service</th><th>Method</th><th>IP</th><th>Duration</th><th>Status</th></tr></thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {data.items.map(log => (
                  <tr key={log.id}>
                    <td className="text-xs whitespace-nowrap">{log.executionTime ? format(new Date(log.executionTime), 'MMM d, HH:mm:ss') : '—'}</td>
                    <td><span className="text-xs">{log.userName || <span className="text-gray-400">Anonymous</span>}</span></td>
                    <td><span className="font-mono text-xs">{log.serviceName}</span></td>
                    <td><span className="font-mono text-xs">{log.methodName}</span></td>
                    <td><span className="text-xs">{log.clientIpAddress}</span></td>
                    <td><span className="text-xs">{log.executionDuration}ms</span></td>
                    <td>
                      <Badge variant={log.exception ? 'error' : (log.httpStatusCode && log.httpStatusCode >= 400 ? 'warning' : 'success')}>
                        {log.httpStatusCode || (log.exception ? 'Error' : 'OK')}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && (data.total_count ?? data.totalCount ?? 0) > PAGE_SIZE && (
          <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between text-sm text-gray-500">
            <span>{data.total_count ?? data.totalCount ?? 0} total</span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>Previous</Button>
              <Button variant="secondary" size="sm" disabled={(page + 1) * PAGE_SIZE >= (data.total_count ?? data.totalCount ?? 0)} onClick={() => setPage(p => p + 1)}>Next</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
