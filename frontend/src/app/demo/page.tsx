'use client'

import { motion } from 'framer-motion'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'

export default function DemoPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-lg"
      >
        <Card className="text-center">
          <div className="w-16 h-16 bg-primary-600 rounded-2xl shadow-sm flex items-center justify-center mx-auto mb-5">
            <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-stone-800 mb-3">
            Бесплатный режим Contract AI
          </h1>
          <p className="text-gray-600 mb-6">
            Создайте аккаунт и используйте 3 договора бесплатно каждый месяц.
          </p>
          <div className="grid grid-cols-1 gap-3 text-left mb-6">
            {[
              '3 договора бесплатно в месяц',
              'AI-анализ рисков и экспорт DOCX',
              'Без готовых публичных логинов и демо-ролей',
            ].map((text) => (
              <div key={text} className="flex items-center gap-3 rounded-xl bg-primary-50 px-4 py-3 text-sm text-primary-900">
                <span className="h-2 w-2 rounded-full bg-primary-600" />
                <span>{text}</span>
              </div>
            ))}
          </div>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button variant="primary" href="/register">
              Начать бесплатно
            </Button>
            <Button variant="outline" href="/#login">
              Уже есть аккаунт
            </Button>
          </div>
        </Card>
      </motion.div>
    </div>
  )
}
