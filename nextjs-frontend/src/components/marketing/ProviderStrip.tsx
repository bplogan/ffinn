'use client'
import { Server } from 'lucide-react'
import { SiAnthropic, SiGithub, SiGooglegemini, SiOllama, SiOpenai } from 'react-icons/si'
import { VscAzure } from 'react-icons/vsc'

// Client-only because react-icons relies on React context.
const providers = [
  { name: 'OpenAI', icon: <SiOpenai /> },
  { name: 'Claude', icon: <SiAnthropic /> },
  { name: 'Gemini', icon: <SiGooglegemini /> },
  { name: 'Azure OpenAI', icon: <VscAzure /> },
  { name: 'GitHub Models', icon: <SiGithub /> },
  { name: 'Ollama', icon: <SiOllama /> },
  { name: 'OpenAI-compatible', icon: <Server size={17} strokeWidth={1.75} /> },
]

export default function ProviderStrip() {
  return (
    <ul className="flex flex-wrap items-center justify-center gap-x-8 gap-y-4 text-ink-soft sm:gap-x-10">
      {providers.map(p => (
        <li key={p.name} className="flex items-center gap-2 text-[15px] font-medium tracking-[-0.01em]">
          <span className="text-[18px] text-ink" aria-hidden>{p.icon}</span>
          {p.name}
        </li>
      ))}
    </ul>
  )
}
