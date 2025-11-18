/**
 * Login Page Component
 */

import React, { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'react-hot-toast';
import api from '../services/api';

// Validation schema
const loginSchema = z.object({
  email: z.string().email('Неверный формат email'),
  password: z.string().min(8, 'Минимум 8 символов'),
});

type LoginFormData = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true);

    try {
      const response = await api.login({
        username: data.email,
        password: data.password,
      });

      toast.success(`Добро пожаловать, ${response.user.name}!`);
      router.push('/dashboard');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Ошибка входа';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-secondary-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Contract AI System
          </h1>
          <h2 className="text-2xl font-semibold text-gray-700">
            Вход в систему
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Или{' '}
            <Link href="/register" className="font-medium text-primary-600 hover:text-primary-500">
              зарегистрируйтесь
            </Link>
            {' '}для создания аккаунта
          </p>
        </div>

        {/* Login Form */}
        <div className="mt-8 bg-white py-8 px-6 shadow-xl rounded-lg">
          <form className="space-y-6" onSubmit={handleSubmit(onSubmit)}>
            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                {...register('email')}
                type="email"
                autoComplete="email"
                className={`mt-1 block w-full px-3 py-2 border ${
                  errors.email ? 'border-red-500' : 'border-gray-300'
                } rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500`}
                placeholder="user@example.com"
              />
              {errors.email && (
                <p className="mt-1 text-sm text-red-600">{errors.email.message}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Пароль
              </label>
              <input
                {...register('password')}
                type="password"
                autoComplete="current-password"
                className={`mt-1 block w-full px-3 py-2 border ${
                  errors.password ? 'border-red-500' : 'border-gray-300'
                } rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500`}
                placeholder="••••••••"
              />
              {errors.password && (
                <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
              )}
            </div>

            {/* Remember me & Forgot password */}
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <input
                  id="remember-me"
                  name="remember-me"
                  type="checkbox"
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                />
                <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-900">
                  Запомнить меня
                </label>
              </div>

              <div className="text-sm">
                <Link
                  href="/forgot-password"
                  className="font-medium text-primary-600 hover:text-primary-500"
                >
                  Забыли пароль?
                </Link>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <span className="flex items-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Вход...
                </span>
              ) : (
                'Войти'
              )}
            </button>
          </form>

          {/* Quick demo login */}
          <div className="mt-6 border-t border-gray-200 pt-6">
            <p className="text-xs text-center text-gray-500 mb-3">
              Для тестирования используйте demo аккаунты:
            </p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                onClick={() => {
                  onSubmit({ email: 'demo@example.com', password: 'demopass123' });
                }}
                className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded text-gray-700"
              >
                🔵 DEMO
              </button>
              <button
                onClick={() => {
                  onSubmit({ email: 'admin@example.com', password: 'adminpass123' });
                }}
                className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded text-gray-700"
              >
                🔴 ADMIN
              </button>
            </div>
          </div>
        </div>

        {/* Demo link */}
        <div className="text-center">
          <p className="text-sm text-gray-600">
            Хотите попробовать без регистрации?{' '}
            <Link href="/demo" className="font-medium text-secondary-600 hover:text-secondary-500">
              Получить демо-доступ
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
