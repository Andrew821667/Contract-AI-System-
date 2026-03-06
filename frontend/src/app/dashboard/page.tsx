'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import api, { User, DashboardData, ModelStatus } from '@/services/api'
import toast from 'react-hot-toast'
import { getUserRole, getRolePermissions, getRoleColor, getRoleLabel } from '@/utils/roles'
import ChangePasswordModal from '@/components/ChangePasswordModal'
import NotificationBell from '@/components/NotificationBell'
import { useNotifications } from '@/hooks/useNotifications'
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  BarChart, Bar
} from 'recharts'

interface Contract {
  id: string
  file_name: string
  status: string
  contract_type: string
  created_at: string
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 }
}

const RISK_COLORS: Record<string, string> = {
  critical: '#DC2626',
  high: '#F97316',
  medium: '#EAB308',
  low: '#22C55E',
}

const PIE_COLORS = ['#3B82F6', '#8B5CF6', '#EC4899', '#F97316', '#22C55E', '#06B6D4']

export default function DashboardPage() {
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [showWelcome, setShowWelcome] = useState(false)
  const [showPasswordChange, setShowPasswordChange] = useState(false)
  const userRole = getUserRole()
  const permissions = getRolePermissions(userRole)
  const notif = useNotifications()
  const roleColor = getRoleColor(userRole)
  const roleLabel = getRoleLabel(userRole)

  // Check authentication and default password
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      router.push('/login')
    } else {
      // Check if using default password
      const passwordChanged = localStorage.getItem('passwordChanged')
      const userStr = localStorage.getItem('user')

      if (!passwordChanged && userStr) {
        try {
          const userData = JSON.parse(userStr)
          // Check if using demo credentials (default passwords)
          const defaultEmails = ['demo@example.com', 'admin@example.com', 'lawyer@example.com', 'junior@example.com']
          if (defaultEmails.includes(userData.email)) {
            // Show password change dialog after welcome
            setTimeout(() => {
              setShowPasswordChange(true)
            }, 2000)
          }
        } catch (e) {
          // ignore parse errors
        }
      }

      // Show welcome message on first visit
      const hasSeenWelcome = sessionStorage.getItem('hasSeenWelcome')
      if (!hasSeenWelcome) {
        setShowWelcome(true)
        sessionStorage.setItem('hasSeenWelcome', 'true')
      }
    }
  }, [router])

  // Fetch current user
  const { data: userData, isLoading: userLoading } = useQuery({
    queryKey: ['currentUser'],
    queryFn: async () => {
      const user = await api.getCurrentUser()
      setUser(user)
      return user
    }
  })

  // Fetch recent contracts
  const { data: contractsData, isLoading: contractsLoading } = useQuery({
    queryKey: ['contracts', 'recent'],
    queryFn: async () => {
      const data = await api.listContracts({ page: 1, limit: 5 })
      return data
    }
  })

  // Fetch dashboard analytics
  const { data: dashboardData, isLoading: dashboardLoading } = useQuery<DashboardData>({
    queryKey: ['dashboard', 'analytics'],
    queryFn: () => api.getDashboard(30),
    retry: 1,
    staleTime: 60000,
  })

  // Fetch ML model status
  const { data: mlStatus } = useQuery<ModelStatus>({
    queryKey: ['ml', 'model-status'],
    queryFn: () => api.getModelStatus(),
    retry: 1,
    staleTime: 120000,
  })

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    toast.success('Вы вышли из системы', {
      style: { borderRadius: '12px' }
    })
    router.push('/login')
  }

  if (userLoading) {
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

  const contractsUsagePercent = ((user?.contracts_today || 0) / (user?.max_contracts_per_day || 1)) * 100
  const llmUsagePercent = ((user?.llm_requests_today || 0) / (user?.max_llm_requests_per_day || 1)) * 100

  // Prepare chart data
  const riskTrendData = (dashboardData?.risk_trends || []).map(t => ({
    date: new Date(t.date).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }),
    critical: t.critical_count,
    high: t.high_count,
    medium: t.medium_count,
    low: t.low_count,
  }))

  const riskDistributionData = (dashboardData?.risk_distribution || []).map(d => ({
    name: d.category,
    value: d.count,
  }))

  const headlineMetrics = dashboardData?.headline_metrics || {}

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-orange-50/20">
      {/* Modern Header */}
      <header className="bg-white/80 backdrop-blur-lg shadow-lg border-b border-white/20 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-4"
            >
              <div className="w-12 h-12 bg-primary-600 rounded-xl shadow-sm flex items-center justify-center">
                <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-stone-800">Contract AI System</h1>
                <p className="text-sm text-gray-600">Привет, {user?.name}!</p>
              </div>
            </motion.div>

            <div className="flex items-center space-x-4">
              <motion.div
                whileHover={{ scale: 1.05 }}
                className="px-4 py-2 bg-primary-600 text-white rounded-xl shadow-sm font-semibold text-sm"
              >
                {user?.subscription_tier.toUpperCase()}
              </motion.div>
              <NotificationBell
                notifications={notif.notifications}
                unreadCount={notif.unreadCount}
                isConnected={notif.isConnected}
                markAsRead={notif.markAsRead}
                markAllAsRead={notif.markAllAsRead}
                clearAll={notif.clearAll}
              />
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleLogout}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-xl transition-all duration-300"
              >
                Выход
              </motion.button>
            </div>
          </div>
        </div>
      </header>

      {/* Welcome Modal */}
      {showWelcome && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowWelcome(false)}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-3xl shadow-2xl max-w-2xl w-full p-8 max-h-[90vh] overflow-y-auto"
          >
            <div className="text-center mb-6">
              <div className={`inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br ${roleColor.gradient} mb-4`}>
                <svg className="h-10 w-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <h2 className="text-3xl font-bold text-stone-800 mb-2">
                Добро пожаловать, {user?.name || 'Пользователь'}!
              </h2>
              <p className={`text-lg font-semibold ${roleColor.text}`}>
                Ваша роль: {roleLabel}
              </p>
            </div>

            <div className={`p-6 rounded-2xl ${roleColor.bg} mb-6`}>
              <h3 className="text-xl font-bold text-stone-800 mb-4">
                Ваши возможности:
              </h3>
              <ul className="space-y-3">
                {permissions.features.map((feature, idx) => (
                  <motion.li
                    key={idx}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.3 + idx * 0.05 }}
                    className="flex items-center gap-3"
                  >
                    <span className="text-green-500 text-xl">✓</span>
                    <span className="text-stone-700">{feature}</span>
                  </motion.li>
                ))}
              </ul>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="p-4 bg-stone-50 rounded-xl text-center">
                <p className="text-sm text-stone-600 mb-1">Лимит договоров</p>
                <p className="text-2xl font-bold text-stone-800">
                  {permissions.maxContractsPerDay === -1 ? '∞' : permissions.maxContractsPerDay}
                </p>
                <p className="text-xs text-stone-500">в день</p>
              </div>
              <div className="p-4 bg-stone-50 rounded-xl text-center">
                <p className="text-sm text-stone-600 mb-1">Форматы экспорта</p>
                <p className="text-lg font-bold text-stone-800">
                  {permissions.exportFormats.join(', ').toUpperCase() || 'Нет'}
                </p>
              </div>
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setShowWelcome(false)}
              className={`w-full py-4 rounded-xl font-semibold text-white shadow-sm bg-primary-600 hover:bg-primary-700`}
            >
              Начать работу
            </motion.button>
          </motion.div>
        </motion.div>
      )}

      {/* Change Password Modal */}
      <ChangePasswordModal
        isOpen={showPasswordChange}
        onClose={() => setShowPasswordChange(false)}
        userEmail={user?.email || ''}
      />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Cards */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8"
        >
          {/* Contracts Card */}
          <motion.div variants={itemVariants} whileHover={{ y: -4 }} className="relative">
            <div className="card-modern overflow-hidden">
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-sm font-semibold text-gray-600 mb-1">Контракты сегодня</p>
                    <p className="text-4xl font-bold text-primary-700">
                      {user?.contracts_today || 0}
                      <span className="text-lg text-gray-400 font-normal"> / {user?.max_contracts_per_day}</span>
                    </p>
                  </div>
                  <motion.div
                    whileHover={{ scale: 1.05 }}
                    transition={{ duration: 0.3 }}
                    className="p-4 bg-primary-600 rounded-2xl shadow-sm"
                  >
                    <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </motion.div>
                </div>

                {/* Progress Bar */}
                <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${contractsUsagePercent}%` }}
                    transition={{ duration: 1, delay: 0.5 }}
                    className="absolute inset-y-0 left-0 bg-primary-600 rounded-full"
                  />
                </div>
                <p className="text-xs text-gray-500 mt-2">Использовано {contractsUsagePercent.toFixed(0)}%</p>
              </div>
            </div>
          </motion.div>

          {/* LLM Requests Card */}
          <motion.div variants={itemVariants} whileHover={{ y: -4 }} className="relative">
            <div className="card-modern overflow-hidden">
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-sm font-semibold text-gray-600 mb-1">LLM запросы</p>
                    <p className="text-4xl font-bold text-stone-800">
                      {user?.llm_requests_today || 0}
                      <span className="text-lg text-gray-400 font-normal"> / {user?.max_llm_requests_per_day}</span>
                    </p>
                  </div>
                  <motion.div
                    whileHover={{ scale: 1.05 }}
                    transition={{ type: "spring", stiffness: 300 }}
                    className="p-4 bg-stone-700 rounded-2xl shadow-sm"
                  >
                    <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </motion.div>
                </div>

                {/* Progress Bar */}
                <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${llmUsagePercent}%` }}
                    transition={{ duration: 1, delay: 0.7 }}
                    className="absolute inset-y-0 left-0 bg-stone-600 rounded-full"
                  />
                </div>
                <p className="text-xs text-gray-500 mt-2">Использовано {llmUsagePercent.toFixed(0)}%</p>
              </div>
            </div>
          </motion.div>

          {/* Subscription Card */}
          <motion.div variants={itemVariants} whileHover={{ y: -4 }} className="relative">
            <div className="card-modern overflow-hidden bg-gradient-to-br from-amber-50 to-orange-50">
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-sm font-semibold text-gray-600 mb-1">Тарифный план</p>
                    <p className="text-3xl font-bold text-stone-800 capitalize">
                      {user?.subscription_tier}
                    </p>
                  </div>
                  <motion.div
                    whileHover={{ scale: 1.05 }}
                    transition={{ duration: 0.3 }}
                    className="p-4 bg-accent-500 rounded-2xl shadow-sm"
                  >
                    <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </motion.div>
                </div>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => router.push('/pricing')}
                  className="w-full mt-2 py-2 bg-accent-500 hover:bg-accent-600 text-white font-semibold rounded-xl shadow-sm transition-all duration-300"
                >
                  Улучшить тариф
                </motion.button>
              </div>
            </div>
          </motion.div>
        </motion.div>

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="card-modern mb-8"
        >
          <h2 className="text-2xl font-bold text-stone-800 mb-6">Быстрые действия</h2>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {[
              { icon: <svg className="h-8 w-8 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>, label: 'Загрузить договор', route: '/contracts/upload', color: 'border-l-primary-500', permission: 'canAnalyze' },
              { icon: <svg className="h-8 w-8 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>, label: 'Генерировать', route: '/contracts/generate', color: 'border-l-violet-500', permission: 'canGenerate' },
              { icon: <svg className="h-8 w-8 text-success-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>, label: 'Все договоры', route: '/contracts', color: 'border-l-success-500', permission: null },
              { icon: <svg className="h-8 w-8 text-cyan-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>, label: 'Библиотека клаузул', route: '/clauses', color: 'border-l-cyan-500', permission: null },
              { icon: <svg className="h-8 w-8 text-accent-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>, label: 'Тарифы', route: '/pricing', color: 'border-l-accent-500', permission: null }
            ]
            .filter(action => !action.permission || permissions[action.permission as keyof typeof permissions])
            .map((action, idx) => (
              <motion.button
                key={idx}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.4 + idx * 0.1 }}
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => router.push(action.route)}
                className={`bg-white border-l-4 ${action.color} rounded-xl shadow-sm hover:shadow-md transition-all duration-300 p-5 text-left`}
              >
                <div className="mb-3">{action.icon}</div>
                <div className="text-base font-semibold text-stone-800">{action.label}</div>
              </motion.button>
            ))}
          </div>
        </motion.div>

        {/* Analytics Section */}
        {!dashboardLoading && dashboardData && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="mb-8"
          >
            <h2 className="text-2xl font-bold text-stone-800 mb-6">Аналитика</h2>

            {/* Headline Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              {Object.entries(headlineMetrics).map(([key, metric], idx) => (
                <motion.div
                  key={key}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.5 + idx * 0.05 }}
                  className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100"
                >
                  <p className="text-sm text-gray-500 mb-1">{metric.name}</p>
                  <div className="flex items-end gap-2">
                    <span className="text-3xl font-bold text-stone-800">
                      {metric.unit === 'USD' ? `$${metric.value.toLocaleString()}` : metric.value.toLocaleString()}
                    </span>
                    <span className="text-sm text-gray-400 mb-1">{metric.unit !== 'USD' ? metric.unit : ''}</span>
                  </div>
                  {metric.trend && metric.trend_percentage != null && metric.trend_percentage > 0 && (
                    <div className={`mt-2 text-sm font-medium ${
                      metric.trend === 'up' ? 'text-green-600' :
                      metric.trend === 'down' ? 'text-red-500' : 'text-gray-500'
                    }`}>
                      {metric.trend === 'up' ? '↑' : metric.trend === 'down' ? '↓' : '→'}{' '}
                      {metric.trend_percentage.toFixed(1)}% vs прошлый период
                    </div>
                  )}
                </motion.div>
              ))}
            </div>

            {/* Charts Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              {/* Risk Distribution PieChart */}
              {riskDistributionData.length > 0 && (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                  <h3 className="text-lg font-bold text-stone-800 mb-4">Распределение рисков</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={riskDistributionData}
                        cx="50%"
                        cy="50%"
                        outerRadius={100}
                        dataKey="value"
                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      >
                        {riskDistributionData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Risk Trends LineChart */}
              {riskTrendData.length > 0 && (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                  <h3 className="text-lg font-bold text-stone-800 mb-4">Тренды рисков (30 дней)</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={riskTrendData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="date" fontSize={12} />
                      <YAxis fontSize={12} />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="critical" name="Критические" stroke={RISK_COLORS.critical} strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="high" name="Высокие" stroke={RISK_COLORS.high} strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="medium" name="Средние" stroke={RISK_COLORS.medium} strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="low" name="Низкие" stroke={RISK_COLORS.low} strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* Top Risks BarChart */}
            {dashboardData.top_risks && dashboardData.top_risks.length > 0 && (
              <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 mb-6">
                <h3 className="text-lg font-bold text-stone-800 mb-4">Топ рисков</h3>
                <ResponsiveContainer width="100%" height={Math.max(250, dashboardData.top_risks.length * 40)}>
                  <BarChart
                    data={dashboardData.top_risks.slice(0, 8).map(r => ({
                      name: r.risk_type.length > 30 ? r.risk_type.substring(0, 30) + '...' : r.risk_type,
                      count: r.count,
                      severity: r.severity,
                    }))}
                    layout="vertical"
                    margin={{ left: 200 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis type="number" fontSize={12} />
                    <YAxis dataKey="name" type="category" fontSize={12} width={190} />
                    <Tooltip />
                    <Bar dataKey="count" name="Количество" fill="#3B82F6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Recommendations */}
            {dashboardData.recommendations && dashboardData.recommendations.length > 0 && (
              <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                <h3 className="text-lg font-bold text-stone-800 mb-4">Рекомендации</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {dashboardData.recommendations.map((rec, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl border-l-4 ${
                        rec.type === 'success' ? 'border-l-green-500 bg-green-50' :
                        rec.type === 'warning' ? 'border-l-yellow-500 bg-yellow-50' :
                        'border-l-blue-500 bg-blue-50'
                      }`}
                    >
                      <h4 className="font-semibold text-stone-800 mb-1">{rec.title}</h4>
                      <p className="text-sm text-stone-600">{rec.message}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ML Model Status Card */}
            {mlStatus && (
              <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 mt-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-stone-800">ML Модель</h3>
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                    mlStatus.is_trained ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                  }`}>
                    {mlStatus.is_trained ? 'Обучена' : 'Правила'}
                  </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-3 bg-gray-50 rounded-xl text-center">
                    <p className="text-xs text-gray-500 mb-1">Версия</p>
                    <p className="text-lg font-bold text-stone-800">{mlStatus.model_version}</p>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-xl text-center">
                    <p className="text-xs text-gray-500 mb-1">Тип</p>
                    <p className="text-lg font-bold text-stone-800">
                      {mlStatus.model_type === 'rules' ? 'Правила' : 'ML'}
                    </p>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-xl text-center">
                    <p className="text-xs text-gray-500 mb-1">Отзывы</p>
                    <p className="text-lg font-bold text-stone-800">{mlStatus.feedback_count}</p>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-xl text-center">
                    <p className="text-xs text-gray-500 mb-1">Точность</p>
                    <p className="text-lg font-bold text-stone-800">
                      {mlStatus.accuracy != null ? `${(mlStatus.accuracy * 100).toFixed(1)}%` : '—'}
                    </p>
                  </div>
                </div>
                {mlStatus.unused_feedback_count > 0 && (
                  <p className="text-xs text-amber-600 mt-3">
                    {mlStatus.unused_feedback_count} отзыв(ов) ожидают переобучения модели
                  </p>
                )}
                {mlStatus.last_training && (
                  <p className="text-xs text-gray-400 mt-2">
                    Последнее обучение: {new Date(mlStatus.last_training).toLocaleDateString('ru-RU')}
                  </p>
                )}
              </div>
            )}
          </motion.div>
        )}

        {/* Recent Contracts */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="card-modern"
        >
          <h2 className="text-2xl font-bold text-stone-800 mb-6">Последние договоры</h2>

          {contractsLoading ? (
            <div className="flex justify-center py-12">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full"
              />
            </div>
          ) : contractsData && contractsData.contracts?.length > 0 ? (
            <div className="space-y-3">
              {contractsData.contracts.map((contract: Contract, idx: number) => (
                <motion.div
                  key={contract.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.6 + idx * 0.1 }}
                  whileHover={{ x: 4 }}
                  onClick={() => router.push(`/contracts/${contract.id}`)}
                  className="p-5 bg-gradient-to-r from-white to-gray-50 rounded-xl border border-gray-100 hover:border-primary-300 cursor-pointer transition-all duration-300 hover:shadow-lg"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4 flex-1">
                      <div className="w-12 h-12 bg-primary-600 rounded-xl flex items-center justify-center shadow-sm">
                        <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 mb-1">{contract.file_name}</h3>
                        <div className="flex items-center space-x-3 text-sm text-gray-600">
                          <span className="flex items-center">
                            <svg className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                            </svg>
                            {contract.contract_type}
                          </span>
                          <span className="flex items-center">
                            <svg className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            {new Date(contract.created_at).toLocaleDateString('ru-RU')}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3">
                      <span className={`px-4 py-2 rounded-full text-sm font-semibold
                        ${contract.status === 'completed' ? 'badge-success' : ''}
                        ${contract.status === 'analyzing' ? 'badge-warning' : ''}
                        ${contract.status === 'uploaded' ? 'bg-primary-100 text-primary-800' : ''}
                        ${contract.status === 'error' ? 'badge-danger' : ''}
                      `}>
                        {contract.status}
                      </span>
                      <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-center py-16"
            >
              <motion.div
                animate={{ y: [0, -10, 0] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="inline-block mb-6"
              >
                <div className="w-24 h-24 bg-primary-600 rounded-3xl shadow-lg flex items-center justify-center">
                  <svg className="h-12 w-12 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                </div>
              </motion.div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Нет договоров</h3>
              <p className="text-gray-600 mb-6">Начните с загрузки вашего первого договора</p>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => router.push('/contracts/upload')}
                className="inline-flex items-center px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white font-semibold rounded-xl shadow-sm transition-all duration-300"
              >
                <svg className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Загрузить договор
              </motion.button>
            </motion.div>
          )}
        </motion.div>
      </main>
    </div>
  )
}
