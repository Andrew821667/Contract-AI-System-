'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { useForm } from 'react-hook-form'
import toast from 'react-hot-toast'
import Button from '@/components/ui/Button'
import BrandLockup from '@/components/BrandLockup'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'

interface RegisterFormData {
  name: string
  email: string
  password: string
  confirmPassword: string
}

const translateRegistrationError = (err: any) => {
  const detail = err?.response?.data?.detail || err?.response?.data?.message

  if (typeof detail !== 'string') {
    return 'Ошибка регистрации. Попробуйте снова.'
  }

  const normalized = detail.toLowerCase()

  if (normalized.includes('at least') || normalized.includes('minimum')) {
    return 'Пароль должен быть не короче 8 символов.'
  }
  if (normalized.includes('uppercase')) {
    return 'Пароль должен содержать хотя бы одну заглавную букву.'
  }
  if (normalized.includes('lowercase')) {
    return 'Пароль должен содержать хотя бы одну строчную букву.'
  }
  if (normalized.includes('digit')) {
    return 'Пароль должен содержать хотя бы одну цифру.'
  }

  return detail
}

export default function RegisterPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const { register, handleSubmit, watch, formState: { errors } } = useForm<RegisterFormData>()

  const password = watch('password')

  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await api.register({
        email: data.email,
        name: data.name,
        password: data.password,
      })

      if (response.access_token && response.user) {
        // MVP: auto-login after registration
        useAuthStore.getState().setAuth(response.user, response.access_token)
        toast.success('Регистрация успешна!')
        router.push('/dashboard')
      } else {
        // Fallback: email verification required
        toast.success('Проверьте вашу почту для подтверждения регистрации')
        router.push('/login')
      }
    } catch (err: any) {
      setError(translateRegistrationError(err))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="brand-surface min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      <div className="brand-grid absolute inset-0 pointer-events-none" aria-hidden="true" />
      {/* Animated Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute top-20 right-20 w-96 h-96 bg-primary-400/15 rounded-full blur-3xl"
          animate={{
            scale: [1, 1.2, 1],
            x: [0, 30, 0],
            y: [0, -30, 0]
          }}
          transition={{ duration: 8, repeat: Infinity }}
        />
        <motion.div
          className="absolute bottom-20 left-20 w-96 h-96 bg-slate-400/10 rounded-full blur-3xl"
          animate={{
            scale: [1.2, 1, 1.2],
            x: [0, -30, 0],
            y: [0, 30, 0]
          }}
          transition={{ duration: 10, repeat: Infinity }}
        />
      </div>

      {/* Register Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="brand-panel rounded-3xl p-8">
          {/* Logo */}
          <div className="text-center mb-8">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", duration: 0.6 }}
              className="mx-auto mb-4 w-fit"
            >
              <BrandLockup className="justify-center" />
            </motion.div>
            <h1 className="text-3xl font-bold gradient-text mb-2">
              Бесплатный доступ
            </h1>
            <p className="text-slate-600">
              Создайте аккаунт: 3 договора бесплатно каждый месяц
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
              {error}
            </div>
          )}

          {/* Registration Form */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">
                Имя
              </label>
              <div className="relative">
                <input
                  {...register('name', {
                    required: 'Введите ваше имя',
                    minLength: { value: 2, message: 'Минимум 2 символа' }
                  })}
                  type="text"
                  placeholder="Иван Иванов"
                  className="w-full pl-12 pr-4 py-3.5 bg-white border-2 border-slate-300 rounded-xl focus:border-primary-500 focus:ring-4 focus:ring-primary-100 transition-all outline-none text-slate-900 placeholder-slate-400"
                />
                <svg className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              {errors.name && (
                <p className="text-danger-600 text-sm mt-1">{errors.name.message}</p>
              )}
            </div>

            {/* Email */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">
                Email
              </label>
              <div className="relative">
                <input
                  {...register('email', {
                    required: 'Введите email',
                    pattern: {
                      value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                      message: 'Некорректный email'
                    }
                  })}
                  type="email"
                  placeholder="email@example.com"
                  className="w-full pl-12 pr-4 py-3.5 bg-white border-2 border-slate-300 rounded-xl focus:border-primary-500 focus:ring-4 focus:ring-primary-100 transition-all outline-none text-slate-900 placeholder-slate-400"
                />
                <svg className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              {errors.email && (
                <p className="text-danger-600 text-sm mt-1">{errors.email.message}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">
                Пароль
              </label>
              <div className="relative">
                <input
                  {...register('password', {
                    required: 'Введите пароль',
                    minLength: { value: 8, message: 'Минимум 8 символов' },
                    validate: {
                      uppercase: value => /[A-ZА-ЯЁ]/.test(value) || 'Добавьте заглавную букву',
                      lowercase: value => /[a-zа-яё]/.test(value) || 'Добавьте строчную букву',
                      digit: value => /\d/.test(value) || 'Добавьте цифру',
                    }
                  })}
                  type="password"
                  placeholder="••••••••"
                  className="w-full pl-12 pr-4 py-3.5 bg-white border-2 border-slate-300 rounded-xl focus:border-primary-500 focus:ring-4 focus:ring-primary-100 transition-all outline-none text-slate-900 placeholder-slate-400"
                />
                <svg className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              {errors.password && (
                <p className="text-danger-600 text-sm mt-1">{errors.password.message}</p>
              )}
              {!errors.password && (
                <p className="text-slate-500 text-xs mt-1">Минимум 8 символов: заглавная буква, строчная буква и цифра</p>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">
                Подтверждение пароля
              </label>
              <div className="relative">
                <input
                  {...register('confirmPassword', {
                    required: 'Подтвердите пароль',
                    validate: value => value === password || 'Пароли не совпадают'
                  })}
                  type="password"
                  placeholder="••••••••"
                  className="w-full pl-12 pr-4 py-3.5 bg-white border-2 border-slate-300 rounded-xl focus:border-primary-500 focus:ring-4 focus:ring-primary-100 transition-all outline-none text-slate-900 placeholder-slate-400"
                />
                <svg className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              {errors.confirmPassword && (
                <p className="text-danger-600 text-sm mt-1">{errors.confirmPassword.message}</p>
              )}
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              loading={isLoading}
              disabled={isLoading}
            >
              Начать бесплатно
            </Button>
          </form>

          {/* Login Link */}
          <div className="mt-6 text-center">
            <p className="text-slate-600">
              Уже есть аккаунт?{' '}
              <button
                onClick={() => router.push('/login')}
                className="text-primary-700 hover:text-primary-800 font-semibold"
              >
                Войти
              </button>
            </p>
          </div>

          {/* Back to Home */}
          <div className="mt-4 text-center">
            <button
              onClick={() => router.push('/')}
              className="text-slate-500 hover:text-primary-700 text-sm"
            >
              ← На главную
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
