import { test, expect } from '@playwright/test'

test.describe('Публичные страницы', () => {
  test('Главная страница загружается', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/Contract/)
    // Должны быть вход и переход к персональному демо
    await expect(page.getByRole('link', { name: /войти|вход|login/i })).toBeVisible()
  })

  test('Страница логина отображает форму', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('input[type="text"], input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.getByRole('button', { name: /войти|вход|login/i })).toBeVisible()
  })

  test('Старая регистрация ведёт на заявку демо', async ({ page }) => {
    await page.goto('/register')
    await expect(page).toHaveURL(/\/demo$/)
    await expect(page.getByRole('button', { name: /отправить заявку/i })).toBeVisible()
  })

  test('Страница тарифов загружается', async ({ page }) => {
    await page.goto('/pricing')
    await expect(page.locator('body')).toContainText(/тариф|pricing|план|plan/i)
  })

  test('Демо-страница загружается', async ({ page }) => {
    await page.goto('/demo')
    await expect(page.getByRole('heading', { name: /проверьте систему/i })).toBeVisible()
    await expect(page.getByLabel(/телефон или telegram/i)).toBeVisible()
  })
})

test.describe('Редиректы авторизации', () => {
  test('Защищённые страницы редиректят на /login без токена', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/)
  })

  test('Страница контрактов редиректит на /login без токена', async ({ page }) => {
    await page.goto('/contracts')
    await expect(page).toHaveURL(/\/login/)
  })

  test('/login с redirect параметром сохраняет redirect', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login\?redirect=%2Fdashboard/)
  })
})
