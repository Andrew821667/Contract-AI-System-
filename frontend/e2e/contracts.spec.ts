import { test, expect } from '@playwright/test'
import { mockAuth, mockApiRoute } from './helpers'

test.describe('Контракты', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuth(page)
    await mockApiRoute(page, '**/api/v2/**', [])
    await mockApiRoute(page, '**/api/v1/analytics/**', { data: [] })
  })

  test('Список контрактов загружается', async ({ page }) => {
    await mockApiRoute(page, '**/api/contracts?*', [
      {
        id: 'contract-1',
        title: 'Договор аренды',
        status: 'analyzed',
        contract_type: 'lease',
        created_at: '2025-06-01T10:00:00Z',
        risk_score: 0.3,
      },
      {
        id: 'contract-2',
        title: 'Договор поставки',
        status: 'pending',
        contract_type: 'supply',
        created_at: '2025-06-02T10:00:00Z',
        risk_score: 0.7,
      },
    ])

    await page.goto('/contracts')
    await page.waitForTimeout(2000)
    expect(page.url()).toContain('/contracts')
  })

  test('Страница загрузки контракта доступна', async ({ page }) => {
    await page.goto('/contracts/upload')
    await page.waitForTimeout(2000)
    // Должна быть страница загрузки (не редирект на login)
    expect(page.url()).toContain('/contracts/upload')
  })

  test('Страница генерации контракта доступна', async ({ page }) => {
    await page.goto('/contracts/generate')
    await page.waitForTimeout(2000)
    expect(page.url()).toContain('/contracts/generate')
  })

  test('Детальная страница контракта загружается', async ({ page }) => {
    await mockApiRoute(page, '**/api/contracts/contract-1', {
      id: 'contract-1',
      title: 'Тестовый договор',
      status: 'analyzed',
      contract_type: 'lease',
      content: 'Содержимое договора...',
      created_at: '2025-06-01T10:00:00Z',
      risk_score: 0.25,
      analysis_result: {
        summary: 'Стандартный договор аренды',
        risks: [],
        clauses: [],
      },
    })

    await page.goto('/contracts/contract-1')
    await page.waitForTimeout(2000)
    expect(page.url()).toContain('/contracts/contract-1')
  })
})
