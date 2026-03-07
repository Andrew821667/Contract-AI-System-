/**
 * API Service for Contract-AI-System
 *
 * Handles all HTTP requests to the FastAPI backend
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import { toast } from 'react-hot-toast';

// Types
export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  subscription_tier: string;
  is_demo: boolean;
  email_verified: boolean;
  created_at: string;
  last_login?: string;
  contracts_today: number;
  llm_requests_today: number;
  max_contracts_per_day?: number;
  max_llm_requests_per_day?: number;
  demo_expires?: string;
}

export interface LoginRequest {
  username: string;  // FastAPI OAuth2 uses 'username' field
  password: string;
}

export interface RegisterRequest {
  email: string;
  name: string;
  password: string;
}

export interface DemoActivateRequest {
  token: string;
  email: string;
  name: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface DemoLinkResponse {
  token: string;
  url: string;
  expires_at: string;
  max_contracts: number;
  max_llm_requests: number;
}

// Digital Contract types
export interface DigitalContract {
  id: string;
  contract_id: string;
  version: number;
  content_hash: string;
  signature: string;
  parent_id: string | null;
  status: 'active' | 'superseded' | 'revoked';
  metadata?: Record<string, any> | null;
  created_by: string | null;
  created_at: string;
}

export interface VerificationResult {
  valid: boolean;
  digital_id: string;
  version: number;
  content_hash: string;
  content_hash_match: boolean | null;
  signature_valid: boolean;
  chain_valid: boolean;
  status: string;
  created_at: string;
}

export interface HashChainResponse {
  chain: DigitalContract[];
  length: number;
}

export interface DAGResponse {
  nodes: Array<{
    id: string;
    version: number;
    content_hash: string;
    status: string;
    created_at: string;
  }>;
  edges: Array<{
    from: string;
    to: string;
    type: 'chain' | 'merge';
  }>;
}

// Dashboard / Analytics types
export interface DashboardData {
  period: { start: string; end: string; days: number };
  headline_metrics: Record<string, {
    name: string;
    value: number;
    unit: string;
    metric_type: string;
    timestamp: string;
    trend: string | null;
    trend_percentage: number | null;
    benchmark: number | null;
  }>;
  risk_trends: Array<{
    date: string;
    critical_count: number;
    high_count: number;
    medium_count: number;
    low_count: number;
    total_contracts: number;
    average_risk_score: number;
  }>;
  cost_analysis: {
    period_start: string;
    period_end: string;
    total_cost_usd: number;
    llm_calls: number;
    tokens_used: number;
    cost_per_contract: number;
    ml_prediction_savings: number;
    estimated_monthly_cost: number;
  };
  productivity: {
    contracts_analyzed: number;
    total_time_saved_hours: number;
    average_analysis_time_seconds: number;
    automated_tasks: number;
    manual_tasks_prevented: number;
    roi_multiplier: number;
  };
  top_risks: Array<{
    risk_type: string;
    count: number;
    severity: string;
    avg_impact_score: number;
    trend: string;
  }>;
  risk_distribution: Array<{
    category: string;
    count: number;
    percentage: number;
    average_severity: number;
    trend: string;
  }>;
  recommendations: Array<{
    type: string;
    title: string;
    message: string;
    priority: string;
  }>;
  generated_at: string;
}

// Clause Library types
export interface ExtractedClause {
  id: string;
  contract_id: string;
  clause_number: number;
  clause_type: string;
  title: string;
  text: string;
  xpath_location: string | null;
  risk_level: string | null;
  severity_score: number | null;
  tags: string[];
  created_at: string;
  analysis?: Record<string, any> | null;
}

export interface ClauseLibraryResponse {
  clauses: ExtractedClause[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ClauseStats {
  total_clauses: number;
  contracts_with_clauses: number;
  average_severity: number;
  by_type: Record<string, number>;
  by_risk_level: Record<string, number>;
}

// ML Risk Prediction types
export interface RiskPredictionRequest {
  contract_type: string;
  amount: number;
  duration_days: number;
  counterparty_risk_score?: number;
  clause_count?: number;
  doc_length?: number;
  payment_terms_days?: number;
  penalty_rate?: number;
  has_force_majeure?: boolean;
  has_liability_limit?: boolean;
  has_confidentiality?: boolean;
  has_dispute_resolution?: boolean;
  has_termination_clause?: boolean;
  num_parties?: number;
  counterparty_age_years?: number;
  historical_disputes?: number;
  historical_contracts?: number;
}

export interface RiskPredictionResponse {
  risk_level: string;
  confidence: number;
  risk_score: number;
  should_use_llm: boolean;
  prediction_time_ms: number;
  model_version: string;
  features_used: Record<string, number>;
  recommendation: string;
}

export interface RiskFeedbackRequest {
  contract_id?: number;
  contract_features: Record<string, any>;
  predicted_risk_level: string;
  predicted_confidence?: number;
  actual_risk_level: string;
  feedback_reason?: string;
  model_version?: string;
}

export interface ModelStatus {
  model_type: string;
  model_version: string;
  is_trained: boolean;
  feedback_count: number;
  unused_feedback_count: number;
  last_training: string | null;
  accuracy: number | null;
}

// Contract Version Comparison types
export interface ContractVersionInfo {
  id: number;
  contract_id: string;
  version_number: number;
  file_hash: string | null;
  source: string;
  description: string | null;
  is_current: boolean;
  uploaded_at: string | null;
}

export interface CompareChange {
  change_type: string;
  change_category: string;
  section_name: string | null;
  clause_number: string | null;
  old_content: string | null;
  new_content: string | null;
  xpath_location: string | null;
}

export interface CompareResult {
  total_changes: number;
  by_type: Record<string, number>;
  by_category: Record<string, number>;
  overall_assessment: string | null;
  changes: CompareChange[];
  executive_summary: string | null;
}

// API Client
class APIClient {
  private client: AxiosInstance;
  private refreshing = false;

  constructor() {
    const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor: Add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = this.getAccessToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor: Handle errors and token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as any;

        // Handle 401 errors (token expired)
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          // Try to refresh token
          const refreshed = await this.refreshToken();
          if (refreshed) {
            return this.client(originalRequest);
          }

          // Refresh failed, redirect to login
          this.logout();
          if (typeof window !== 'undefined') {
            window.location.href = '/login';
          }
        }

        // Handle rate limiting
        if (error.response?.status === 429) {
          toast.error('Слишком много запросов. Пожалуйста, подождите.');
        }

        return Promise.reject(error);
      }
    );
  }

  // ==================== Token Management ====================

  private getAccessToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('access_token');
  }

  private getRefreshToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('refresh_token');
  }

  private setTokens(accessToken: string, refreshToken: string) {
    if (typeof window === 'undefined') return;
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    // Set cookie for Next.js middleware (server-side auth check)
    document.cookie = `access_token=${accessToken}; path=/; max-age=3600; SameSite=Lax`;
  }

  private clearTokens() {
    if (typeof window === 'undefined') return;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    document.cookie = 'access_token=; path=/; max-age=0';
  }

  // ==================== Authentication ====================

  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>('/api/v1/auth/register', data);
    this.setTokens(response.data.access_token, response.data.refresh_token);
    return response.data;
  }

  async login(data: LoginRequest): Promise<AuthResponse> {
    // FastAPI OAuth2PasswordRequestForm expects form data
    const params = new URLSearchParams();
    params.append('username', data.username);
    params.append('password', data.password);

    const response = await this.client.post<AuthResponse>(
      '/api/v1/auth/login',
      params.toString(),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    this.setTokens(response.data.access_token, response.data.refresh_token);
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(response.data.user));
    }
    return response.data;
  }

  async activateDemo(data: DemoActivateRequest): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>(
      '/api/v1/auth/demo-activate',
      data
    );

    this.setTokens(response.data.access_token, response.data.refresh_token);
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(response.data.user));
    }
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/api/v1/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      this.clearTokens();
    }
  }

  async refreshToken(): Promise<boolean> {
    if (this.refreshing) return false;

    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return false;

    this.refreshing = true;

    try {
      const response = await this.client.post('/api/v1/auth/refresh', {
        refresh_token: refreshToken,
      });

      this.setTokens(response.data.access_token, response.data.refresh_token);
      this.refreshing = false;
      return true;
    } catch (error) {
      this.refreshing = false;
      return false;
    }
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
    const response = await this.client.post('/api/v1/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<User>('/api/v1/auth/me');
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(response.data));
    }
    return response.data;
  }

  // ==================== Admin Operations ====================

  async generateDemoLink(data: {
    max_contracts: number;
    max_llm_requests: number;
    expires_in_hours: number;
    campaign?: string;
  }): Promise<DemoLinkResponse> {
    const response = await this.client.post<DemoLinkResponse>(
      '/api/v1/auth/admin/demo-link',
      data
    );
    return response.data;
  }

  async createUser(data: {
    email: string;
    name: string;
    role: string;
    subscription_tier: string;
  }): Promise<any> {
    const response = await this.client.post('/api/v1/auth/admin/users', data);
    return response.data;
  }

  async updateUserRole(
    userId: string,
    data: { role: string; subscription_tier?: string }
  ): Promise<any> {
    const response = await this.client.patch(
      `/api/v1/auth/admin/users/${userId}/role`,
      data
    );
    return response.data;
  }

  async listUsers(params?: {
    page?: number;
    limit?: number;
    role?: string;
    search?: string;
    is_demo?: boolean;
  }): Promise<any> {
    const response = await this.client.get('/api/v1/auth/admin/users', { params });
    return response.data;
  }

  async getAnalytics(): Promise<any> {
    const response = await this.client.get('/api/v1/auth/admin/analytics');
    return response.data;
  }

  // ==================== Contract Operations ====================

  async uploadContract(file: File, metadata?: any): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }

    const response = await this.client.post('/api/v1/contracts/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 120000, // 2 minutes for large files
    });

    return response.data;
  }

  async analyzeContract(contractId: string): Promise<any> {
    const response = await this.client.post('/api/v1/contracts/analyze', {
      contract_id: contractId,
    });
    return response.data;
  }

  async getContract(contractId: string): Promise<any> {
    const response = await this.client.get(`/api/v1/contracts/${contractId}`);
    return response.data;
  }

  async listContracts(params?: {
    page?: number;
    limit?: number;
    status?: string;
  }): Promise<any> {
    const response = await this.client.get('/api/v1/contracts', { params });
    return response.data;
  }

  async generateContract(data: {
    contract_type: string;
    template_id?: string;
    params: Record<string, any>;
  }): Promise<any> {
    const response = await this.client.post('/api/v1/contracts/generate', data);
    return response.data;
  }

  async exportContract(contractId: string, format: string): Promise<Blob> {
    const response = await this.client.get(
      `/api/v1/contracts/${contractId}/export`,
      {
        params: { format },
        responseType: 'blob',
      }
    );
    return response.data;
  }

  // ==================== Digital Contract Operations ====================

  async digitalizeContract(contractId: string): Promise<DigitalContract> {
    const response = await this.client.post<DigitalContract>(
      `/api/v1/contracts/${contractId}/digitalize`
    );
    return response.data;
  }

  async getDigitalVersions(contractId: string): Promise<{ versions: DigitalContract[]; total: number }> {
    const response = await this.client.get(`/api/v1/contracts/${contractId}/digital`);
    return response.data;
  }

  async verifyDigital(contractId: string, digitalId: string): Promise<VerificationResult> {
    const response = await this.client.get<VerificationResult>(
      `/api/v1/contracts/${contractId}/digital/${digitalId}/verify`
    );
    return response.data;
  }

  async getHashChain(contractId: string): Promise<HashChainResponse> {
    const response = await this.client.get<HashChainResponse>(
      `/api/v1/contracts/${contractId}/digital/chain`
    );
    return response.data;
  }

  async getDAG(contractId: string): Promise<DAGResponse> {
    const response = await this.client.get<DAGResponse>(
      `/api/v1/contracts/${contractId}/digital/dag`
    );
    return response.data;
  }

  // ==================== Analytics Dashboard ====================

  async getDashboard(period: number = 30): Promise<DashboardData> {
    const response = await this.client.get<DashboardData>(
      '/api/v1/analytics/dashboard',
      { params: { period_days: period } }
    );
    return response.data;
  }

  // ==================== Clause Library ====================

  async getClauseLibrary(params?: {
    page?: number;
    page_size?: number;
    clause_type?: string;
    risk_level?: string;
    contract_id?: string;
  }): Promise<ClauseLibraryResponse> {
    const response = await this.client.get<ClauseLibraryResponse>(
      '/api/v1/clauses',
      { params }
    );
    return response.data;
  }

  async getClauseStats(): Promise<ClauseStats> {
    const response = await this.client.get<ClauseStats>('/api/v1/clauses/stats');
    return response.data;
  }

  async getClause(clauseId: string): Promise<ExtractedClause> {
    const response = await this.client.get<ExtractedClause>(
      `/api/v1/clauses/${clauseId}`
    );
    return response.data;
  }

  async searchClauses(query: string, clauseType?: string): Promise<ClauseLibraryResponse> {
    const response = await this.client.get<ClauseLibraryResponse>(
      '/api/v1/clauses/search',
      { params: { q: query, clause_type: clauseType } }
    );
    return response.data;
  }

  // ==================== ML Risk Prediction ====================

  async predictRisk(data: RiskPredictionRequest): Promise<RiskPredictionResponse> {
    const response = await this.client.post<RiskPredictionResponse>(
      '/api/v1/ml/predict-risk',
      data
    );
    return response.data;
  }

  async submitRiskFeedback(data: RiskFeedbackRequest): Promise<{ success: boolean; feedback_id: number; message: string }> {
    const response = await this.client.post(
      '/api/v1/ml/feedback',
      data
    );
    return response.data;
  }

  async getModelStatus(): Promise<ModelStatus> {
    const response = await this.client.get<ModelStatus>(
      '/api/v1/ml/model/status'
    );
    return response.data;
  }

  // ==================== Contract Version Comparison ====================

  async uploadVersion(
    contractId: string,
    file: File,
    source?: string,
    description?: string
  ): Promise<ContractVersionInfo> {
    const formData = new FormData();
    formData.append('file', file);
    if (source) formData.append('source', source);
    if (description) formData.append('description', description);

    const response = await this.client.post<ContractVersionInfo>(
      `/api/v1/contracts/${contractId}/versions`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      }
    );
    return response.data;
  }

  async getVersions(contractId: string): Promise<{ versions: ContractVersionInfo[]; total: number }> {
    const response = await this.client.get(`/api/v1/contracts/${contractId}/versions`);
    return response.data;
  }

  async compareVersions(
    contractId: string,
    fromVersionId: number,
    toVersionId: number
  ): Promise<CompareResult> {
    const response = await this.client.post<CompareResult>(
      `/api/v1/contracts/${contractId}/compare`,
      { from_version_id: fromVersionId, to_version_id: toVersionId }
    );
    return response.data;
  }
}

// Export singleton instance
const api = new APIClient();
export default api;
