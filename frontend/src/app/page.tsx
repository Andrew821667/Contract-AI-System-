'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'

export default function Home() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      router.push('/dashboard')
    } else {
      setIsLoading(false)
    }
  }, [router])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-stone-50 to-stone-100">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-16 h-16 border-4 border-primary-500 border-t-transparent rounded-full"
        />
      </div>
    )
  }

  const features = [
    {
      icon: <svg className="h-7 w-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>,
      title: 'Цифровизация договоров',
      description: 'Криптографическая подпись, hash-chain версий, проверка целостности документа'
    },
    {
      icon: <svg className="h-7 w-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
      title: 'Smart Composer',
      description: 'AI-помощник при составлении: подсказки, валидация, 50+ шаблонов пунктов'
    },
    {
      icon: <svg className="h-7 w-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>,
      title: 'Двухуровневый анализ',
      description: 'Быстрый скрининг + глубокий анализ критичных рисков со ссылками на ГК РФ'
    },
    {
      icon: <svg className="h-7 w-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>,
      title: 'ML-предсказание рисков',
      description: 'Моментальная оценка за <100 мс — в 100 раз быстрее полного AI-анализа'
    },
    {
      icon: <svg className="h-7 w-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>,
      title: 'Полный цикл',
      description: 'Генерация, анализ, разногласия, сравнение версий, экспорт — всё в одной системе'
    },
    {
      icon: <svg className="h-7 w-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>,
      title: 'Безопасность',
      description: 'On-premise для Enterprise, локальные AI-модели, данные не покидают периметр'
    }
  ]

  const advantages = [
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
      title: 'Кратно дешевле аналогов',
      description: 'От 20 ₽ за договор вместо 5 000–30 000 ₽ за ручной анализ. Прозрачные цены без «свяжитесь с отделом продаж».',
      gradient: 'from-green-500 to-emerald-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
      title: '10–30 секунд вместо часов',
      description: 'Двухуровневый AI: быстрый скрининг всех пунктов + глубокий анализ критичных рисков. Streaming — результат появляется в реальном времени.',
      gradient: 'from-blue-500 to-cyan-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>,
      title: 'Цифровизация договоров',
      description: 'Криптографическая подпись каждой версии, hash-chain целостности, DAG для слияния правок нескольких сторон.',
      gradient: 'from-purple-500 to-pink-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" /></svg>,
      title: 'Российское право',
      description: 'Ссылки на статьи ГК РФ и ФЗ. Типовые шаблоны российских договоров. Протоколы разногласий по российской практике.',
      gradient: 'from-orange-500 to-red-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>,
      title: 'Smart Composer',
      description: 'AI-помощник при наборе текста: подсказки пунктов, валидация на лету, 50+ шаблонов по типам договоров.',
      gradient: 'from-indigo-500 to-violet-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>,
      title: 'RAG — база знаний компании',
      description: 'Система учится на ваших политиках, шаблонах и прецедентах. Гибридный поиск: вектор + ключевые слова + ре-ранкинг.',
      gradient: 'from-teal-500 to-cyan-600',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>,
      title: 'Безопасность и On-premise',
      description: 'HTTPS, 4 уровня доступа, аудит-лог. Enterprise: система на вашем сервере, локальные AI-модели, данные не уходят наружу.',
      gradient: 'from-stone-600 to-stone-800',
    },
    {
      icon: <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>,
      title: 'Аналитика и ROI',
      description: 'Дашборд: сколько договоров обработано, время и деньги сэкономлены. ROI-мультипликатор для руководства.',
      gradient: 'from-amber-500 to-orange-600',
    },
  ]

  const stats = [
    { value: '10,000+', label: 'Проанализированных договоров' },
    { value: '99.8%', label: 'Точность анализа' },
    { value: '1-3 мин', label: 'Среднее время обработки' },
    { value: '24/7', label: 'Доступность системы' }
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20">
      {/* Навигация */}
      <nav className="bg-white/80 backdrop-blur-lg shadow-lg border-b border-white/20 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3"
            >
              <div className="w-10 h-10 bg-primary-600 rounded-xl shadow-sm flex items-center justify-center">
                <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              </div>
              <span className="text-xl font-bold text-stone-800">Contract AI</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-4"
            >
              <Button variant="outline" size="sm" onClick={() => router.push('/login')}>
                Вход
              </Button>
              <Button variant="primary" size="sm" onClick={() => router.push('/register')}>
                Попробовать бесплатно
              </Button>
            </motion.div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden py-20 px-4">
        {/* Background decoration */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-20 right-20 w-96 h-96 bg-primary-200/20 rounded-full blur-3xl" />
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <div className="text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <h1 className="text-6xl md:text-7xl font-bold mb-6">
                <span className="gradient-text">Умная работа</span>
                <br />
                с договорами
              </h1>
              <p className="text-xl md:text-2xl text-gray-600 mb-8 max-w-3xl mx-auto">
                AI-система для анализа, генерации и управления юридическими договорами.
                Экономьте время и снижайте риски с помощью искусственного интеллекта.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="flex flex-col sm:flex-row gap-4 justify-center"
            >
              <Button
                variant="primary"
                size="lg"
                onClick={() => router.push('/register')}
                icon={
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                }
              >
                Начать бесплатно
              </Button>
              <Button
                variant="outline"
                size="lg"
                onClick={() => router.push('/pricing')}
              >
                Посмотреть тарифы
              </Button>
            </motion.div>

            {/* Demo Image/Animation */}
            <motion.div
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.4 }}
              className="mt-16"
            >
              <div className="relative">
                <div className="absolute inset-0 bg-primary-200 opacity-20 blur-3xl rounded-3xl" />
                <div className="relative bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-white/20">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <Card hover className="text-center">
                      <div className="w-14 h-14 bg-primary-100 rounded-xl flex items-center justify-center mx-auto mb-3">
                        <svg className="h-7 w-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                      </div>
                      <h3 className="font-bold text-lg mb-2">Загрузите</h3>
                      <p className="text-sm text-gray-600">Договор в PDF, DOCX или XML</p>
                    </Card>
                    <Card hover className="text-center">
                      <div className="w-14 h-14 bg-primary-100 rounded-xl flex items-center justify-center mx-auto mb-3">
                        <svg className="h-7 w-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                      </div>
                      <h3 className="font-bold text-lg mb-2">Анализ AI</h3>
                      <p className="text-sm text-gray-600">Автоматический анализ рисков</p>
                    </Card>
                    <Card hover className="text-center">
                      <div className="w-14 h-14 bg-primary-100 rounded-xl flex items-center justify-center mx-auto mb-3">
                        <svg className="h-7 w-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                      </div>
                      <h3 className="font-bold text-lg mb-2">Получите отчет</h3>
                      <p className="text-sm text-gray-600">С рекомендациями и рисками</p>
                    </Card>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 px-4">
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
                <Card className="text-center">
                  <div className="text-3xl md:text-4xl font-bold text-primary-700 mb-2">
                    {stat.value}
                  </div>
                  <div className="text-sm text-gray-600">{stat.label}</div>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold text-stone-800 mb-4">
              Возможности системы
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Все инструменты для профессиональной работы с договорами в одной системе
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
              >
                <Card hover className="h-full">
                  <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">{feature.icon}</div>
                  <h3 className="text-xl font-bold mb-2">{feature.title}</h3>
                  <p className="text-gray-600">{feature.description}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Advantages Section */}
      <section className="py-20 px-4 bg-gradient-to-br from-stone-900 via-stone-800 to-stone-900">
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
              10 причин выбрать нашу систему для работы с договорами
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
                  <p className="text-sm text-stone-400 leading-relaxed">{adv.description}</p>
                </div>
              </motion.div>
            ))}
          </div>

          {/* AI Models note */}
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="mt-12 text-center"
          >
            <p className="text-stone-400 text-sm">
              Поддерживаемые AI-модели: DeepSeek V3/R1, YandexGPT 5, Qwen3 и другие современные модели.
              <br />Переключение между провайдерами одной настройкой. Нет привязки к одному поставщику.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Pricing Preview */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-4xl md:text-5xl font-bold text-stone-800 mb-4">
              Прозрачные цены
            </h2>
            <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
              Подписка от 1 990 ₽/мес или пакеты от 20 ₽ за договор
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-8">
              <Card hover className="text-center">
                <div className="text-sm text-gray-500 mb-1">Персональный</div>
                <div className="text-3xl font-bold text-primary-700">1 990 ₽</div>
                <div className="text-sm text-gray-500">в месяц</div>
              </Card>
              <Card hover className="text-center border-2 border-primary-300">
                <div className="text-sm text-primary-600 font-semibold mb-1">Команда</div>
                <div className="text-3xl font-bold text-primary-700">4 990 ₽</div>
                <div className="text-sm text-gray-500">в месяц</div>
              </Card>
              <Card hover className="text-center">
                <div className="text-sm text-gray-500 mb-1">Бизнес</div>
                <div className="text-3xl font-bold text-primary-700">14 990 ₽</div>
                <div className="text-sm text-gray-500">в месяц</div>
              </Card>
            </div>

            <Button variant="primary" size="lg" onClick={() => router.push('/pricing')}>
              Все тарифы и сравнение с конкурентами
            </Button>
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
          >
            <Card className="text-center bg-gradient-to-br from-primary-50 to-stone-50 border-2 border-primary-200">
              <div className="py-8">
                <h2 className="text-3xl md:text-4xl font-bold text-stone-800 mb-4">
                  Готовы попробовать?
                </h2>
                <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
                  5 бесплатных анализов. Без кредитной карты. Результат за 30 секунд.
                </p>
                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                  <Button
                    variant="primary"
                    size="lg"
                    onClick={() => router.push('/register')}
                    icon={
                      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                    }
                  >
                    Начать бесплатно
                  </Button>
                  <Button variant="outline" size="lg" onClick={() => router.push('/pricing')}>
                    Посмотреть тарифы
                  </Button>
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-white/80 backdrop-blur-lg border-t border-gray-200 py-12 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                  <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                </div>
                <span className="font-bold text-stone-800">Contract AI</span>
              </div>
              <p className="text-sm text-gray-600">
                Умная работа с договорами на основе искусственного интеллекта
              </p>
            </div>

            <div>
              <h4 className="font-bold mb-4">Продукт</h4>
              <ul className="space-y-2 text-sm text-gray-600">
                <li><a href="/pricing" className="hover:text-primary-600">Тарифы</a></li>
                <li><a href="/demo" className="hover:text-primary-600">Демо</a></li>
                <li><a href="/login" className="hover:text-primary-600">Вход</a></li>
                <li><a href="/register" className="hover:text-primary-600">Регистрация</a></li>
              </ul>
            </div>

            <div>
              <h4 className="font-bold mb-4">Контакты</h4>
              <ul className="space-y-2 text-sm text-gray-600">
                <li><a href="https://t.me/legal_ai_helper_new_bot" target="_blank" rel="noopener noreferrer" className="hover:text-primary-600">Telegram-бот</a></li>
                <li><a href="/pricing" className="hover:text-primary-600">Для бизнеса</a></li>
              </ul>
            </div>

            <div>
              <h4 className="font-bold mb-4">Правовая информация</h4>
              <ul className="space-y-2 text-sm text-gray-600">
                <li><span className="text-gray-400">Политика конфиденциальности</span></li>
                <li><span className="text-gray-400">Условия использования</span></li>
              </ul>
            </div>
          </div>

          <div className="pt-8 border-t border-gray-200 text-center text-sm text-gray-600">
            <p>© 2025–2026 Contract AI System. Все права защищены.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
