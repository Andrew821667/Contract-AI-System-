import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Routes that require authentication
const protectedRoutes = ['/dashboard', '/contracts', '/clauses', '/conditions', '/ai', '/negotiations', '/workflow', '/admin', '/organization', '/counterparties', '/revisions']

// Routes that should redirect to dashboard if already logged in.
// Keep /register always reachable: browsers can retain a stale has_token cookie
// after failed/partial auth flows, and the registration page must remain a
// single reliable entry point from all public CTAs.
const authRoutes = ['/login']
const noindexRoutes = [...protectedRoutes, '/login', '/register', '/auth']

function withNoindex(response: NextResponse) {
  response.headers.set('X-Robots-Tag', 'noindex, nofollow, noarchive')
  return response
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  const shouldNoindex = noindexRoutes.some(route => pathname.startsWith(route))

  // Check for auth flag cookie (does NOT contain the actual JWT - just a presence flag)
  const token = request.cookies.get('has_token')?.value

  // Protected routes: redirect to login if no token
  const isProtected = protectedRoutes.some(route => pathname.startsWith(route))
  if (isProtected && !token) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('redirect', pathname)
    const response = NextResponse.redirect(loginUrl)
    return shouldNoindex ? withNoindex(response) : response
  }

  // Auth routes: redirect to dashboard if already logged in
  const isAuthRoute = authRoutes.some(route => pathname.startsWith(route))
  if (isAuthRoute && token) {
    const response = NextResponse.redirect(new URL('/dashboard', request.url))
    return shouldNoindex ? withNoindex(response) : response
  }

  const response = NextResponse.next()
  return shouldNoindex ? withNoindex(response) : response
}

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/contracts/:path*',
    '/clauses/:path*',
    '/conditions/:path*',
    '/ai/:path*',
    '/negotiations/:path*',
    '/workflow/:path*',
    '/admin/:path*',
    '/organization/:path*',
    '/counterparties/:path*',
    '/revisions/:path*',
    '/auth/:path*',
    '/login',
    '/register',
  ],
}
