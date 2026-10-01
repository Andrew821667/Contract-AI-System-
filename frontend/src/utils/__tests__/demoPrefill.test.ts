import { demoRequestHref, demoTaskPrefill, PASSWORD_RESET_HREF } from '../demoPrefill'

const params = (query: string) => new URLSearchParams(query)

describe('demoPrefill', () => {
  it('ведёт кнопку тарифа на заявку с тарифом', () => {
    expect(demoRequestHref('Команда')).toBe('/demo?plan=%D0%9A%D0%BE%D0%BC%D0%B0%D0%BD%D0%B4%D0%B0')
    expect(demoTaskPrefill(params('plan=Команда'))).toBe('Интересует тариф «Команда».')
  })

  it('подставляет просьбу восстановить доступ', () => {
    expect(demoTaskPrefill(params(PASSWORD_RESET_HREF.split('?')[1]))).toContain('восстановить доступ')
  })

  it('ничего не подставляет без параметров и режет мусор', () => {
    expect(demoTaskPrefill(params(''))).toBe('')
    const long = demoTaskPrefill(params(`plan=${'x'.repeat(200)}<script>`))
    expect(long.length).toBeLessThan(90)
    expect(long).not.toContain('<')
  })
})
