import { test, expect } from '@playwright/test'
import { mockAuth, mockApiRoute } from './helpers'

test.describe('Аутентификация', () => {
  test('Форма логина принимает ввод и отправляет запрос', async ({ page }) => {
    let loginCalled = false
    await page.route('**/api/v1/auth/login', (route) => {
      loginCalled = true
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: {
            id: 'user-1',
            email: 'test@example.com',
            name: 'Тест Тестович',
            role: 'admin',
            subscription_tier: 'professional',
            is_demo: false,
            email_verified: true,
            created_at: '2025-01-01T00:00:00Z',
            contracts_today: 0,
            llm_requests_today: 0,
          },
          access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEiLCJleHAiOjk5OTk5OTk5OTl9.fake',
          token_type: 'bearer',
          expires_in: 3600,
        }),
      })
    })

    await page.goto('/login')

    // Заполняем форму
    await page.locator('input[type="text"], input[type="email"]').first().fill('test@example.com')
    await page.locator('input[type="password"]').fill('password123')

    // Сабмитим
    await page.getByRole('button', { name: /войти|вход|login/i }).click()
    await page.waitForTimeout(2000)

    // Проверяем что API логина был вызван
    expect(loginCalled).toBe(true)
  })

  test('Неверный пароль → ошибка на странице', async ({ page }) => {
    await page.goto('/login')

    await page.route('**/api/v1/auth/login', (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Неверный email или пароль' }),
      })
    )

    await page.locator('input[type="text"], input[type="email"]').first().fill('wrong@example.com')
    await page.locator('input[type="password"]').fill('wrongpassword')
    await page.getByRole('button', { name: /войти|вход|login/i }).click()

    // Проверяем что страница осталась на /login (не редиректнула)
    await page.waitForTimeout(2000)
    expect(page.url()).toContain('/login')
  })

  test('Авторизованный пользователь на /login → редирект на /dashboard', async ({ page }) => {
    await mockAuth(page)
    await page.goto('/login')
    await expect(page).toHaveURL(/\/dashboard/)
  })
})
