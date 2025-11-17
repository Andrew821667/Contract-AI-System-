/**
 * Contract AI Demo Button Component
 *
 * Добавьте этот компонент на ваш Next.js сайт (Vessel)
 * для интеграции со системой Contract AI
 */

import { useState } from 'react';

interface ContractAIDemoProps {
  /** URL вашей Contract AI системы (Ngrok или домен) */
  demoUrl: string;
  /** Стиль кнопки: 'button' | 'card' | 'banner' */
  variant?: 'button' | 'card' | 'banner';
  /** Цветовая тема */
  theme?: 'light' | 'dark';
}

export function ContractAIDemo({
  demoUrl,
  variant = 'button',
  theme = 'light'
}: ContractAIDemoProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Вариант 1: Простая кнопка
  if (variant === 'button') {
    return (
      <a
        href={demoUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-lg transition-all duration-200 hover:scale-105"
      >
        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        Попробовать AI Анализ Договоров
      </a>
    );
  }

  // Вариант 2: Карточка с описанием
  if (variant === 'card') {
    return (
      <div className={`max-w-md rounded-xl shadow-2xl p-6 ${theme === 'dark' ? 'bg-gray-800 text-white' : 'bg-white'}`}>
        <div className="flex items-center mb-4">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h3 className="ml-4 text-xl font-bold">Contract AI System</h3>
        </div>

        <p className={`mb-4 ${theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}`}>
          Интеллектуальная система анализа и генерации договоров с использованием AI
        </p>

        <div className="space-y-2 mb-6">
          <div className="flex items-center text-sm">
            <svg className="w-5 h-5 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            Анализ рисков за 30 секунд
          </div>
          <div className="flex items-center text-sm">
            <svg className="w-5 h-5 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            Генерация документов
          </div>
          <div className="flex items-center text-sm">
            <svg className="w-5 h-5 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            Поддержка всех форматов
          </div>
        </div>

        <a
          href={demoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold rounded-lg shadow-lg transition-all duration-200 hover:scale-105"
        >
          Попробовать бесплатно →
        </a>
      </div>
    );
  }

  // Вариант 3: Баннер (полная ширина)
  if (variant === 'banner') {
    return (
      <div className={`w-full rounded-2xl shadow-xl p-8 ${theme === 'dark' ? 'bg-gradient-to-r from-gray-800 to-gray-900' : 'bg-gradient-to-r from-blue-50 to-purple-50'}`}>
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex-1">
            <h2 className={`text-3xl font-bold mb-2 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
              Автоматизируйте работу с договорами
            </h2>
            <p className={`text-lg mb-4 ${theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}`}>
              AI-система анализа и генерации юридических документов.
              Экономьте до 80% времени юристов.
            </p>
            <div className="flex flex-wrap gap-4 text-sm">
              <span className="flex items-center">
                <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                Claude + GPT-4
              </span>
              <span className="flex items-center">
                <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                RAG система
              </span>
              <span className="flex items-center">
                <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                ML предсказания
              </span>
            </div>
          </div>

          <div className="flex-shrink-0">
            <a
              href={demoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white text-lg font-bold rounded-xl shadow-2xl transition-all duration-200 hover:scale-105"
            >
              Попробовать демо
              <svg className="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </a>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

// Пример использования:
export function ExampleUsage() {
  return (
    <div className="p-8 space-y-8">
      {/* Простая кнопка */}
      <ContractAIDemo
        demoUrl="https://your-ngrok-url.ngrok-free.app"
        variant="button"
      />

      {/* Карточка */}
      <ContractAIDemo
        demoUrl="https://your-ngrok-url.ngrok-free.app"
        variant="card"
        theme="light"
      />

      {/* Баннер */}
      <ContractAIDemo
        demoUrl="https://your-ngrok-url.ngrok-free.app"
        variant="banner"
        theme="dark"
      />
    </div>
  );
}
