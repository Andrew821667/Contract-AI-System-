import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Routes that require authentication
const protectedRoutes = ['/dashboard', '/contracts', '/clauses']

// Routes that should redirect to dashboard if already logged in
const authRoutes = ['/login', '/register']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Check for auth token in cookies
  const token = request.cookies.get('access_token')?.value

  // Protected routes: redirect to login if no token
  const isProtected = protectedRoutes.some(route => pathname.startsWith(route))
  if (isProtected && !token) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('redirect', pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Auth routes: redirect to dashboard if already logged in
  const isAuthRoute = authRoutes.some(route => pathname.startsWith(route))
  if (isAuthRoute && token) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/contracts/:path*',
    '/clauses/:path*',
    '/login',
    '/register',
  ],
}
