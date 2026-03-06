'use client'

import { useEffect } from 'react'
import Link from 'next/link'

export default function ContractsError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Contracts error:', error)
  }, [error])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8 text-center">
        <div className="text-red-500 text-5xl mb-4">!</div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Ошибка загрузки договоров
        </h2>
        <p className="text-gray-600 mb-6">
          Не удалось загрузить данные. Проверьте подключение и попробуйте снова.
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={reset}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Попробовать снова
          </button>
          <Link
            href="/dashboard"
            className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
          >
            На дашборд
          </Link>
        </div>
      </div>
    </div>
  )
}
