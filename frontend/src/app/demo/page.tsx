'use client'

import { Suspense, useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { motion } from 'framer-motion'
import { toast } from 'react-hot-toast'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import api from '@/services/api'

function DemoForm() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [token, setToken] = useState('')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const urlToken = searchParams.get('token')
    if (urlToken) {
      setToken(urlToken)
    }
  }, [searchParams])

  const handleActivate = async () => {
    if (!token || !email || !name) {
      toast.error('Заполните все поля')
      return
    }

    setLoading(true)
    try {
      await api.activateDemo({ token, email, name })
      toast.success('Демо-доступ активирован!')
      router.push('/dashboard')
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Ошибка активации демо-доступа'
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-lg"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-primary-600 rounded-2xl shadow-sm flex items-center justify-center mx-auto mb-4">
            <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          </div>
          <h1 className="text-3xl font-bold text-stone-800 mb-2">
            Contract AI — Демо
          </h1>
          <p className="text-gray-600">
            Активируйте демо-доступ для тестирования системы
          </p>
        </div>

        {/* Activation Form */}
        <Card>
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Демо-токен
              </label>
              <input
                type="text"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Вставьте токен из ссылки..."
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Имя
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Иван Петров"
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
              />
            </div>

            <Button
              onClick={handleActivate}
              loading={loading}
              disabled={!token || !email || !name}
              className="w-full"
            >
              Активировать демо-доступ
            </Button>
          </div>
        </Card>

        {/* Demo Limitations */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mt-6"
        >
          <Card className="bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200">
            <h3 className="font-bold text-amber-800 mb-3">
              Ограничения демо-режима
            </h3>
            <ul className="space-y-2 text-sm text-amber-700">
              <li className="flex items-center gap-2">
                <span>📄</span>
                <span>До 3 договоров в день</span>
              </li>
              <li className="flex items-center gap-2">
                <span>🤖</span>
                <span>До 10 LLM-запросов в день</span>
              </li>
              <li className="flex items-center gap-2">
                <span>⏰</span>
                <span>Доступ ограничен по времени (см. токен)</span>
              </li>
              <li className="flex items-center gap-2">
                <span>📊</span>
                <span>Полный анализ и генерация договоров</span>
              </li>
            </ul>
          </Card>
        </motion.div>

        {/* Back to login */}
        <div className="text-center mt-6">
          <button
            onClick={() => router.push('/login')}
            className="text-primary-600 hover:text-primary-700 text-sm font-medium"
          >
            Уже есть аккаунт? Войти
          </button>
        </div>
      </motion.div>
    </div>
  )
}

export default function DemoPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Загрузка...</div>
      </div>
    }>
      <DemoForm />
    </Suspense>
  )
}
