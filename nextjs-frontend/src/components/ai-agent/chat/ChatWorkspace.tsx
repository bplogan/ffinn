'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import { formatDistanceToNow } from 'date-fns'
import {
  ArrowUp, Check, FileText, Image as ImageIcon, Loader2, MessageSquarePlus, Paperclip, Pencil,
  PanelLeftClose, PanelLeftOpen, Settings2, Square, Trash2, X, AlertCircle, RotateCcw,
} from 'lucide-react'
import Button from '@/components/ui/Button'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import AgentAvatar from '@/components/ai-agent/AgentAvatar'
import Markdown from '@/components/ai-agent/chat/Markdown'
import { aiChatApi } from '@/lib/api'
import type { AIAgentConfig, AIProvider, ChatAttachmentSummary, ChatConversation, ChatMessage } from '@/types'

interface Props {
  agent: AIAgentConfig
  provider?: AIProvider
  onEditAgent: () => void
}

interface PendingFile {
  localId: string
  file: File
  status: 'uploading' | 'ready' | 'failed'
  summary?: ChatAttachmentSummary
  error?: string
}

const MAX_FILES = 10
const MAX_FILE_MB = 20

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export default function ChatWorkspace({ agent, provider, onEditAgent }: Props) {
  const qc = useQueryClient()
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [files, setFiles] = useState<PendingFile[]>([])
  const [streaming, setStreaming] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const stickToBottom = useRef(true)
  // Set when send() creates the thread itself, so the load effect doesn't wipe the live bubbles.
  const skipNextLoad = useRef(false)

  const convosKey = useMemo(() => ['ai-chat-conversations', agent.id], [agent.id])
  const { data: conversations = [], isLoading: convosLoading } = useQuery<ChatConversation[]>({
    queryKey: convosKey,
    queryFn: () => aiChatApi.listConversations(agent.id),
  })

  // Load the active thread's messages whenever it changes (not while a reply is streaming).
  useEffect(() => {
    if (!activeId) { setMessages([]); return }
    if (skipNextLoad.current) { skipNextLoad.current = false; return }
    let cancelled = false
    aiChatApi.getConversation(activeId)
      .then(c => { if (!cancelled) setMessages(c.messages) })
      .catch(() => { if (!cancelled) toast.error('Could not load this conversation.') })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId])

  // Auto-scroll while new content arrives, unless the user scrolled up.
  useEffect(() => {
    const el = scrollRef.current
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight
  }, [messages])

  const onScroll = () => {
    const el = scrollRef.current
    if (!el) return
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  // Grow the composer with its content, up to a cap.
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = '0px'
    ta.style.height = `${Math.min(ta.scrollHeight, 220)}px`
  }, [draft])

  const newChat = () => {
    if (streaming) return
    setActiveId(null)
    setMessages([])
    setFiles([])
    textareaRef.current?.focus()
  }

  const renameMut = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => aiChatApi.renameConversation(id, title),
    onSuccess: () => { qc.invalidateQueries({ queryKey: convosKey }); setRenamingId(null) },
    onError: () => toast.error('Rename failed'),
  })
  const deleteMut = useMutation({
    mutationFn: (id: string) => aiChatApi.deleteConversation(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: convosKey })
      if (activeId === id) newChat()
      setDeleteId(null)
    },
    onError: () => toast.error('Delete failed'),
  })

  // ── attachments ──
  const addFiles = useCallback((incoming: FileList | File[]) => {
    const list = Array.from(incoming)
    if (!list.length) return
    if (files.length + list.length > MAX_FILES) {
      toast.error(`You can attach up to ${MAX_FILES} files per message.`)
      return
    }
    for (const file of list) {
      if (file.size > MAX_FILE_MB * 1024 * 1024) {
        toast.error(`${file.name} is larger than ${MAX_FILE_MB} MB.`)
        continue
      }
      const localId = `${Date.now()}-${Math.random().toString(36).slice(2)}`
      setFiles(f => [...f, { localId, file, status: 'uploading' }])
      aiChatApi.uploadAttachment(file)
        .then(summary => setFiles(f => f.map(x => x.localId === localId ? { ...x, status: 'ready', summary } : x)))
        .catch((err) => {
          const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          setFiles(f => f.map(x => x.localId === localId ? { ...x, status: 'failed', error: detail || 'Upload failed' } : x))
        })
    }
  }, [files.length])

  const onPaste = (e: React.ClipboardEvent) => {
    const items = Array.from(e.clipboardData.files)
    if (items.length) { e.preventDefault(); addFiles(items) }
  }

  // ── sending ──
  const canSend = !streaming && (draft.trim().length > 0 || files.some(f => f.status === 'ready')) && !files.some(f => f.status === 'uploading')

  const send = async () => {
    if (!canSend) return
    const content = draft.trim()
    const attachmentIds = files.filter(f => f.status === 'ready' && f.summary).map(f => f.summary!.id)
    const attachmentSummaries = files.filter(f => f.status === 'ready' && f.summary).map(f => f.summary!)
    setDraft('')
    setFiles([])
    setStreaming(true)
    stickToBottom.current = true

    let convoId = activeId
    try {
      if (!convoId) {
        const created = await aiChatApi.createConversation(agent.id)
        convoId = created.id
        skipNextLoad.current = true
        setActiveId(created.id)
        qc.setQueryData<ChatConversation[]>(convosKey, old => [created, ...(old ?? [])])
      }
    } catch (err) {
      setStreaming(false)
      setDraft(content)
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || 'Could not start a conversation.')
      return
    }

    // Optimistic user bubble + empty assistant bubble that fills as tokens arrive.
    const tempUserId = `temp-user-${Date.now()}`
    const tempAssistantId = `temp-assistant-${Date.now()}`
    setMessages(m => [
      ...m,
      { id: tempUserId, role: 'user', content, attachments: attachmentSummaries, created_at: new Date().toISOString() },
      { id: tempAssistantId, role: 'assistant', content: '', attachments: [], streaming: true },
    ])

    const controller = new AbortController()
    abortRef.current = controller
    try {
      await aiChatApi.sendMessage(convoId, { content, attachment_ids: attachmentIds }, (event) => {
        switch (event.type) {
          case 'user_message':
            setMessages(m => m.map(x => x.id === tempUserId ? event.message : x))
            qc.setQueryData<ChatConversation[]>(convosKey, old =>
              (old ?? []).map(c => c.id === convoId ? { ...c, title: event.title, updated_at: new Date().toISOString() } : c))
            break
          case 'token':
            setMessages(m => m.map(x => x.id === tempAssistantId ? { ...x, content: x.content + event.text } : x))
            break
          case 'done':
            setMessages(m => m.map(x => x.id === tempAssistantId ? { ...event.message, streaming: false } : x))
            break
          case 'error':
            setMessages(m => m.map(x => x.id === tempAssistantId ? { ...x, streaming: false, error: event.message } : x))
            break
        }
      }, controller.signal)
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        setMessages(m => m.map(x => x.id === tempAssistantId ? { ...x, streaming: false, content: x.content || '', error: x.content ? undefined : 'Stopped.' } : x))
      } else {
        setMessages(m => m.map(x => x.id === tempAssistantId ? { ...x, streaming: false, error: (err as Error).message || 'The reply failed.' } : x))
      }
    } finally {
      abortRef.current = null
      setStreaming(false)
      qc.invalidateQueries({ queryKey: convosKey })
    }
  }

  const stop = () => abortRef.current?.abort()

  const retryLast = () => {
    const lastUser = [...messages].reverse().find(m => m.role === 'user')
    if (!lastUser || streaming) return
    setDraft(lastUser.content)
    textareaRef.current?.focus()
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  const providerLabel = provider
    ? `${provider.display_name || provider.provider_name}${agent.ai_model || provider.model_name ? ` · ${agent.ai_model || provider.model_name}` : ''}`
    : 'No provider linked'

  return (
    <div
      className={clsx(
        'relative flex h-[calc(100vh-7.5rem)] min-h-[520px] overflow-hidden rounded-2xl border border-gray-200/80 dark:border-gray-700/60 bg-white dark:bg-gray-900 shadow-sm',
        dragOver && 'ring-2 ring-brand-500',
      )}
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={e => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files) }}
    >
      {/* ── Conversations ── */}
      <aside
        className={clsx(
          'flex flex-col border-r border-gray-200/80 dark:border-gray-700/60 bg-gray-50/80 dark:bg-gray-950/40 transition-[width] duration-200',
          sidebarOpen ? 'w-64' : 'w-0 overflow-hidden border-r-0',
        )}
      >
        <div className="p-3">
          <Button className="w-full justify-start" variant="secondary" icon={<MessageSquarePlus size={15} />} onClick={newChat} disabled={streaming}>
            New chat
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
          {convosLoading && <p className="px-3 py-2 text-xs text-gray-400">Loading…</p>}
          {!convosLoading && conversations.length === 0 && (
            <p className="px-3 py-6 text-xs text-gray-400 text-center">Your chats with {agent.name} will appear here.</p>
          )}
          {conversations.map(c => {
            const active = c.id === activeId
            return (
              <div
                key={c.id}
                className={clsx(
                  'group flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm cursor-pointer',
                  active ? 'bg-white dark:bg-gray-800 shadow-sm text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-300 hover:bg-white/70 dark:hover:bg-gray-800/60',
                )}
                onClick={() => { if (!streaming && renamingId !== c.id) setActiveId(c.id) }}
              >
                {renamingId === c.id ? (
                  <form
                    className="flex-1 flex items-center gap-1"
                    onSubmit={e => { e.preventDefault(); renameMut.mutate({ id: c.id, title: renameValue }) }}
                  >
                    <input
                      autoFocus
                      value={renameValue}
                      onChange={e => setRenameValue(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Escape') setRenamingId(null) }}
                      className="flex-1 min-w-0 rounded-md border border-brand-400 bg-white dark:bg-gray-900 px-1.5 py-0.5 text-sm focus:outline-none"
                    />
                    <button type="submit" className="p-1 text-brand-600"><Check size={13} /></button>
                  </form>
                ) : (
                  <>
                    <span className="flex-1 truncate">{c.title}</span>
                    <button
                      type="button"
                      title="Rename"
                      onClick={e => { e.stopPropagation(); setRenamingId(c.id); setRenameValue(c.title) }}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                    >
                      <Pencil size={12} />
                    </button>
                    <button
                      type="button"
                      title="Delete"
                      onClick={e => { e.stopPropagation(); setDeleteId(c.id) }}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded text-gray-400 hover:text-error-500"
                    >
                      <Trash2 size={12} />
                    </button>
                  </>
                )}
              </div>
            )
          })}
        </div>
      </aside>

      {/* ── Thread ── */}
      <section className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center gap-3 px-4 py-3 border-b border-gray-200/80 dark:border-gray-700/60">
          <button
            type="button"
            onClick={() => setSidebarOpen(s => !s)}
            className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
            title={sidebarOpen ? 'Hide conversations' : 'Show conversations'}
          >
            {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
          </button>
          <AgentAvatar name={agent.name} avatar={agent.avatar} size="sm" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{agent.name}</p>
            <p className="text-[11px] text-gray-500 dark:text-gray-400 truncate">{providerLabel}</p>
          </div>
          <Button size="sm" variant="ghost" icon={<Settings2 size={14} />} onClick={onEditAgent}>Edit agent</Button>
        </header>

        <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <EmptyThread agent={agent} onPick={text => { setDraft(text); textareaRef.current?.focus() }} />
          ) : (
            <div className="mx-auto max-w-3xl px-4 py-6 space-y-6">
              {messages.map(m => <MessageRow key={m.id} message={m} agent={agent} onRetry={retryLast} />)}
            </div>
          )}
        </div>

        {/* ── Composer ── */}
        <div className="px-4 pb-4 pt-2">
          <div className="mx-auto max-w-3xl">
            {files.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {files.map(f => (
                  <div
                    key={f.localId}
                    className={clsx(
                      'flex items-center gap-2 rounded-xl border px-2.5 py-1.5 text-xs',
                      f.status === 'failed'
                        ? 'border-error-300 bg-error-50 text-error-700 dark:bg-error-900/20 dark:text-error-300'
                        : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-200',
                    )}
                  >
                    {f.status === 'uploading' ? <Loader2 size={13} className="animate-spin" /> : f.file.type.startsWith('image/') ? <ImageIcon size={13} /> : <FileText size={13} />}
                    <span className="max-w-[160px] truncate">{f.file.name}</span>
                    <span className="text-gray-400">{formatBytes(f.file.size)}</span>
                    {f.status === 'failed' && <span title={f.error}>· {f.error}</span>}
                    {f.status === 'ready' && f.summary && f.summary.readable === false && (
                      <span className="text-amber-600" title="This file type cannot be read as text; the agent will only see its name.">· not readable</span>
                    )}
                    <button type="button" onClick={() => setFiles(x => x.filter(y => y.localId !== f.localId))} className="text-gray-400 hover:text-gray-700 dark:hover:text-white">
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex items-end gap-2 rounded-2xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 shadow-sm focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20 transition">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={e => { if (e.target.files) addFiles(e.target.files); e.target.value = '' }}
              />
              <button
                type="button"
                title="Attach files"
                onClick={() => fileInputRef.current?.click()}
                className="p-2 rounded-xl text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-white"
              >
                <Paperclip size={18} />
              </button>
              <textarea
                ref={textareaRef}
                rows={1}
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={onKeyDown}
                onPaste={onPaste}
                placeholder={`Message ${agent.name}…`}
                className="flex-1 resize-none bg-transparent py-2 text-[15px] leading-6 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none max-h-[220px]"
              />
              {streaming ? (
                <button type="button" onClick={stop} title="Stop" className="p-2 rounded-xl bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:opacity-90">
                  <Square size={16} fill="currentColor" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={send}
                  disabled={!canSend}
                  title="Send (Enter)"
                  className="p-2 rounded-xl bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-30 disabled:cursor-not-allowed transition"
                >
                  <ArrowUp size={18} />
                </button>
              )}
            </div>
            <p className="mt-1.5 text-center text-[11px] text-gray-400">
              Enter to send · Shift+Enter for a new line · drop or paste files to attach
            </p>
          </div>
        </div>
      </section>

      {dragOver && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-brand-500/5 backdrop-blur-[1px]">
          <div className="rounded-2xl border-2 border-dashed border-brand-500 bg-white/90 dark:bg-gray-900/90 px-6 py-4 text-sm font-semibold text-brand-600">
            Drop files to attach
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={() => deleteId && deleteMut.mutate(deleteId)}
        loading={deleteMut.isPending}
        title="Delete conversation"
        message="This removes the conversation and any files you attached to it."
        confirmLabel="Delete"
      />
    </div>
  )
}

// ── Pieces ───────────────────────────────────────────────────────────────────

function EmptyThread({ agent, onPick }: { agent: AIAgentConfig; onPick: (text: string) => void }) {
  const suggestions = [
    'Give me a quick summary of what you can help with.',
    'I will paste some text — tell me the three most important points.',
    'Review the file I attach and list anything that looks wrong.',
  ]
  return (
    <div className="h-full flex flex-col items-center justify-center px-6 text-center">
      <AgentAvatar name={agent.name} avatar={agent.avatar} size="xl" className="mb-4" />
      <h2 className="text-xl font-bold text-gray-900 dark:text-white">{agent.name}</h2>
      {agent.description && <p className="mt-1 max-w-md text-sm text-gray-500 dark:text-gray-400">{agent.description}</p>}
      <div className="mt-8 grid gap-2 sm:grid-cols-3 w-full max-w-2xl">
        {suggestions.map(s => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3 text-left text-sm text-gray-600 dark:text-gray-300 hover:border-brand-300 hover:bg-brand-50/50 dark:hover:bg-brand-900/10 transition"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

function MessageRow({ message, agent, onRetry }: { message: ChatMessage; agent: AIAgentConfig; onRetry: () => void }) {
  const isUser = message.role === 'user'
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] space-y-2">
          {message.attachments?.length > 0 && (
            <div className="flex flex-wrap justify-end gap-2">
              {message.attachments.map(a => <AttachmentChip key={a.id} att={a} />)}
            </div>
          )}
          {message.content && (
            <div className="rounded-2xl rounded-br-md bg-brand-500 px-4 py-2.5 text-[15px] leading-7 text-white whitespace-pre-wrap break-words shadow-sm">
              {message.content}
            </div>
          )}
        </div>
      </div>
    )
  }
  return (
    <div className="flex gap-3">
      <AgentAvatar name={agent.name} avatar={agent.avatar} size="sm" className="mt-1" />
      <div className="flex-1 min-w-0">
        {message.content ? <Markdown>{message.content}</Markdown> : message.streaming ? (
          <div className="flex items-center gap-1 py-3 text-gray-400">
            <span className="h-2 w-2 rounded-full bg-current animate-bounce [animation-delay:-0.3s]" />
            <span className="h-2 w-2 rounded-full bg-current animate-bounce [animation-delay:-0.15s]" />
            <span className="h-2 w-2 rounded-full bg-current animate-bounce" />
          </div>
        ) : null}
        {message.streaming && message.content && (
          <span className="inline-block w-2 h-4 -mb-0.5 bg-gray-400 animate-pulse rounded-sm" />
        )}
        {message.error && (
          <div className="mt-2 flex items-start gap-2 rounded-xl border border-error-200 dark:border-error-800 bg-error-50 dark:bg-error-900/20 px-3 py-2 text-sm text-error-700 dark:text-error-300">
            <AlertCircle size={15} className="mt-0.5 flex-shrink-0" />
            <span className="flex-1">{message.error}</span>
            <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 text-xs font-medium hover:underline">
              <RotateCcw size={12} /> Retry
            </button>
          </div>
        )}
        {!message.streaming && !message.error && (message.model || message.tokens_used != null || message.created_at) && (
          <p className="mt-1 text-[11px] text-gray-400">
            {[message.model, message.tokens_used != null ? `${message.tokens_used} tokens` : null,
              message.created_at ? formatDistanceToNow(new Date(message.created_at), { addSuffix: true }) : null]
              .filter(Boolean).join(' · ')}
          </p>
        )}
      </div>
    </div>
  )
}

function AttachmentChip({ att }: { att: ChatAttachmentSummary }) {
  const isImage = att.content_type.startsWith('image/')
  return (
    <a
      href={aiChatApi.attachmentUrl(att.id)}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 rounded-xl border border-brand-200 dark:border-brand-800 bg-brand-50 dark:bg-brand-900/20 px-2.5 py-1.5 text-xs text-brand-800 dark:text-brand-200 hover:bg-brand-100 dark:hover:bg-brand-900/40"
      title="Open attachment"
    >
      {isImage ? <ImageIcon size={13} /> : <FileText size={13} />}
      <span className="max-w-[180px] truncate">{att.filename}</span>
      <span className="text-brand-500/70">{formatBytes(att.size_bytes)}</span>
    </a>
  )
}
