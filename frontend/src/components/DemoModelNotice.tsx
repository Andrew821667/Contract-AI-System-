import Link from 'next/link'
import { SparklesIcon } from '@heroicons/react/24/outline'
import { DEMO_MODEL_NOTE, DEMO_MODEL_NOTE_SHORT, DEMO_MODEL_NOTE_TITLE } from '@/utils/demoModel'

/**
 * Примечание клиенту о модели в демо: показывается на активации, в
 * приветствии и рядом с лимитами. Один текст — см. utils/demoModel.
 */
export default function DemoModelNotice({ variant = 'card' }: { variant?: 'card' | 'compact' }) {
  if (variant === 'compact') {
    return (
      <p className="mt-3 text-xs leading-relaxed text-gray-500 dark:text-gray-400" data-testid="demo-model-notice">
        {DEMO_MODEL_NOTE_SHORT}{' '}
        <Link className="font-semibold text-primary-700 hover:underline dark:text-primary-300" href="/pricing">
          Тарифы
        </Link>
      </p>
    )
  }
  return (
    <div
      className="flex gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-900"
      data-testid="demo-model-notice"
      role="note"
    >
      <SparklesIcon aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
      <div>
        <p className="font-semibold">{DEMO_MODEL_NOTE_TITLE}</p>
        <p className="mt-1">{DEMO_MODEL_NOTE}</p>
      </div>
    </div>
  )
}
