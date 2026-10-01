// Доступ к Contract AI — персональный демо по заявке: регистрации и оплаты
// на сайте нет. Кнопки тарифов и «Забыли пароль?» ведут на форму заявки
// и подставляют в поле задачи, о чём просит человек.

const MAX_PLAN_LENGTH = 60

export function demoRequestHref(plan: string): string {
  return `/demo?plan=${encodeURIComponent(plan)}`
}

export const PASSWORD_RESET_HREF = '/demo?reason=reset'

export function demoTaskPrefill(params: { get(name: string): string | null }): string {
  if (params.get('reason') === 'reset') {
    return 'Забыл пароль — прошу восстановить доступ к аккаунту.'
  }
  const plan = (params.get('plan') || '').replace(/[\r\n<>]/g, ' ').trim().slice(0, MAX_PLAN_LENGTH)
  return plan ? `Интересует тариф «${plan}».` : ''
}
