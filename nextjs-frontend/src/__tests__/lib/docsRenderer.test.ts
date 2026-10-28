import { renderContent, slug } from '@/lib/docsRenderer'

function render(markdown: string): HTMLDivElement {
  const container = document.createElement('div')
  container.innerHTML = renderContent(markdown)
  return container
}

describe('docs markdown renderer', () => {
  it('preserves fenced code line breaks and leaves markdown inside code literal', () => {
    const code = '# comment\n\n**literal** and `literal`\n- item\n1. item\n> quote'
    const result = render('```bash\n' + code + '\n```\n\n## After code')
    expect(result.querySelector('pre code')?.textContent).toBe(code)
    expect(result.querySelector('pre')?.children).toHaveLength(1)
    expect(result.querySelector('pre')?.querySelector('h1, strong, blockquote, .docs-li, .docs-gap')).toBeNull()
    expect(result.querySelector('h2')?.id).toBe('after-code')
  })

  it('escapes ampersands and angle brackets without double-decoding entities', () => {
    const code = '<script>alert("test")</script>\na < b && c > d\n&lt;'
    const html = renderContent('```\n' + code + '\n```')
    expect(html).toContain('&lt;script&gt;')
    expect(html).toContain('&amp;&amp;')
    expect(html).toContain('&amp;lt;')
    const result = render('```\n' + code + '\n```')
    expect(result.querySelector('script')).toBeNull()
    expect(result.querySelector('pre code')?.textContent).toBe(code)
  })

  it('restores multiple fenced blocks independently', () => {
    const result = render('```txt\nfirst\nline\n```\n\nBetween\n\n```\nsecond\nline\n```')
    expect(Array.from(result.querySelectorAll('pre code'), node => node.textContent)).toEqual([
      'first\nline', 'second\nline',
    ])
    expect(result.textContent).toContain('Between')
  })

  it('renders headings with section anchors matching the table of contents', () => {
    const result = render('# Quick Start\n\n## 1. Get the code & start it!')
    expect(result.querySelector('h1')?.textContent).toBe('Quick Start')
    const heading = result.querySelector('h2')
    expect(heading?.textContent).toBe('1. Get the code & start it!')
    expect(heading?.id).toBe('1-get-the-code-start-it')
    expect(slug('1. Get the code & start it!')).toBe('1-get-the-code-start-it')
  })

  it('renders table headers and body rows, including inline formatting', () => {
    const result = render('| To | Run |\n|---|---|\n| **Stop** | `docker compose down` |\n| Start | `docker compose up` |')
    expect(result.querySelector('.docs-table table')).not.toBeNull()
    expect(Array.from(result.querySelectorAll('thead th'), cell => cell.textContent)).toEqual(['To', 'Run'])
    expect(Array.from(result.querySelectorAll('tbody tr'), row =>
      Array.from(row.querySelectorAll('td'), cell => cell.textContent)
    )).toEqual([['Stop', 'docker compose down'], ['Start', 'docker compose up']])
    expect(result.querySelector('tbody strong')?.textContent).toBe('Stop')
    expect(result.querySelector('tbody code')?.textContent).toBe('docker compose down')
  })

  it('renders numbered and bulleted lists, emphasis, inline code and blockquotes', () => {
    const result = render('1. **First**\n2. `Second`\n\n- Bullet\n\n> A **note** with `code`')
    expect(Array.from(result.querySelectorAll('.docs-li'), item =>
      Array.from(item.children, child => child.textContent)
    )).toEqual([['1.', 'First'], ['2.', 'Second'], ['–', 'Bullet']])
    expect(result.querySelector('.docs-li strong')?.textContent).toBe('First')
    expect(result.querySelector('.docs-li code')?.textContent).toBe('Second')
    expect(result.querySelector('blockquote strong')?.textContent).toBe('note')
    expect(result.querySelector('blockquote code')?.textContent).toBe('code')
  })
})
