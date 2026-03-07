'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'

export default function PricingPage() {
  const router = useRouter()
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly')
  const [pricingModel, setPricingModel] = useState<'subscription' | 'packs'>('subscription')

  const plans = [
    {
      name: 'Бесплатный',
      tier: 'demo',
      price: { monthly: 0, annual: 0 },
      description: 'Попробуйте все возможности системы',
      gradient: 'from-gray-400 to-gray-600',
      popular: false,
      features: [
        { text: '5 договоров в месяц', included: true },
        { text: '15 AI-запросов', included: true },
        { text: 'Базовый анализ рисков (Уровень 1)', included: true },
        { text: '2 шаблона генерации', included: true },
        { text: 'Экспорт DOCX', included: true },
        { text: 'Глубокий анализ (Уровень 2)', included: false },
        { text: 'Сравнение версий', included: false },
        { text: 'Протоколы разногласий', included: false },
        { text: 'Smart Composer', included: false },
        { text: 'Цифровая подпись', included: false },
      ]
    },
    {
      name: 'Персональный',
      tier: 'personal',
      price: { monthly: 1990, annual: 17900 },
      description: 'Для юристов и частной практики',
      gradient: 'from-blue-500 to-cyan-600',
      popular: false,
      features: [
        { text: '50 договоров в месяц', included: true },
        { text: '200 AI-запросов', included: true },
        { text: 'Полный анализ (Уровень 1 + 2)', included: true },
        { text: 'Все шаблоны генерации', included: true },
        { text: 'Экспорт DOCX, PDF, XML', included: true },
        { text: 'Streaming-анализ в реальном времени', included: true },
        { text: 'Сравнение версий', included: true },
        { text: 'Протоколы разногласий', included: true },
        { text: 'Smart Composer', included: false },
        { text: 'Цифровая подпись', included: false },
      ]
    },
    {
      name: 'Команда',
      tier: 'team',
      price: { monthly: 4990, annual: 44900 },
      description: 'Для юридических отделов и фирм',
      gradient: 'from-purple-500 to-pink-600',
      popular: true,
      features: [
        { text: 'До 10 пользователей', included: true },
        { text: '300 договоров в месяц', included: true },
        { text: '1 000 AI-запросов', included: true },
        { text: 'Всё из «Персональный»', included: true },
        { text: 'Smart Composer — AI-помощник', included: true },
        { text: 'Аннотированный DOCX с подсветкой', included: true },
        { text: 'RAG — база знаний компании', included: true },
        { text: 'Batch-анализ пачки договоров', included: true },
        { text: 'Цифровая подпись (hash-chain)', included: true },
        { text: 'SLA 99%', included: true },
      ]
    },
    {
      name: 'Бизнес',
      tier: 'business',
      price: { monthly: 14990, annual: 134900 },
      description: 'Для компаний и корпоративных юристов',
      gradient: 'from-orange-500 to-red-600',
      popular: false,
      features: [
        { text: 'До 50 пользователей', included: true },
        { text: '1 500 договоров в месяц', included: true },
        { text: '5 000 AI-запросов', included: true },
        { text: 'Всё из «Команда»', included: true },
        { text: 'REST API для интеграции (CRM, 1С)', included: true },
        { text: 'Кастомные шаблоны договоров', included: true },
        { text: 'ML-предсказание рисков (<100 мс)', included: true },
        { text: 'Аналитика ROI и дашборд', included: true },
        { text: 'Приоритетная поддержка', included: true },
        { text: 'SLA 99.5%', included: true },
      ]
    },
    {
      name: 'Enterprise',
      tier: 'enterprise',
      price: { monthly: 39990, annual: 0 },
      description: 'On-premise, безлимит, свои модели',
      gradient: 'from-stone-700 to-stone-900',
      popular: false,
      isCustom: true,
      features: [
        { text: 'Безлимит пользователей', included: true },
        { text: 'Безлимит договоров и запросов', included: true },
        { text: 'Всё из «Бизнес»', included: true },
        { text: 'On-premise на вашем сервере', included: true },
        { text: 'Локальные AI-модели (Ollama)', included: true },
        { text: 'Данные не покидают периметр', included: true },
        { text: 'Кастомизация под ваши процессы', included: true },
        { text: 'Выделенный менеджер', included: true },
        { text: '24/7 техподдержка', included: true },
        { text: 'SLA 99.9%', included: true },
      ]
    }
  ]

  const documentPacks = [
    { name: 'Пробный', count: 5, price: 390, perDoc: 78, saving: 0 },
    { name: 'Малый', count: 25, price: 1490, perDoc: 60, saving: 23 },
    { name: 'Стандарт', count: 100, price: 4490, perDoc: 45, saving: 42 },
    { name: 'Объёмный', count: 500, price: 14990, perDoc: 30, saving: 62 },
    { name: 'Корпоративный', count: 2000, price: 39990, perDoc: 20, saving: 74 },
  ]

  const competitors = [
    { name: 'Doczilla Pro', price: 'от 2 500 ₽/мес', our: 'от 1 990 ₽/мес', diff: 'Дешевле + больше функций' },
    { name: 'PravoTech', price: 'Только по запросу', our: 'от 1 990 ₽/мес', diff: 'Прозрачные цены' },
    { name: 'Noroots', price: 'По запросу', our: 'от 20 ₽/договор', diff: 'Понятно с первой минуты' },
    { name: 'Ручной анализ', price: '5 000–30 000 ₽/договор', our: 'от 20 ₽/договор', diff: 'В 250–1500 раз дешевле' },
  ]

  const getPrice = (plan: typeof plans[0]) => {
    if (plan.isCustom) return 'от 39 990 ₽'
    if (plan.price.monthly === 0) return 'Бесплатно'
    const price = billingCycle === 'monthly' ? plan.price.monthly : plan.price.annual
    return `${price.toLocaleString('ru-RU')} ₽`
  }

  const getSavings = (plan: typeof plans[0]) => {
    if (billingCycle === 'annual' && !plan.isCustom && plan.price.monthly > 0) {
      const monthlyCost = plan.price.monthly * 12
      const annualCost = plan.price.annual
      const savings = monthlyCost - annualCost
      return `Экономия ${savings.toLocaleString('ru-RU')} ₽/год`
    }
    return null
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20">
      {/* Header */}
      <nav className="bg-white/80 backdrop-blur-lg shadow-lg border-b border-white/20 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3 cursor-pointer"
              onClick={() => router.push('/')}
            >
              <div className="w-10 h-10 bg-primary-600 rounded-xl shadow-sm flex items-center justify-center">
                <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              </div>
              <span className="text-xl font-bold text-stone-800">Contract AI</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3"
            >
              <Button variant="outline" size="sm" onClick={() => router.push('/')}>
                ← На главную
              </Button>
              <Button variant="primary" size="sm" onClick={() => router.push('/register')}>
                Попробовать бесплатно
              </Button>
            </motion.div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Title */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <h1 className="text-5xl md:text-6xl font-bold text-stone-900 mb-4">
            Тарифы и цены
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
            Кратно дешевле любого аналога на рынке. Прозрачно. Без скрытых платежей.
          </p>

          {/* Model Toggle */}
          <div className="inline-flex items-center bg-white rounded-2xl p-2 shadow-lg mb-6">
            <button
              onClick={() => setPricingModel('subscription')}
              className={`px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
                pricingModel === 'subscription'
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Подписка
            </button>
            <button
              onClick={() => setPricingModel('packs')}
              className={`px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
                pricingModel === 'packs'
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Пакеты документов
            </button>
          </div>

          {/* Billing Toggle (only for subscription) */}
          {pricingModel === 'subscription' && (
            <div className="block">
              <div className="inline-flex items-center bg-white rounded-2xl p-2 shadow-lg">
                <button
                  onClick={() => setBillingCycle('monthly')}
                  className={`px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
                    billingCycle === 'monthly'
                      ? 'bg-primary-600 text-white shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Ежемесячно
                </button>
                <button
                  onClick={() => setBillingCycle('annual')}
                  className={`px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
                    billingCycle === 'annual'
                      ? 'bg-primary-600 text-white shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Ежегодно
                  <Badge variant="success" size="sm" className="ml-2">-25%</Badge>
                </button>
              </div>
            </div>
          )}
        </motion.div>

        {/* === SUBSCRIPTION PLANS === */}
        {pricingModel === 'subscription' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6 mb-16">
            {plans.map((plan, idx) => (
              <motion.div
                key={plan.tier}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.08 }}
                className="relative"
              >
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 z-10">
                    <Badge variant="warning" size="lg">Популярный</Badge>
                  </div>
                )}

                <Card className={`h-full relative overflow-hidden ${
                  plan.popular ? 'border-2 border-primary-300 shadow-2xl' : ''
                }`}>
                  <div className={`absolute top-0 left-0 right-0 h-2 bg-gradient-to-r ${plan.gradient}`} />

                  <div className="pt-6">
                    <h3 className="text-xl font-bold text-gray-900 mb-1">{plan.name}</h3>
                    <p className="text-sm text-gray-500 mb-4">{plan.description}</p>

                    <div className="mb-5">
                      <div className="text-3xl font-bold text-primary-700 mb-1">
                        {getPrice(plan)}
                      </div>
                      {!plan.isCustom && plan.price.monthly > 0 && (
                        <div className="text-sm text-gray-500">
                          {billingCycle === 'monthly' ? 'в месяц' : 'в год'}
                        </div>
                      )}
                      {getSavings(plan) && (
                        <div className="text-sm text-green-600 font-semibold mt-1">
                          {getSavings(plan)}
                        </div>
                      )}
                    </div>

                    <ul className="space-y-2 mb-6">
                      {plan.features.map((feature, fIdx) => (
                        <li key={fIdx} className="flex items-start text-sm">
                          {feature.included ? (
                            <svg className="h-4 w-4 text-green-500 mr-2 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          ) : (
                            <svg className="h-4 w-4 text-gray-300 mr-2 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          )}
                          <span className={feature.included ? 'text-gray-700' : 'text-gray-400'}>
                            {feature.text}
                          </span>
                        </li>
                      ))}
                    </ul>

                    {plan.isCustom ? (
                      <Button variant="outline" className="w-full" onClick={() => window.open('https://t.me/legal_ai_helper_new_bot', '_blank')}>
                        Связаться с нами
                      </Button>
                    ) : plan.price.monthly === 0 ? (
                      <Button variant="outline" className="w-full" onClick={() => router.push('/register')}>
                        Попробовать
                      </Button>
                    ) : (
                      <Button variant={plan.popular ? 'primary' : 'outline'} className="w-full" onClick={() => router.push('/register')}>
                        Выбрать
                      </Button>
                    )}
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>
        )}

        {/* === DOCUMENT PACKS === */}
        {pricingModel === 'packs' && (
          <div className="max-w-5xl mx-auto mb-16">
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-center text-gray-600 mb-8"
            >
              Без подписки. Купите пакет — используйте в течение 12 месяцев.
              <br />Включает полный анализ (Уровень 1+2), генерацию, экспорт DOCX/PDF.
            </motion.p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
              {documentPacks.map((pack, idx) => (
                <motion.div
                  key={pack.name}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.08 }}
                >
                  <Card hover className="h-full text-center">
                    <h3 className="text-lg font-bold text-gray-900 mb-2">{pack.name}</h3>
                    <div className="text-4xl font-bold text-primary-700 mb-1">
                      {pack.count}
                    </div>
                    <div className="text-sm text-gray-500 mb-4">договоров</div>

                    <div className="text-2xl font-bold text-stone-800 mb-1">
                      {pack.price.toLocaleString('ru-RU')} ₽
                    </div>
                    <div className="text-sm text-gray-500 mb-2">
                      {pack.perDoc} ₽ за договор
                    </div>
                    {pack.saving > 0 && (
                      <Badge variant="success" size="sm">-{pack.saving}%</Badge>
                    )}

                    <div className="mt-4">
                      <Button variant="outline" className="w-full" onClick={() => router.push('/register')}>
                        Купить
                      </Button>
                    </div>
                  </Card>
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {/* === COMPETITOR COMPARISON === */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="max-w-4xl mx-auto mb-16"
        >
          <h2 className="text-3xl font-bold text-stone-800 text-center mb-8">
            Сравнение с конкурентами
          </h2>

          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-600">Решение</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-600">Их цена</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-primary-700">Наша цена</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-600">Преимущество</th>
                  </tr>
                </thead>
                <tbody>
                  {competitors.map((comp, idx) => (
                    <tr key={idx} className="border-b border-gray-100 last:border-0">
                      <td className="py-3 px-4 font-medium text-gray-900">{comp.name}</td>
                      <td className="py-3 px-4 text-gray-600">{comp.price}</td>
                      <td className="py-3 px-4 font-semibold text-primary-700">{comp.our}</td>
                      <td className="py-3 px-4">
                        <Badge variant="success" size="sm">{comp.diff}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </motion.div>

        {/* === FAQ === */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="max-w-4xl mx-auto mb-16"
        >
          <h2 className="text-3xl font-bold text-stone-800 text-center mb-8">
            Частые вопросы
          </h2>

          <div className="space-y-4">
            {[
              { q: 'Чем подписка отличается от пакетов документов?', a: 'Подписка — ежемесячный доступ ко всем функциям с лимитами. Пакеты — разовая покупка определённого количества анализов без привязки к сроку (действуют 12 месяцев).' },
              { q: 'Можно ли сменить тариф?', a: 'Да, вы можете повысить или понизить тариф в любое время из личного кабинета.' },
              { q: 'Что будет, если лимиты закончатся?', a: 'Вы можете перейти на старший тариф или докупить пакет документов.' },
              { q: 'Как работает Enterprise on-premise?', a: 'Мы разворачиваем систему на вашем сервере. Все данные остаются внутри вашего периметра. AI-модели работают локально через Ollama.' },
              { q: 'Какие AI-модели используются?', a: 'DeepSeek V3/R1, YandexGPT 5, Qwen3 и другие современные модели. Также поддерживаются локальные модели через Ollama для полной конфиденциальности.' },
              { q: 'Есть ли бесплатный период?', a: 'Да, бесплатный тариф без ограничений по времени: 5 договоров и 15 AI-запросов в месяц.' },
            ].map((faq, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.05 }}
              >
                <Card hover>
                  <h3 className="font-bold text-gray-900 mb-2">{faq.q}</h3>
                  <p className="text-gray-600 text-sm">{faq.a}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center"
        >
          <Card className="bg-gradient-to-br from-primary-50 to-stone-50 border-2 border-primary-200">
            <div className="py-8">
              <h2 className="text-3xl font-bold text-stone-800 mb-4">
                Остались вопросы?
              </h2>
              <p className="text-gray-600 mb-6 max-w-2xl mx-auto">
                Свяжитесь с нами — поможем выбрать оптимальный тариф для ваших задач
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button variant="primary" onClick={() => window.open('https://t.me/legal_ai_helper_new_bot', '_blank')}>
                  Связаться с нами
                </Button>
                <Button variant="outline" onClick={() => router.push('/register')}>
                  Начать бесплатно
                </Button>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}
