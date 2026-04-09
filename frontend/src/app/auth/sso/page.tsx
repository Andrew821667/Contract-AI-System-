'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';

/**
 * SSO Callback Page
 *
 * Reads JWT token from URL fragment (#token=...) and stores it.
 * Fragment is never sent to the server, avoiding token leaks via
 * Referer headers, server logs, or browser history.
 */
export default function SSOCallbackPage() {
  const router = useRouter();
  const { setAccessToken, setAuth } = useAuthStore();

  useEffect(() => {
    const hash = window.location.hash;
    const params = new URLSearchParams(hash.replace('#', ''));
    const token = params.get('token');

    if (!token) {
      router.replace('/login');
      return;
    }

    // Store token and fetch user profile
    (async () => {
      try {
        const { default: api } = await import('@/services/api');
        api.setAccessToken(token);
        const user = await api.getCurrentUser();
        setAuth(user, token);
        // Clear fragment from URL
        window.history.replaceState(null, '', '/auth/sso');
        router.replace('/dashboard');
      } catch {
        router.replace('/login');
      }
    })();
  }, [router, setAccessToken, setAuth]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4" />
        <p className="text-gray-600">Выполняется вход...</p>
      </div>
    </div>
  );
}
