'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import api from '@/services/api'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      // Demo credentials with roles
      const demoCredentials = [
        { email: 'demo@example.com', password: 'demo123', name: 'Demo User', role: 'demo' },
        { email: 'admin@example.com', password: 'admin123', name: 'Admin User', role: 'admin' },
        { email: 'lawyer@example.com', password: 'lawyer123', name: 'Lawyer User', role: 'lawyer' },
        { email: 'junior@example.com', password: 'junior123', name: 'Junior Lawyer', role: 'junior_lawyer' },
      ]

      const demoUser = demoCredentials.find(
        u => u.email === email && u.password === password
      )

      if (demoUser) {
        localStorage.setItem('access_token', 'demo_token_' + Date.now())
        localStorage.setItem('user', JSON.stringify({
          name: demoUser.name,
          email: demoUser.email,
          role: demoUser.role
        }))

        toast.success(`Добро пожаловать, ${demoUser.name}!`, {
          style: {
            borderRadius: '12px',
            background: '#967b52',
            color: '#fff',
          },
        })

        setTimeout(() => {
          window.location.href = '/dashboard'
        }, 100)
        return
      }

      // Try real API
      const response = await api.login({
        username: email,
        password: password,
      })

      toast.success(`Добро пожаловать, ${response.user.name}!`, {
        style: {
          borderRadius: '12px',
          background: '#967b52',
          color: '#fff',
        },
      })
      router.push('/dashboard')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Неверный email или пароль', {
        style: {
          borderRadius: '12px',
        },
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen relative overflow-hidden bg-gradient-to-br from-stone-50 via-amber-50/30 to-stone-100">
      {/* Subtle background blur */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-primary-200/20 rounded-full blur-3xl" />
      </div>

      {/* Main Content */}
      <div className="relative z-10 min-h-screen flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-md"
        >
          {/* Logo & Title */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
            className="text-center mb-8"
          >
            <motion.div
              className="inline-block mb-4"
              whileHover={{ scale: 1.05 }}
              transition={{ type: "spring", stiffness: 300 }}
            >
              <div className="w-20 h-20 mx-auto bg-primary-600 rounded-2xl shadow-lg flex items-center justify-center">
                <svg className="h-10 w-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              </div>
            </motion.div>

            <h1 className="text-5xl font-bold text-stone-800 mb-3">
              Contract AI
            </h1>
            <p className="text-xl text-stone-600 font-medium">
              Умная работа с договорами
            </p>
          </motion.div>

          {/* Login Card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="bg-white rounded-3xl shadow-card p-8 border border-stone-100"
          >
            <h2 className="text-2xl font-bold text-stone-800 mb-6 text-center">
              Вход в систему
            </h2>

            <form onSubmit={handleLogin} className="space-y-5">
              {/* Email Field */}
              <div>
                <label className="block text-sm font-semibold text-stone-700 mb-2">
                  Email
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg className="h-5 w-5 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                    </svg>
                  </div>
                  <input
                    type="text"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-12 pr-4 py-3.5 bg-white border-2 border-stone-200 rounded-xl text-stone-900 placeholder-slate-400 focus:border-primary-500 focus:ring-4 focus:ring-primary-100 transition-all duration-300 outline-none"
                    placeholder="user@example.com"
                    required
                  />
                </div>
              </div>

              {/* Password Field */}
              <div>
                <label className="block text-sm font-semibold text-stone-700 mb-2">
                  Пароль
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg className="h-5 w-5 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  </div>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-12 pr-4 py-3.5 bg-white border-2 border-stone-200 rounded-xl text-stone-900 placeholder-slate-400 focus:border-primary-500 focus:ring-4 focus:ring-primary-100 transition-all duration-300 outline-none"
                    placeholder="••••••••"
                    required
                  />
                </div>
              </div>

              {/* Submit Button */}
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                type="submit"
                disabled={isLoading}
                className="w-full py-4 bg-primary-600 hover:bg-primary-700 text-white font-bold rounded-xl shadow-sm transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Вход...
                  </span>
                ) : (
                  'Войти'
                )}
              </motion.button>
            </form>

            <div className="mt-4 text-right">
              <a
                href="https://t.me/legal_ai_helper_new_bot"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary-600 hover:text-primary-700 hover:underline"
              >
                Забыли пароль?
              </a>
            </div>

            {/* Demo Credentials */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="mt-6 p-4 bg-stone-50 rounded-xl border border-stone-200"
            >
              <p className="text-sm font-semibold text-stone-700 mb-2 flex items-center">
                <svg className="h-4 w-4 mr-2 text-stone-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Демо-аккаунты:
              </p>
              <div className="space-y-1.5 text-xs text-stone-600">
                <div className="flex flex-col sm:flex-row sm:justify-between gap-1">
                  <span className="font-semibold">Demo:</span>
                  <code className="bg-stone-200 text-stone-700 px-2 py-0.5 rounded">demo@example.com / demo123</code>
                </div>
                <div className="flex flex-col sm:flex-row sm:justify-between gap-1">
                  <span className="font-semibold">Admin:</span>
                  <code className="bg-stone-200 text-stone-700 px-2 py-0.5 rounded">admin@example.com / admin123</code>
                </div>
              </div>
            </motion.div>
          </motion.div>

          {/* Footer Links */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
            className="mt-6 text-center space-y-2"
          >
            <p className="text-stone-600 text-sm">
              Нет аккаунта?{' '}
              <button
                onClick={() => router.push('/register')}
                className="font-semibold text-primary-600 hover:text-primary-700 hover:underline"
              >
                Зарегистрироваться
              </button>
            </p>
            <p className="text-stone-400 text-xs">
              © 2025 Contract AI System. Все права защищены.
            </p>
          </motion.div>
        </motion.div>
      </div>
    </div>
  )
}
