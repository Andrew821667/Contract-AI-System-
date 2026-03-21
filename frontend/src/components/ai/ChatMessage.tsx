'use client'

import { motion } from 'framer-motion'
import { sanitizeHTML } from '@/utils/sanitize'
import type { AIMessage } from '@/services/api'

/** Simple markdown-to-HTML: bold, italic, code, code blocks, lists, headers, links */
function markdownToHTML(text: string): string {
  let html = text
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Headers
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // Ordered lists
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // Paragraphs (double newline)
    .replace(/\n\n/g, '</p><p>')
    // Single newlines
    .replace(/\n/g, '<br/>')

  // Wrap consecutive <li> in <ul>
  html = html.replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul>$1</ul>')

  return `<p>${html}</p>`
}

interface ChatMessageProps {
  message: AIMessage
  compact?: boolean
}

export default function ChatMessage({ message, compact }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  if (isSystem) {
    return (
      <div className="flex justify-center my-2">
        <span className="text-xs text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-dark-800 px-3 py-1 rounded-full">
          {message.content}
        </span>
      </div>
    )
  }

  const rendered = sanitizeHTML(markdownToHTML(message.content))

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} ${compact ? 'mb-2' : 'mb-4'}`}
    >
      {/* Avatar */}
      {!isUser && (
        <div className="flex-shrink-0 mr-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
        </div>
      )}

      {/* Bubble */}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${compact ? 'text-sm' : 'text-sm'} ${
          isUser
            ? 'bg-primary-600 text-white rounded-br-md'
            : 'bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-700 text-gray-800 dark:text-gray-200 rounded-bl-md'
        }`}
      >
        <div
          className={`prose prose-sm max-w-none ${
            isUser
              ? 'prose-invert'
              : 'dark:prose-invert'
          } [&_pre]:bg-gray-100 [&_pre]:dark:bg-dark-900 [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-x-auto [&_code]:text-xs [&_p]:my-1 [&_ul]:my-1 [&_li]:my-0`}
          dangerouslySetInnerHTML={{ __html: rendered }}
        />
        <div className={`text-[10px] mt-1 ${isUser ? 'text-primary-200' : 'text-gray-400 dark:text-gray-500'}`}>
          {new Date(message.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="flex-shrink-0 ml-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-stone-400 to-stone-600 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
        </div>
      )}
    </motion.div>
  )
}
