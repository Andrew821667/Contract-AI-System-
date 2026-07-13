'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { useAuthStore } from '../stores/authStore'
import api from '@/services/api'
import toast from 'react-hot-toast'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'

const freeLimits = [
  { value: '0 ₽', label: 'стоимость бесплатного режима' },
  { value: '3', label: 'договора бесплатно в месяц' },
  { value: '5 МБ', label: 'размер одного файла' },
]

export default function Home() {
  const router = useRouter()

  // Login form state
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)

  useEffect(() => {
    const token = useAuthStore.getState().accessToken
    if (token) {
      router.replace('/dashboard')
    }
  }, [router])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoginLoading(true)
    try {
      const response = await api.login({ username: email, password })
      toast.success(`Добро пожаловать, ${response.user.name}!`, {
        style: { borderRadius: '12px', background: '#7d6744', color: '#fff' },
      })
      router.push('/dashboard')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || error.response?.data?.message || 'Неверный email или пароль', {
        style: { borderRadius: '12px' },
      })
    } finally {
      setLoginLoading(false)
    }
  }

  const features = [
    {
      icon: <svg className="h-7 w-7 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>,
      title: 'Цифровизация договоров',
      description: 'Криптографическая подпись, hash-chain версий, проверка целостности документа'
    },
    {
      icon: <svg className="h-7 w-7 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
      title: 'Smart Composer',
      description: 'AI-помощник при составлении: подсказки, валидация, 50+ шаблонов пунктов'
    },
    {
      icon: <svg className="h-7 w-7 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>,
      title: 'Двухуровневый анализ',
      description: 'Быстрый скрининг + глубокий анализ критичных рисков со ссылками на ГК РФ'
    },
    {
      icon: <svg className="h-7 w-7 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>,
      title: 'ML-предсказание рисков',
      description: 'Предварительная оценка помогает приоритизировать документы до полного AI-анализа'
    },
    {
      icon: <svg className="h-7 w-7 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>,
      title: 'Полный цикл',
      description: 'Генерация, анализ, разногласия, сравнение версий, экспорт — всё в одной системе'
    },
    {
      icon: <svg className="h-7 w-7 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>,
      title: 'Безопасность',
      description: 'On-premise для Enterprise, локальные AI-модели, данные не покидают периметр'
    }
  ]

  const advantages = [
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
      title: 'Бесплатный вход',
      description: 'Бесплатный вход — 3 договора в месяц, дальше пилот и рабочий контур под задачу.',
      gradient: 'from-emerald-500 to-teal-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
      title: 'Быстрый первый проход',
      description: 'Двухуровневый AI: предварительный скрининг и подробный анализ критичных рисков. Время зависит от объема документа.',
      gradient: 'from-blue-500 to-cyan-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>,
      title: 'Цифровизация договоров',
      description: 'Криптографическая подпись, hash-chain целостности, DAG для слияния правок.',
      gradient: 'from-violet-500 to-purple-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" /></svg>,
      title: 'Российское право',
      description: 'Ссылки на статьи ГК РФ и ФЗ. Типовые шаблоны российских договоров.',
      gradient: 'from-rose-500 to-red-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>,
      title: 'Smart Composer',
      description: 'AI-помощник при наборе текста: подсказки пунктов, валидация на лету.',
      gradient: 'from-indigo-500 to-violet-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>,
      title: 'RAG — база знаний',
      description: 'Система учится на ваших политиках, шаблонах и прецедентах.',
      gradient: 'from-teal-500 to-cyan-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>,
      title: 'Безопасность и On-premise',
      description: 'HTTPS, 4 уровня доступа, аудит-лог. Enterprise на вашем сервере.',
      gradient: 'from-primary-500 to-primary-700',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>,
      title: 'Аналитика и ROI',
      description: 'Дашборд: сколько договоров обработано, время и деньги сэкономлены.',
      gradient: 'from-amber-500 to-orange-600',
    },
  ]

  const stats = [
    { value: '3/мес', label: 'Договора бесплатно' },
    { value: '0 ₽', label: 'Стоимость первого шага' },
    { value: '2 уровня', label: 'Проверки рисков' },
    { value: '24/7', label: 'Доступность системы' }
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-700 via-slate-800 to-slate-900">
      {/* Навигация */}
      <nav className="bg-slate-800/95 backdrop-blur-lg shadow-lg border-b border-primary-600/30 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3"
            >
              <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-xl shadow-sm flex items-center justify-center">
                <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              </div>
              <span className="text-xl font-bold text-white">Contract AI</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-4"
            >
              <a href="#login" className="text-stone-300 hover:text-white transition text-sm font-medium">Вход</a>
              <a href="/demo" className="hidden text-stone-300 hover:text-white transition text-sm font-medium md:inline">Демо</a>
              <a href="#pricing" className="hidden text-stone-300 hover:text-white transition text-sm font-medium sm:inline">Тарифы</a>
              <Button variant="primary" size="sm" href="/register">
                3 договора бесплатно
              </Button>
            </motion.div>
          </div>
        </div>
      </nav>

      <main>
      {/* Hero Section с формой входа */}
      <section className="relative overflow-hidden py-16 px-4">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-20 right-20 w-96 h-96 bg-primary-500/10 rounded-full blur-3xl" />
          <div className="absolute bottom-10 left-10 w-72 h-72 bg-primary-400/10 rounded-full blur-3xl" />
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            {/* Левая часть — текст */}
            <div>
              <h1 className="text-5xl md:text-6xl font-bold mb-6 leading-tight">
                <span className="text-white">Анализ и проверка</span>{' '}
                <br />
                <span className="bg-gradient-to-r from-primary-300 to-primary-500 bg-clip-text text-transparent">договоров с ИИ</span>
              </h1>
              <p className="text-lg md:text-xl text-stone-300 mb-8 leading-relaxed">
                AI-система для анализа, генерации и управления юридическими договорами.
                Начните с 3 бесплатных договоров в месяц, чтобы проверить сценарий на практике.
              </p>

              {/* Мини-статистика */}
              <div className="grid grid-cols-2 gap-4">
                {[
                  { value: '2 уровня', label: 'анализа рисков' },
                  { value: '3/мес', label: 'бесплатно' },
                  { value: 'Юрист', label: 'подтверждает выводы' },
                  { value: 'On-premise', label: 'для Enterprise' },
                ].map((s, i) => (
                  <div key={i} className="bg-white/15 backdrop-blur-sm rounded-xl p-3 border border-white/20">
                    <div className="text-lg font-bold text-white">{s.value}</div>
                    <div className="text-xs text-primary-200">{s.label}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Правая часть — форма входа */}
            <motion.div
              id="login"
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              <div className="bg-slate-700/90 backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-primary-500/30">
                <div className="text-center mb-6">
                  <div className="w-16 h-16 mx-auto bg-gradient-to-br from-primary-500 to-primary-700 rounded-2xl shadow-lg flex items-center justify-center mb-4">
                    <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                  </div>
                  <h2 className="text-2xl font-bold text-stone-200">Вход в систему</h2>
                  <p className="text-stone-300 text-sm mt-1">
                    Нет аккаунта? <a href="/register" className="text-stone-300 font-semibold hover:underline">Начните бесплатно</a>: 3 договора в месяц.
                  </p>
                </div>

                <form onSubmit={handleLogin} className="space-y-4">
                  <div>
                    <label className="block text-sm font-semibold text-stone-300 mb-1.5">Email</label>
                    <input
                      type="text"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full px-4 py-3 bg-slate-800 border-2 border-stone-500 rounded-xl text-white placeholder-stone-500 focus:border-primary-500 focus:ring-4 focus:ring-primary-900 transition-all outline-none"
                      placeholder="user@example.com"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-stone-300 mb-1.5">Пароль</label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full px-4 py-3 bg-slate-800 border-2 border-stone-500 rounded-xl text-white placeholder-stone-500 focus:border-primary-500 focus:ring-4 focus:ring-primary-900 transition-all outline-none"
                      placeholder="••••••••"
                      required
                    />
                  </div>

                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    type="submit"
                    disabled={loginLoading}
                    className="w-full py-3.5 bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-700 hover:to-primary-800 text-white font-bold rounded-xl shadow-lg transition-all disabled:opacity-50"
                  >
                    {loginLoading ? (
                      <span className="flex items-center justify-center">
                        <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Вход...
                      </span>
                    ) : 'Войти'}
                  </motion.button>
                </form>

                <div className="mt-4 text-center">
                  <a
                    href="https://t.me/legal_ai_helper_new_bot"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-stone-300 hover:text-stone-300 hover:underline"
                  >
                    Забыли пароль?
                  </a>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      <section className="py-8 px-4">
        <div className="max-w-7xl mx-auto">
          <Card className="bg-slate-600/40 border-2 border-primary-500/30">
            <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-8 items-center">
              <div>
                <p className="text-sm font-semibold uppercase tracking-wide text-primary-300 mb-3">
                  Бесплатный режим
                </p>
                <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                  3 договора бесплатно каждый месяц
                </h2>
                <p className="text-lg text-stone-300">
                  Бесплатный режим нужен для спокойной проверки сценария: загрузить документ,
                  посмотреть структуру отчета и понять, подходит ли система под ваш процесс.
                  Оплата появляется только на следующем этапе — пилоте или рабочем контуре.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-4">
                {freeLimits.map((limit) => (
                  <div key={limit.label} className="rounded-2xl border border-primary-500/20 bg-slate-800/70 p-5">
                    <div className="text-3xl font-bold text-white">{limit.value}</div>
                    <div className="text-sm text-primary-300 mt-1">{limit.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* Как это работает */}
      <section className="py-12 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="relative bg-slate-600/30 backdrop-blur-xl rounded-3xl shadow-xl p-8 border border-primary-500/20">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <Card hover className="text-center bg-slate-600/50 border-primary-500/30">
                <div className="w-14 h-14 bg-slate-700/60 rounded-xl flex items-center justify-center mx-auto mb-3">
                  <svg className="h-7 w-7 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                </div>
                <h3 className="font-bold text-lg mb-2 text-stone-200">Загрузите</h3>
                <p className="text-sm text-stone-400">Договор в PDF, DOCX или XML</p>
              </Card>
              <Card hover className="text-center bg-slate-600/50 border-primary-500/30">
                <div className="w-14 h-14 bg-slate-700/60 rounded-xl flex items-center justify-center mx-auto mb-3">
                  <svg className="h-7 w-7 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                </div>
                <h3 className="font-bold text-lg mb-2 text-stone-200">Анализ AI</h3>
                <p className="text-sm text-stone-400">Автоматический анализ рисков</p>
              </Card>
              <Card hover className="text-center bg-slate-600/50 border-primary-500/30">
                <div className="w-14 h-14 bg-slate-700/60 rounded-xl flex items-center justify-center mx-auto mb-3">
                  <svg className="h-7 w-7 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                </div>
                <h3 className="font-bold text-lg mb-2 text-stone-200">Получите отчет</h3>
                <p className="text-sm text-stone-400">С рекомендациями и рисками</p>
              </Card>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-12 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {stats.map((stat, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
              >
                <Card className="text-center bg-slate-600/40 border-primary-500/20">
                  <div className="text-3xl md:text-4xl font-bold text-stone-200 mb-2">
                    {stat.value}
                  </div>
                  <div className="text-sm text-primary-300">{stat.label}</div>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-16 px-4">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
              Возможности системы
            </h2>
            <p className="text-xl text-stone-300 max-w-3xl mx-auto">
              Все инструменты для профессиональной работы с договорами
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
              >
                <Card hover className="h-full bg-slate-600/40 border-primary-500/20">
                  <div className="w-12 h-12 bg-slate-900/50 rounded-lg flex items-center justify-center mb-4">{feature.icon}</div>
                  <h3 className="text-xl font-bold mb-2 text-stone-200">{feature.title}</h3>
                  <p className="text-primary-300">{feature.description}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Advantages Section */}
      <section className="py-20 px-4 bg-gradient-to-br from-slate-800 via-slate-900 to-slate-800">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
              Почему Contract AI
            </h2>
            <p className="text-xl text-stone-300 max-w-3xl mx-auto">
              8 причин выбрать нашу систему для работы с договорами
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {advantages.map((adv, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.08 }}
                className="group"
              >
                <div className="h-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 hover:bg-white/10 transition-all duration-300">
                  <div className={`w-14 h-14 bg-gradient-to-br ${adv.gradient} rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                    {adv.icon}
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">{adv.title}</h3>
                  <p className="text-sm text-stone-300 leading-relaxed">{adv.description}</p>
                </div>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="mt-12 text-center"
          >
            <p className="text-stone-300 text-sm">
              AI-модели: DeepSeek V3/R1, YandexGPT 5, Qwen3 и другие.
              Переключение между провайдерами одной настройкой.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Pricing Preview */}
      <section id="pricing" className="py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
              Бесплатный старт и пилот
            </h2>
            <p className="text-xl text-stone-300 mb-8 max-w-2xl mx-auto">
              3 договора бесплатно в месяц. После проверки сценария обсуждаем пилот и рабочий контур.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-8">
              <Card hover className="text-center bg-slate-600/40 border-primary-500/20">
                <div className="text-sm text-primary-300 mb-1">Бесплатный режим</div>
                <div className="text-3xl font-bold text-stone-200">0 ₽</div>
                <div className="text-sm text-stone-300">первый шаг</div>
              </Card>
              <Card hover className="text-center border-2 border-primary-500 bg-slate-600/50">
                <div className="text-sm text-stone-200 font-semibold mb-1">Бесплатный лимит</div>
                <div className="text-3xl font-bold text-white">3</div>
                <div className="text-sm text-stone-300">договора в месяц</div>
              </Card>
              <Card hover className="text-center bg-slate-600/40 border-primary-500/20">
                <div className="text-sm text-primary-300 mb-1">Следующий этап</div>
                <div className="text-3xl font-bold text-stone-200">Пилот</div>
                <div className="text-sm text-stone-300">после проверки</div>
              </Card>
            </div>

            <div className="flex flex-col justify-center gap-3 sm:flex-row">
              <Button variant="primary" size="lg" onClick={() => router.push('/pricing')}>
                Форматы и условия запуска
              </Button>
              <Button variant="outline" size="lg" href="/demo">
                Как работает бесплатный режим
              </Button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 px-4">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
          >
            <Card className="text-center bg-slate-600/40 border-2 border-primary-500/30">
              <div className="py-8">
                <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                  Готовы попробовать?
                </h2>
                <p className="text-xl text-stone-300 mb-8 max-w-2xl mx-auto">
                  3 договора бесплатно в месяц. Без кредитной карты. Время анализа зависит от объёма документа.
                </p>
                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                  <Button variant="primary" size="lg" href="/register">
                    Начать бесплатно
                  </Button>
                  <a href="#login">
                    <Button variant="outline" size="lg">
                      Войти в систему
                    </Button>
                  </a>
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </section>
      </main>

      {/* Footer */}
      <footer className="bg-slate-800/95 backdrop-blur-lg border-t border-primary-600/30 py-12 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
                  <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                </div>
                <span className="font-bold text-white">Contract AI</span>
              </div>
              <p className="text-sm text-stone-300">
                Умная работа с договорами на основе искусственного интеллекта
              </p>
            </div>

            <div>
              <p className="font-bold text-white mb-4">Продукт</p>
              <ul className="space-y-2 text-sm text-stone-300">
                <li><a href="/pricing" className="hover:text-white transition">Тарифы</a></li>
                <li><a href="/demo" className="hover:text-white transition">Бесплатный режим</a></li>
                <li><a href="/register" className="hover:text-white transition">3 договора бесплатно</a></li>
                <li><a href="#login" className="hover:text-white transition">Вход</a></li>
              </ul>
            </div>

            <div>
              <p className="font-bold text-white mb-4">Контакты</p>
              <ul className="space-y-2 text-sm text-stone-300">
                <li><a href="https://t.me/legal_ai_helper_new_bot" target="_blank" rel="noopener noreferrer" className="hover:text-white transition">Telegram-бот</a></li>
                <li><a href="/pricing" className="hover:text-white transition">Для бизнеса</a></li>
              </ul>
            </div>

            <div>
              <p className="font-bold text-white mb-4">Правовая информация</p>
              <ul className="space-y-2 text-sm text-stone-300">
                <li><a href="/privacy" className="hover:text-white transition">Политика конфиденциальности</a></li>
                <li><a href="/terms" className="hover:text-white transition">Условия использования</a></li>
              </ul>
            </div>
          </div>

          <div className="pt-8 border-t border-slate-700 text-center text-sm text-stone-300">
            <p>&copy; 2025–2026 Contract AI System. Все права защищены.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
