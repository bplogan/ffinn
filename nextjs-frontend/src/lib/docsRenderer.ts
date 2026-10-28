export const slug = (h: string) => h.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')

/** Tiny renderer for the in-page docs. Styling lives in `.docs-prose` (globals.css) so it follows the theme. */
export function renderContent(md: string): string {
  // Set code blocks aside first so the rules below can't touch them: no headings
  // from `# comments`, and their newlines survive the final newline collapse.
  const blocks: string[] = []
  const escape = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return md
    .replace(/```(\w+)?\n?([\s\S]+?)```/g, (_, _lang, code: string) => {
      blocks.push(`<pre><code>${escape(code.replace(/\n$/, ''))}</code></pre>`)
      return `\u0000${blocks.length - 1}\u0000`
    })
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^## (.+)$/gm, (_, h: string) => `<h2 id="${slug(h)}">${h}</h2>`)
    .replace(/\|([^\n]+)\|\n\|[-| :]+\|\n((?:\|[^\n]+\|\n?)*)/g, (_, head: string, body: string) => {
      const th = head.split('|').filter(Boolean).map(c => `<th>${c.trim()}</th>`).join('')
      const rows = body.trim().split('\n').map(r => `<tr>${r.split('|').filter(Boolean).map(c => `<td>${c.trim()}</td>`).join('')}</tr>`).join('')
      return `<div class="docs-table"><table><thead><tr>${th}</tr></thead><tbody>${rows}</tbody></table></div>`
    })
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^(\d+)\. (.+)$/gm, '<div class="docs-li"><span>$1.</span><span>$2</span></div>')
    .replace(/^- (.+)$/gm, '<div class="docs-li"><span>–</span><span>$1</span></div>')
    .replace(/\n\n/g, '<div class="docs-gap"></div>')
    .replace(/\n/g, ' ')
    .replace(/\u0000(\d+)\u0000/g, (_, i: string) => blocks[Number(i)])
}
