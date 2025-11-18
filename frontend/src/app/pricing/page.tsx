'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import toast from 'react-hot-toast'

export default function PricingPage() {
  const router = useRouter()
  const [loading, setLoading] = useState<string | null>(null)

  const { data: pricing } = useQuery({
    queryKey: ['pricing'],
    queryFn: async () => {
      const data = await api.getPricing()
      return data
    }
  })

  const handleSubscribe = async (tier: string) => {
    setLoading(tier)
    try {
      const checkoutUrl = await api.createCheckoutSession({
        tier,
        success_url: `${window.location.origin}/dashboard?payment=success`,
        cancel_url: `${window.location.origin}/pricing?payment=cancelled`
      })
      window.location.href = checkoutUrl
    } catch (error) {
      toast.error('Ошибка создания checkout session')
      setLoading(null)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900">Тарифные планы</h1>
          <p className="mt-4 text-xl text-gray-600">Выберите план, который подходит вам</p>
        </div>

        <div className="mt-12 grid gap-8 lg:grid-cols-4">
          {pricing?.tiers.map((tier: any) => (
            <div key={tier.tier} className="bg-white rounded-lg shadow-lg overflow-hidden">
              <div className="px-6 py-8">
                <h3 className="text-2xl font-bold text-gray-900">{tier.name}</h3>
                <p className="mt-4">
                  <span className="text-4xl font-bold text-gray-900">{tier.price_monthly}</span>
                  <span className="text-gray-600"> ₽/мес</span>
                </p>

                <ul className="mt-6 space-y-4">
                  <li className="flex items-center">
                    <span className="text-green-500 mr-2">✓</span>
                    {tier.features.max_contracts_per_day} контрактов/день
                  </li>
                  <li className="flex items-center">
                    <span className="text-green-500 mr-2">✓</span>
                    {tier.features.max_llm_requests_per_day} LLM запросов/день
                  </li>
                  {tier.features.can_export_pdf && (
                    <li className="flex items-center">
                      <span className="text-green-500 mr-2">✓</span>
                      Экспорт в PDF
                    </li>
                  )}
                  {tier.features.can_use_disagreements && (
                    <li className="flex items-center">
                      <span className="text-green-500 mr-2">✓</span>
                      Генерация возражений
                    </li>
                  )}
                  {tier.features.can_use_changes_analyzer && (
                    <li className="flex items-center">
                      <span className="text-green-500 mr-2">✓</span>
                      Анализ изменений
                    </li>
                  )}
                </ul>

                {tier.tier !== 'free' && (
                  <button
                    onClick={() => handleSubscribe(tier.tier)}
                    disabled={loading === tier.tier}
                    className="mt-8 w-full bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {loading === tier.tier ? 'Загрузка...' : 'Выбрать план'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-8 text-center">
          <button
            onClick={() => router.push('/dashboard')}
            className="text-indigo-600 hover:text-indigo-800"
          >
            ← Вернуться в dashboard
          </button>
        </div>
      </div>
    </div>
  )
}
