/**
 * Русские подписи для статусов системы.
 * Используй getStatusLabel() вместо вывода сырых English-значений.
 */

const contractStatusMap: Record<string, string> = {
  pending: 'Ожидает',
  uploaded: 'Загружен',
  parsing: 'Разбор',
  analyzing: 'Анализ',
  reviewing: 'Проверка',
  completed: 'Завершён',
  error: 'Ошибка',
}

const riskLevelMap: Record<string, string> = {
  CRITICAL: 'Критический',
  HIGH: 'Высокий',
  MEDIUM: 'Средний',
  LOW: 'Низкий',
}

const taskStatusMap: Record<string, string> = {
  pending: 'Ожидает',
  in_review: 'На проверке',
  approved: 'Одобрено',
  rejected: 'Отклонено',
  completed: 'Завершено',
}

export function getContractStatusLabel(status: string): string {
  return contractStatusMap[status] || status
}

export function getRiskLevelLabel(level: string): string {
  return riskLevelMap[level] || level
}

export function getTaskStatusLabel(status: string): string {
  return taskStatusMap[status] || status
}

/** CSS-класс для бейджа статуса контракта */
export function getContractStatusClass(status: string): string {
  switch (status) {
    case 'completed': return 'badge-success'
    case 'analyzing':
    case 'reviewing':
    case 'parsing': return 'badge-warning'
    case 'uploaded':
    case 'pending': return 'bg-primary-100 text-primary-800'
    case 'error': return 'badge-danger'
    default: return 'bg-gray-100 text-gray-800'
  }
}
