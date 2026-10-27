import Image from 'next/image'

/** ffinn mark + wordmark. The mark is a black SVG, inverted for dark mode. */
export function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <Image src="/ffinn-icon.svg" alt="" width={22} height={22} className="dark:invert" priority />
      <span className="font-display text-[19px] font-semibold tracking-[-0.04em]">ffinn</span>
    </span>
  )
}
