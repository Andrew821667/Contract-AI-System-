'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

interface DemoToken {
  id: string;
  token: string;
  url: string;
  created_at: string;
  expires_at: string;
  used: boolean;
  used_at: string | null;
  max_contracts: number;
  max_llm_requests: number;
  campaign: string | null;
  source: string;
}

export default function AdminDemoTokens() {
  const router = useRouter();
  const [tokens, setTokens] = useState<DemoToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showGenerator, setShowGenerator] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    max_contracts: 3,
    max_llm_requests: 10,
    expires_in_hours: 24,
    campaign: ''
  });

  // Check admin access on mount
  useEffect(() => {
    const checkAdminAccess = async () => {
      const token = localStorage.getItem('access_token');
      const userStr = localStorage.getItem('user');
      
      if (!token || !userStr) {
        // Not logged in - redirect to login
        router.push('/login?redirect=/admin/demo-tokens');
        return;
      }

      try {
        const user = JSON.parse(userStr);
        
        // Check if user is admin
        if (user.role !== 'admin') {
          alert('Access Denied: Admin role required');
          router.push('/dashboard');
          return;
        }

        setIsAdmin(true);
        fetchTokens();
      } catch (err) {
        router.push('/login');
      }
    };

    checkAdminAccess();
  }, [router]);

  const fetchTokens = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      const res = await fetch('http://localhost:8000/api/v1/auth/admin/demo-tokens', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (res.status === 403) {
        alert('Access Denied: Admin role required');
        router.push('/dashboard');
        return;
      }

      if (res.ok) {
        const data = await res.json();
        setTokens(data);
      } else if (res.status === 401) {
        // Token expired
        localStorage.clear();
        router.push('/login?redirect=/admin/demo-tokens');
      } else {
        setError('Failed to load tokens');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  const generateToken = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      const res = await fetch('http://localhost:8000/api/v1/auth/admin/demo-link', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          ...formData,
          source: 'nextjs_admin'
        })
      });

      if (res.status === 403) {
        alert('Access Denied: Admin role required');
        router.push('/dashboard');
        return;
      }

      if (res.ok) {
        const data = await res.json();
        alert(`Token generated!\n\nURL: ${data.url}\n\nCopied to clipboard!`);
        navigator.clipboard.writeText(data.url);
        setShowGenerator(false);
        fetchTokens(); // Refresh list
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail}`);
      }
    } catch (err) {
      alert('Connection error');
    }
  };

  const getStatus = (token: DemoToken) => {
    if (token.used) return { text: '✅ Used', color: 'bg-green-100 text-green-800' };
    if (new Date(token.expires_at) < new Date()) return { text: '⏰ Expired', color: 'bg-gray-100 text-gray-800' };
    return { text: '🟢 Active', color: 'bg-blue-100 text-blue-800' };
  };

  const copyUrl = (url: string) => {
    navigator.clipboard.writeText(url);
    alert('URL copied to clipboard!');
  };

  // Show loading while checking access
  if (!isAdmin || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg">
          {loading ? 'Loading...' : 'Checking access...'}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">🎫 Demo Tokens Management</h1>
            <p className="text-gray-600 mt-1">Generate and manage demo access tokens</p>
          </div>
          <div className="text-sm text-gray-500">
            🔒 Admin Only
          </div>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Generate Button */}
        <button
          onClick={() => setShowGenerator(!showGenerator)}
          className="mb-6 bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-medium transition"
        >
          {showGenerator ? '✖ Cancel' : '➕ Generate New Token'}
        </button>

        {/* Generator Form */}
        {showGenerator && (
          <div className="mb-6 bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Generate Demo Token</h2>
            <form onSubmit={generateToken} className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Contracts
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={formData.max_contracts}
                    onChange={(e) => setFormData({...formData, max_contracts: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max LLM Requests
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={formData.max_llm_requests}
                    onChange={(e) => setFormData({...formData, max_llm_requests: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Valid for (hours)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="168"
                    value={formData.expires_in_hours}
                    onChange={(e) => setFormData({...formData, expires_in_hours: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Campaign (optional)
                </label>
                <input
                  type="text"
                  value={formData.campaign}
                  onChange={(e) => setFormData({...formData, campaign: e.target.value})}
                  placeholder="e.g., website_header_cta"
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <button
                type="submit"
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium transition"
              >
                🎫 Generate Token
              </button>
            </form>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-2xl font-bold text-gray-900">{tokens.length}</div>
            <div className="text-sm text-gray-600">Total</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-2xl font-bold text-blue-600">
              {tokens.filter(t => !t.used && new Date(t.expires_at) >= new Date()).length}
            </div>
            <div className="text-sm text-gray-600">Active</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-2xl font-bold text-green-600">
              {tokens.filter(t => t.used).length}
            </div>
            <div className="text-sm text-gray-600">Used</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-2xl font-bold text-gray-400">
              {tokens.filter(t => !t.used && new Date(t.expires_at) < new Date()).length}
            </div>
            <div className="text-sm text-gray-600">Expired</div>
          </div>
        </div>

        {/* Tokens Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Token</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Campaign</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Limits</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Expires</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {tokens.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-gray-500">
                    No demo tokens generated yet
                  </td>
                </tr>
              ) : (
                tokens.map((token) => {
                  const status = getStatus(token);
                  return (
                    <tr key={token.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 text-xs font-medium rounded ${status.color}`}>
                          {status.text}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <code className="text-sm bg-gray-100 px-2 py-1 rounded">
                          {token.token.slice(0, 12)}...{token.token.slice(-6)}
                        </code>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {token.campaign || '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {token.max_contracts}C / {token.max_llm_requests}L
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {new Date(token.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {new Date(token.expires_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={() => copyUrl(token.url)}
                          className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                        >
                          📋 Copy URL
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
