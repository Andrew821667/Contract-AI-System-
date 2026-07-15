import BrandMark from './BrandMark'

interface BrandLockupProps {
  compact?: boolean
  dark?: boolean
  className?: string
}

export default function BrandLockup({ compact = false, dark = false, className = '' }: BrandLockupProps) {
  return (
    <span className={`inline-flex items-center gap-3 ${className}`}>
      <BrandMark size={compact ? 36 : 42} title="AI Verdict" />
      <span className="min-w-0 leading-tight">
        <span className={`block font-bold tracking-tight ${compact ? 'text-base' : 'text-lg'} ${dark ? 'text-white' : 'text-slate-900'}`}>
          Contract AI
        </span>
        <span className={`block text-[10px] font-semibold uppercase tracking-[0.18em] ${dark ? 'text-cyan-300' : 'text-cyan-700'}`}>
          by AI Verdict
        </span>
      </span>
    </span>
  )
}
