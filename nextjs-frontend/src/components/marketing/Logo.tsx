import Image from 'next/image'

/** ffinn mark + wordmark. The mark is a black SVG, inverted for dark mode. */
export function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <Image src="/ffinn-icon.svg" alt="" width={30} height={30} className="dark:invert" priority />
      <span className="font-display text-[26px] font-semibold tracking-[-0.04em]">ffinn</span>
    </span>
  )
}
