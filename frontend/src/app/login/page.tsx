'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Auto login on page load
    console.log('AUTO LOGIN - AUTH DISABLED')
    autoLogin()
  }, [])

  const autoLogin = async () => {
    // Mock login - just set admin user in localStorage
    const mockUser = {
      id: "admin-001",
      email: "admin@test.com",
      name: "Administrator",
      role: "admin",
      subscription_tier: "enterprise"
    }

    localStorage.setItem('access_token', 'mock_token_' + Date.now())
    localStorage.setItem('user', JSON.stringify(mockUser))

    toast.success(`Добро пожаловать, ${mockUser.name}! (AUTH DISABLED)`, {
      icon: '🎉',
      style: {
        borderRadius: '12px',
        background: 'linear-gradient(135deg, #0ea5e9, #d946ef)',
        color: '#fff',
      },
    })

    setTimeout(() => {
      window.location.href = '/dashboard'
    }, 1000)
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    console.log('DISABLED AUTH - auto login as admin')

    setIsLoading(true)

    // Mock login - just set admin user in localStorage
    const mockUser = {
      id: "admin-001",
      email: "admin@test.com",
      name: "Administrator",
      role: "admin",
      subscription_tier: "enterprise"
    }

    localStorage.setItem('access_token', 'mock_token_' + Date.now())
    localStorage.setItem('user', JSON.stringify(mockUser))

    toast.success(`Добро пожаловать, ${mockUser.name}! (AUTH DISABLED)`, {
      icon: '🎉',
      style: {
        borderRadius: '12px',
        background: 'linear-gradient(135deg, #0ea5e9, #d946ef)',
        color: '#fff',
      },
    })

    setTimeout(() => {
      window.location.href = '/dashboard'
    }, 100)

    setIsLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-500 via-secondary-500 to-accent-500">
      <div className="text-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-white mx-auto mb-8"></div>
        <h1 className="text-4xl font-bold text-white mb-4">Contract AI System</h1>
        <p className="text-xl text-white/80 mb-4">Аутентификация отключена</p>
        <p className="text-lg text-white/60">Автоматический вход как администратор...</p>
      </div>
    </div>
  )
}
