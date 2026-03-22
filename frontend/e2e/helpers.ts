import { Page } from '@playwright/test'

/**
 * Создаёт фейковый JWT с exp далеко в будущем.
 */
function makeFakeJwt(): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const payload = btoa(
    JSON.stringify({
      sub: 'e2e-user-id',
      exp: Math.floor(Date.now() / 1000) + 86400, // +24h
    })
  )
  // base64url encoding
  const h = header.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const p = payload.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${h}.${p}.fake-signature`
}

const FAKE_JWT = makeFakeJwt()

const MOCK_USER = {
  id: 'e2e-user-id',
  email: 'test@example.com',
  name: 'E2E Тестер',
  role: 'admin',
  subscription_tier: 'enterprise',
  is_demo: false,
  email_verified: true,
  created_at: '2025-01-01T00:00:00Z',
  contracts_today: 0,
  llm_requests_today: 0,
}

/**
 * Устанавливает auth-токен в localStorage и cookie, имитируя залогиненного пользователя.
 * Мокирует /auth/me и /auth/refresh чтобы useAuthGuard не редиректил на /login.
 */
export async function mockAuth(page: Page) {
  // Cookie для middleware
  await page.context().addCookies([
    {
      name: 'has_token',
      value: '1',
      domain: 'localhost',
      path: '/',
    },
  ])

  // Мокируем auth API endpoints
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_USER),
    })
  )
  await page.route('**/api/v1/auth/refresh', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user: MOCK_USER,
        access_token: FAKE_JWT,
        token_type: 'bearer',
        expires_in: 3600,
      }),
    })
  )

  // localStorage + valid JWT для useAuthGuard
  const token = FAKE_JWT
  const user = JSON.stringify(MOCK_USER)
  await page.addInitScript(
    ({ token, user }) => {
      localStorage.setItem('access_token', token)
      localStorage.setItem('user', user)
    },
    { token, user }
  )
}

/**
 * Мокирует API ответы для конкретного эндпоинта.
 */
export async function mockApiRoute(
  page: Page,
  urlPattern: string | RegExp,
  responseData: unknown,
  status = 200
) {
  await page.route(urlPattern, (route) =>
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(responseData),
    })
  )
}
