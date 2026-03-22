import { test, expect } from '@playwright/test'
import { mockAuth, mockApiRoute } from './helpers'

test.describe('Phase 12 страницы', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuth(page)
    // Catch-all for v2 API
    await mockApiRoute(page, '**/api/v2/**', [])
    await mockApiRoute(page, '**/api/contracts?*', [])
    await mockApiRoute(page, '**/api/v1/analytics/**', { data: [] })
  })

  test.describe('AI Workspace (/ai)', () => {
    test('Страница загружается', async ({ page }) => {
      await page.goto('/ai')
      await page.waitForTimeout(2000)
      // Не редиректит на login
      expect(page.url()).not.toContain('/login')
    })
  })

  test.describe('Переговоры (/negotiations)', () => {
    test('Страница загружается', async ({ page }) => {
      await page.goto('/negotiations')
      await page.waitForTimeout(2000)
      expect(page.url()).not.toContain('/login')
    })
  })

  test.describe('Workflow (/workflow)', () => {
    test('Страница загружается', async ({ page }) => {
      await page.goto('/workflow')
      await page.waitForTimeout(2000)
      expect(page.url()).not.toContain('/login')
    })
  })

  test.describe('Администрирование (/admin)', () => {
    test('Страница загружается', async ({ page }) => {
      await page.goto('/admin')
      await page.waitForTimeout(2000)
      expect(page.url()).not.toContain('/login')
    })

    test('Все 5 вкладок доступны', async ({ page }) => {
      await page.goto('/admin')
      await page.waitForTimeout(3000)

      // Если страница загрузилась (не login), проверяем вкладки
      if (!page.url().includes('/login')) {
        const tabNames = ['Организации', 'Политики', 'Инструменты', 'Агенты', 'Шаблоны']
        for (const name of tabNames) {
          await expect(page.getByRole('button', { name })).toBeVisible({ timeout: 5000 })
        }
      }
    })

    test('Вкладка "Шаблоны" открывается', async ({ page }) => {
      await page.goto('/admin')
      await page.waitForTimeout(3000)

      if (!page.url().includes('/login')) {
        await page.getByRole('button', { name: 'Шаблоны' }).click()
        await expect(page.locator('text=Политики клауз')).toBeVisible({ timeout: 5000 })
      }
    })

    test('Создание организации — UI flow', async ({ page }) => {
      await page.goto('/admin')
      await page.waitForTimeout(3000)

      if (!page.url().includes('/login')) {
        // Кликаем "+ Создать"
        const createBtn = page.getByText('+ Создать').first()
        await createBtn.click()
        await expect(page.locator('input[placeholder*="Название"]')).toBeVisible()
      }
    })

    test('Вкладка "Политики"', async ({ page }) => {
      await page.goto('/admin')
      await page.waitForTimeout(3000)

      if (!page.url().includes('/login')) {
        await page.getByRole('button', { name: 'Политики' }).click()
        await expect(page.getByRole('button', { name: 'Все' })).toBeVisible()
      }
    })

    test('Вкладка "Инструменты"', async ({ page }) => {
      await page.goto('/admin')
      await page.waitForTimeout(3000)

      if (!page.url().includes('/login')) {
        await page.getByRole('button', { name: 'Инструменты' }).click()
        await expect(page.locator('body')).toContainText(/инструмент/i)
      }
    })

    test('Вкладка "Агенты"', async ({ page }) => {
      await page.goto('/admin')
      await page.waitForTimeout(3000)

      if (!page.url().includes('/login')) {
        await page.getByRole('button', { name: 'Агенты' }).click()
        await expect(page.locator('body')).toContainText(/агент/i)
      }
    })
  })
})
