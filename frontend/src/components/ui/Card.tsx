import { motion } from 'framer-motion'
import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  hover?: boolean
  gradient?: boolean
  className?: string
  onClick?: () => void
}

export default function Card({
  children,
  hover = false,
  gradient = false,
  className = '',
  onClick
}: CardProps) {
  const hasBg = className.includes('bg-')
  const hasBorder = className.includes('border-')
  const baseStyles = `${hasBg ? '' : 'bg-white'} rounded-2xl shadow-card p-6 ${hasBorder ? '' : 'border border-gray-100'}`
  const hoverStyles = hover ? 'hover:shadow-card-hover cursor-pointer' : ''
  const gradientStyles = gradient ? 'bg-gradient-to-br from-white to-gray-50' : ''

  const isInteractive = !!onClick

  return (
    <motion.div
      whileHover={hover ? { y: -4 } : {}}
      onClick={onClick}
      role={isInteractive ? 'button' : undefined}
      tabIndex={isInteractive ? 0 : undefined}
      onKeyDown={isInteractive ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick?.()
        }
      } : undefined}
      className={`
        ${baseStyles}
        ${hoverStyles}
        ${gradientStyles}
        ${className}
        transition-all duration-300
        ${isInteractive ? 'focus:outline-none focus:ring-2 focus:ring-primary-400 focus:ring-offset-2' : ''}
      `}
    >
      {children}
    </motion.div>
  )
}
