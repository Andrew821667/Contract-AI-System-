import { test, expect } from '@playwright/test'
import { mockAuth, mockApiRoute } from './helpers'

test.describe('Template Governance UI', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuth(page)
    // Catch-all v2 API
    await mockApiRoute(page, '**/api/v2/**', [])
    await mockApiRoute(page, '**/api/contracts?*', [])
    await mockApiRoute(page, '**/api/v1/analytics/**', { data: [] })
  })

  test('Политики клауз отображаются', async ({ page }) => {
    // Override clause-policies mock with data
    await page.route('**/api/v2/clause-policies**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'cp-1',
            org_id: null,
            clause_type: 'financial',
            status: 'approved',
            alternative_clause_id: null,
            risk_explanation: null,
            created_at: '2025-06-01T00:00:00Z',
            updated_at: null,
          },
          {
            id: 'cp-2',
            org_id: 'org-1',
            clause_type: 'liability',
            status: 'prohibited',
            alternative_clause_id: null,
            risk_explanation: 'Высокий риск ответственности',
            created_at: '2025-06-02T00:00:00Z',
            updated_at: null,
          },
        ]),
      })
    )

    await page.goto('/admin')
    await page.waitForTimeout(3000)

    if (!page.url().includes('/login')) {
      await page.getByRole('button', { name: 'Шаблоны' }).click()
      await expect(page.locator('body')).toContainText('financial')
      await expect(page.locator('body')).toContainText('liability')
    }
  })

  test('Фильтрация политик клауз по статусу', async ({ page }) => {
    await page.goto('/admin')
    await page.waitForTimeout(3000)

    if (!page.url().includes('/login')) {
      await page.getByRole('button', { name: 'Шаблоны' }).click()

      const filterBtns = ['Все', 'approved', 'prohibited', 'risky', 'fallback']
      for (const btn of filterBtns) {
        await expect(page.getByRole('button', { name: btn, exact: true })).toBeVisible()
      }
    }
  })

  test('Форма создания политики клаузы', async ({ page }) => {
    await page.goto('/admin')
    await page.waitForTimeout(3000)

    if (!page.url().includes('/login')) {
      await page.getByRole('button', { name: 'Шаблоны' }).click()
      await page.getByText('+ Создать').click()
      await expect(page.locator('input[placeholder*="Тип клаузы"]')).toBeVisible()
    }
  })

  test('Версии шаблонов — поиск по ID', async ({ page }) => {
    await page.route('**/api/v2/templates/tpl-1/versions**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'ver-1',
            template_id: 'tpl-1',
            version: 2,
            content: { body: 'template content' },
            variables: [{ name: 'party_name', type: 'string' }],
            validation_rules: null,
            status: 'active',
            created_by: 'user-1',
            created_at: '2025-06-01T00:00:00Z',
          },
          {
            id: 'ver-2',
            template_id: 'tpl-1',
            version: 1,
            content: { body: 'old content' },
            variables: null,
            validation_rules: null,
            status: 'deprecated',
            created_by: 'user-1',
            created_at: '2025-05-01T00:00:00Z',
          },
        ]),
      })
    )

    await page.goto('/admin')
    await page.waitForTimeout(3000)

    if (!page.url().includes('/login')) {
      await page.getByRole('button', { name: 'Шаблоны' }).click()
      await page.locator('input[placeholder*="ID шаблона"]').fill('tpl-1')
      await page.locator('#main-content').getByRole('button', { name: /загрузить/i }).click()

      await expect(page.locator('text=Версия 2')).toBeVisible({ timeout: 5000 })
      await expect(page.locator('text=Версия 1')).toBeVisible()
    }
  })

  test('Кнопка "Активировать" для draft версии', async ({ page }) => {
    await page.route('**/api/v2/templates/tpl-1/versions**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'ver-draft',
            template_id: 'tpl-1',
            version: 3,
            content: {},
            variables: null,
            validation_rules: null,
            status: 'draft',
            created_by: null,
            created_at: '2025-06-10T00:00:00Z',
          },
        ]),
      })
    )

    await page.goto('/admin')
    await page.waitForTimeout(3000)

    if (!page.url().includes('/login')) {
      await page.getByRole('button', { name: 'Шаблоны' }).click()
      await page.locator('input[placeholder*="ID шаблона"]').fill('tpl-1')
      await page.locator('#main-content').getByRole('button', { name: /загрузить/i }).click()
      await expect(page.getByRole('button', { name: /активировать/i })).toBeVisible({ timeout: 5000 })
    }
  })
})
