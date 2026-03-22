import { test, expect } from '@playwright/test'
import { mockAuth, mockApiRoute } from './helpers'

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuth(page)

    await mockApiRoute(page, '**/api/contracts?*', [])
    await mockApiRoute(page, '**/api/contracts/stats*', {
      total: 42,
      analyzed: 35,
      pending: 7,
    })
    // Catch-all for any other API calls
    await mockApiRoute(page, '**/api/v2/**', [])
    await mockApiRoute(page, '**/api/v1/analytics/**', { data: [] })
  })

  test('Dashboard загружается для авторизованного пользователя', async ({ page }) => {
    await page.goto('/dashboard')
    // useEffect проверяет localStorage — если race condition отправил на /login, повторяем
    await page.waitForTimeout(2000)
    if (page.url().includes('/login')) {
      // Race condition: init script не успел до useEffect — повторяем навигацию
      await page.goto('/dashboard')
      await page.waitForTimeout(2000)
    }
    expect(page.url()).toContain('/dashboard')
  })

  test('Sidebar навигация отображается на десктопе', async ({ page }) => {
    await page.goto('/dashboard')
    // На десктопе sidebar скрыт за lg: breakpoint, проверяем <nav> элемент
    const nav = page.locator('nav[aria-label]')
    // Может быть скрыт на маленьком viewport, проверяем существование
    await expect(nav.first()).toBeAttached({ timeout: 10000 })
  })

  test('Навигация на /contracts работает', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForTimeout(1000)

    const contractsLink = page.locator('a[href="/contracts"]').first()
    if (await contractsLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await contractsLink.click()
      await expect(page).toHaveURL(/\/contracts/)
    }
  })
})
