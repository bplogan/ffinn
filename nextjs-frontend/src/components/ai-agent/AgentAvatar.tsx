import { clsx } from 'clsx'
import { Hammer } from 'lucide-react'
import { avatarStyle, monogram } from '@/lib/agentAvatars'

interface Props {
  name?: string | null
  avatar?: string | null
  kind?: 'build' | 'assistant'
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
}

const SIZES = {
  sm: 'w-7 h-7 text-[10px] rounded-lg',
  md: 'w-9 h-9 text-xs rounded-xl',
  lg: 'w-12 h-12 text-sm rounded-2xl',
  xl: 'w-16 h-16 text-lg rounded-2xl',
}
const ICON = { sm: 13, md: 16, lg: 20, xl: 28 }

export default function AgentAvatar({ name, avatar, kind = 'assistant', size = 'md', className }: Props) {
  const style = avatarStyle(kind === 'build' ? 'build' : avatar)
  return (
    <div
      aria-hidden
      className={clsx(
        'flex items-center justify-center flex-shrink-0 font-black tracking-wide text-white',
        'bg-gradient-to-br shadow-md shadow-black/10 ring-1 ring-white/20',
        style.gradient, SIZES[size], className,
      )}
    >
      {kind === 'build' ? <Hammer size={ICON[size]} /> : monogram(name)}
    </div>
  )
}
