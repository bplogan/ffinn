'use client'

import { memo, useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Check, Copy } from 'lucide-react'
import 'highlight.js/styles/github-dark.css'

function CodeBlock({ className, children }: { className?: string; children?: ReactNode }) {
  const [copied, setCopied] = useState(false)
  const lang = /language-(\w+)/.exec(className ?? '')?.[1]
  const text = extractText(children)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard unavailable */ }
  }
  return (
    <div className="group relative my-3 rounded-xl overflow-hidden border border-white/10 bg-[#0d1117] text-[13px]">
      <div className="flex items-center justify-between px-3 py-1.5 bg-white/5 text-[11px] uppercase tracking-wider text-gray-400">
        <span>{lang ?? 'code'}</span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 hover:bg-white/10 hover:text-white transition-colors normal-case tracking-normal"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}{copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="!m-0 !bg-transparent overflow-x-auto p-3"><code className={className}>{children}</code></pre>
    </div>
  )
}

function extractText(node: ReactNode): string {
  if (node == null || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(extractText).join('')
  if (typeof node === 'object' && 'props' in node) {
    return extractText((node as { props: { children?: ReactNode } }).props.children)
  }
  return ''
}

/** Renders assistant replies: GitHub-flavoured markdown with highlighted, copyable code. */
function MarkdownInner({ children }: { children: string }) {
  return (
    <div className="chat-markdown text-[15px] leading-7 text-gray-800 dark:text-gray-100 break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: false, ignoreMissing: true }]]}
        components={{
          pre: ({ children }) => <>{children}</>,
          code: ({ className, children, ...rest }) => {
            const inline = !/language-/.test(className ?? '') && !String(children).includes('\n')
            if (inline) {
              return (
                <code
                  {...rest}
                  className="rounded-md bg-gray-200/70 dark:bg-white/10 px-1.5 py-0.5 text-[13px] font-mono text-pink-700 dark:text-pink-300"
                >
                  {children}
                </code>
              )
            }
            return <CodeBlock className={className}>{children}</CodeBlock>
          },
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand-600 dark:text-brand-400 underline underline-offset-2">
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
              <table className="min-w-full text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="bg-gray-50 dark:bg-gray-800 px-3 py-2 text-left font-semibold">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 border-t border-gray-100 dark:border-gray-800 align-top">{children}</td>,
          ul: ({ children }) => <ul className="my-2 ml-5 list-disc space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 ml-5 list-decimal space-y-1">{children}</ol>,
          h1: ({ children }) => <h1 className="mt-4 mb-2 text-xl font-bold">{children}</h1>,
          h2: ({ children }) => <h2 className="mt-4 mb-2 text-lg font-bold">{children}</h2>,
          h3: ({ children }) => <h3 className="mt-3 mb-1.5 text-base font-semibold">{children}</h3>,
          p: ({ children }) => <p className="my-2">{children}</p>,
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-4 border-brand-300 dark:border-brand-700 pl-3 text-gray-600 dark:text-gray-300 italic">{children}</blockquote>
          ),
          hr: () => <hr className="my-4 border-gray-200 dark:border-gray-700" />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}

export default memo(MarkdownInner)
