import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8 text-center">
        <div className="text-gray-400 text-6xl font-bold mb-4">404</div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Страница не найдена
        </h2>
        <p className="text-gray-600 mb-6">
          Запрашиваемая страница не существует или была перемещена.
        </p>
        <Link
          href="/"
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors inline-block"
        >
          На главную
        </Link>
      </div>
    </div>
  )
}
