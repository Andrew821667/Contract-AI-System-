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
  refresh_token?: string;  // Now sent as httpOnly cookie, may be absent from JSON
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

// AI Session types
export interface AISession {
  id: string;
  document_id: string;
  user_id: string;
  stage: string;
  status: 'active' | 'completed' | 'archived';
  turns_count: number;
  created_at: string;
  updated_at: string;
}

export interface AIMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface AIContext {
  session_id: string;
  document: {
    id: string;
    file_name: string;
    contract_type: string;
    status: string;
    risk_level?: string;
  };
  stage: string;
  history_summary?: string;
}

export interface AIAction {
  id: string;
  session_id: string;
  action_type: string;
  description: string;
  confidence: number;
  status: 'pending' | 'approved' | 'rejected' | 'edited';
  payload?: Record<string, any>;
  result?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

// Orchestrator types
export interface OrchestratorRun {
  id: string;
  goal: string;
  document_id?: string;
  status: 'planning' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  steps_total: number;
  steps_completed: number;
  current_step?: string;
  result?: Record<string, any>;
  error?: string;
  tokens_used?: number;
  model?: string;
  created_at: string;
  updated_at: string;
}

export interface OrchestratorStep {
  id: string;
  run_id: string;
  step_number: number;
  name: string;
  tool_name?: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  input?: Record<string, any>;
  output?: Record<string, any>;
  error?: string;
  started_at?: string;
  completed_at?: string;
}

// Negotiation types
export interface Negotiation {
  id: string;
  document_id: string;
  user_id: string;
  analysis_id: string | null;
  goal: string;
  status: string;
  objections_count: number;
  by_priority: Record<string, number>;
  created_at: string;
  updated_at: string | null;
}

export interface NegotiationStartResponse {
  negotiation_id: string;
  status: string;
  objections_count: number;
  by_priority: Record<string, number>;
}

export interface Objection {
  objection_id: string;
  issue_description: string;
  legal_basis: string;
  risk_explanation: string;
  alternative_formulation: string;
  alternative_reasoning: string;
  priority: string;
  auto_priority: number;
  confidence: number;
}

export interface NegotiationPosition {
  position_text: string;
  key_arguments: string[];
  concession_candidates: string[];
  red_lines: string[];
}

// Comment types
export interface Comment {
  id: string;
  document_id: string;
  author_id: string;
  content: string;
  anchor_type: string;
  anchor_id: string | null;
  parent_comment_id: string | null;
  status: string;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string | null;
}

// Version Intelligence types
export interface VersionCompareResult {
  comparison_id: string;
  total_changes: number;
  by_type: Record<string, number>;
  by_category: Record<string, number>;
  overall_assessment: string;
  material_changes: MaterialChange[];
  executive_summary: string;
}

export interface MaterialChange {
  change_id: string;
  change_type: string;
  change_category: string;
  section_name: string | null;
  clause_number: string | null;
  old_content: string | null;
  new_content: string | null;
  semantic_description: string | null;
  impact_direction: string | null;
  severity: string | null;
  recommendation: string | null;
  requires_review: boolean;
}

export interface VersionHistoryItem {
  id: number;
  version_number: number;
  source: string;
  file_hash: string | null;
  is_current: boolean;
  description: string | null;
  uploaded_at: string | null;
}

// Organization types
export interface Organization {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  settings: Record<string, any> | null;
  active: boolean;
  created_at: string;
}

export interface OrgMembership {
  id: string;
  user_id: string;
  org_id: string;
  unit_id: string | null;
  company_role: string | null;
  functional_role: string;
  active: boolean;
  joined_at: string;
}

// Policy types
export interface Policy {
  id: string;
  name: string;
  level: string;
  action_type: string;
  effect: string;
  conditions: Record<string, any> | null;
  priority: number;
  active: boolean;
  created_at: string;
}

// Tool & Agent types
export interface ToolDefinition {
  id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  category: string | null;
  input_schema: Record<string, any> | null;
  output_schema: Record<string, any> | null;
  active: boolean;
  created_at: string;
}

export interface AgentDefinition {
  id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  agent_type: string | null;
  capabilities: string[] | null;
  tools: string[] | null;
  active: boolean;
  created_at: string;
}

// Template Governance types
export interface TemplateVersion {
  id: string;
  template_id: string;
  version: number;
  content: Record<string, unknown>;
  variables: Record<string, unknown>[] | null;
  validation_rules: Record<string, unknown> | null;
  status: string;
  created_by: string | null;
  created_at: string;
}

export interface ClausePolicy {
  id: string;
  org_id: string | null;
  clause_type: string;
  status: string;
  alternative_clause_id: string | null;
  risk_explanation: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface ClauseCheckResult {
  clause_type: string;
  allowed: boolean;
  policy: ClausePolicy | null;
}

// Workflow types
export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string | null;
  document_type: string | null;
  jurisdiction: string | null;
  org_id: string | null;
  conditions: Record<string, any> | null;
  steps: Array<{
    name: string;
    assignee_role?: string;
    sla_hours?: number;
    task_type?: string;
  }>;
  active: boolean;
  version: number;
  created_at: string;
}

export interface WorkflowExecution {
  id: string;
  definition_id: string | null;
  document_id: string;
  current_step: number;
  status: 'active' | 'completed' | 'cancelled' | 'failed';
  started_at: string;
  completed_at: string | null;
}

export interface WorkflowTask {
  id: string;
  execution_id: string;
  step_name: string;
  step_order: number;
  assignee_id: string | null;
  task_type: string;
  status: 'pending' | 'in_progress' | 'completed' | 'escalated' | 'skipped';
  decision: string | null;
  comment: string | null;
  sla_deadline: string | null;
  sla_breached: boolean;
  created_at: string;
  completed_at: string | null;
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

// LLM Settings types
export interface LLMModel {
  id: string;
  name: string;
  provider: string;
  cost_input: number;
  cost_output: number;
  description: string;
}

export interface LLMStageSetting {
  stage_id: string;
  stage_name: string;
  stage_description: string;
  model: string;
  temperature: number;
  max_tokens: number;
  enabled: boolean;
  is_default: boolean;
}

export interface LLMSettingsResponse {
  stages: LLMStageSetting[];
  available_models: LLMModel[];
  router_mode: string;
}

export interface LLMStageSettingUpdate {
  model: string;
  temperature: number;
  max_tokens: number;
  enabled: boolean;
}

// API Client
class APIClient {
  private client: AxiosInstance;
  private refreshing = false;

  constructor() {
    // Use relative URL so requests go to the same origin (works with ngrok, localhost, etc.)
    const baseURL = process.env.NEXT_PUBLIC_API_URL || '';

    this.client = axios.create({
      baseURL,
      timeout: 30000,
      withCredentials: true,  // Send httpOnly cookies (refresh_token) with every request
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',
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

  /**
   * Get access token from Zustand store (in-memory only).
   * Security: never reads from localStorage to prevent XSS token theft.
   */
  private getAccessToken(): string | null {
    if (typeof window === 'undefined') return null;
    try {
      const { useAuthStore } = require('../stores/authStore');
      return useAuthStore.getState().accessToken || null;
    } catch {
      return null;
    }
  }

  /**
   * Store access token in Zustand store (memory) and set has_token flag cookie.
   * Refresh token is now an httpOnly cookie set by the backend — we never touch it.
   * Security: access token is ONLY in memory (Zustand), never in localStorage.
   */
  private setAccessToken(accessToken: string) {
    if (typeof window === 'undefined') return;
    // Store in localStorage (used by AppLayout, dashboard, hooks for auth checks)
    localStorage.setItem('access_token', accessToken);
    // Update Zustand store
    try {
      const { useAuthStore } = require('../stores/authStore');
      useAuthStore.getState().setAccessToken(accessToken);
    } catch {
      // Store not available
    }
    // Set flag cookie for Next.js middleware (no actual token value)
    const secure = window.location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `has_token=1; path=/; max-age=3600; SameSite=Lax${secure}`;
  }

  private clearTokens() {
    if (typeof window === 'undefined') return;
    localStorage.removeItem('access_token');  // Clean up legacy if still present
    localStorage.removeItem('refresh_token');  // Clean up legacy
    localStorage.removeItem('user');
    document.cookie = 'has_token=; path=/; max-age=0';
    // Clear Zustand store
    try {
      const { useAuthStore } = require('../stores/authStore');
      useAuthStore.getState().clearAuth();
    } catch {
      // Store not available
    }
  }

  // ==================== Authentication ====================

  async register(data: RegisterRequest): Promise<any> {
    const response = await this.client.post('/api/v1/auth/register', data);
    // Backend returns {message: "..."} without tokens — user must verify email first
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

    // access_token in memory (Zustand + legacy localStorage)
    // refresh_token comes as httpOnly cookie — we don't handle it
    this.setAccessToken(response.data.access_token);

    // Update Zustand store with full auth data
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(response.data.user));
      try {
        const { useAuthStore } = require('../stores/authStore');
        useAuthStore.getState().setAuth(response.data.user, response.data.access_token);
      } catch {
        // Store not available
      }
    }
    return response.data;
  }

  async activateDemo(data: DemoActivateRequest): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>(
      '/api/v1/auth/demo-activate',
      data
    );

    // access_token in memory, refresh_token as httpOnly cookie
    this.setAccessToken(response.data.access_token);

    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(response.data.user));
      try {
        const { useAuthStore } = require('../stores/authStore');
        useAuthStore.getState().setAuth(response.data.user, response.data.access_token);
      } catch {
        // Store not available
      }
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

    this.refreshing = true;

    try {
      // Refresh token is sent automatically as httpOnly cookie (withCredentials: true)
      // No body needed — backend reads from cookie first
      const response = await this.client.post('/api/v1/auth/refresh', {});

      // Store new access token in memory
      this.setAccessToken(response.data.access_token);

      // Update Zustand store with user data if present
      if (response.data.user) {
        try {
          const { useAuthStore } = require('../stores/authStore');
          useAuthStore.getState().setAuth(response.data.user, response.data.access_token);
        } catch {
          // Store not available
        }
      }

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
      try {
        const { useAuthStore } = require('../stores/authStore');
        useAuthStore.getState().setUser(response.data);
      } catch {
        // Store not available
      }
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
    search?: string;
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
  // ==================== Admin: Contract Deletion ====================

  async deleteContract(contractId: string, reason: string): Promise<{ contract_id: string; status: string; message: string }> {
    const response = await this.client.delete(`/api/v1/contracts/${contractId}`, {
      data: { reason }
    });
    return response.data;
  }

  // ==================== AI Sessions (v2) ====================

  async createAISession(documentId: string | null, stage: string = 'analysis'): Promise<AISession> {
    if (documentId) {
      const response = await this.client.post<AISession>(
        `/api/v2/documents/${documentId}/ai/sessions`,
        { stage }
      );
      return response.data;
    }
    // General session without document
    const response = await this.client.post<AISession>(
      `/api/v2/ai/sessions`,
      { stage: 'general' }
    );
    return response.data;
  }

  async listAISessions(documentId: string): Promise<{ sessions: AISession[]; total: number }> {
    const response = await this.client.get(`/api/v2/documents/${documentId}/ai/sessions`);
    return response.data;
  }

  async sendAIMessage(sessionId: string, content: string): Promise<AIMessage> {
    const response = await this.client.post<AIMessage>(
      `/api/v2/ai/sessions/${sessionId}/messages`,
      { content }
    );
    return response.data;
  }

  async getAIMessages(sessionId: string): Promise<{ messages: AIMessage[] }> {
    const response = await this.client.get(`/api/v2/ai/sessions/${sessionId}/messages`);
    // Backend returns array directly, wrap it
    const data = response.data;
    if (Array.isArray(data)) {
      return { messages: data };
    }
    return data;
  }

  async getAIContext(sessionId: string): Promise<AIContext> {
    const response = await this.client.get<AIContext>(
      `/api/v2/ai/sessions/${sessionId}/context`
    );
    return response.data;
  }

  // ==================== AI Actions (v2) ====================

  async listAIActions(sessionId: string): Promise<{ actions: AIAction[] }> {
    const response = await this.client.get(`/api/v2/ai/sessions/${sessionId}/actions`);
    return response.data;
  }

  async approveAIAction(actionId: string, comment?: string): Promise<AIAction> {
    const response = await this.client.post<AIAction>(
      `/api/v2/ai/actions/${actionId}/approve`,
      { comment }
    );
    return response.data;
  }

  async rejectAIAction(actionId: string, comment?: string): Promise<AIAction> {
    const response = await this.client.post<AIAction>(
      `/api/v2/ai/actions/${actionId}/reject`,
      { comment }
    );
    return response.data;
  }

  async editAndApproveAction(actionId: string, payload: Record<string, any>): Promise<AIAction> {
    const response = await this.client.post<AIAction>(
      `/api/v2/ai/actions/${actionId}/edit-and-approve`,
      payload
    );
    return response.data;
  }

  // ==================== Orchestrator (v2) ====================

  async createRun(goal: string, documentId?: string): Promise<OrchestratorRun> {
    const response = await this.client.post<OrchestratorRun>(
      '/api/v2/orchestrator/runs',
      { goal, document_id: documentId }
    );
    return response.data;
  }

  async getRun(runId: string): Promise<OrchestratorRun> {
    const response = await this.client.get<OrchestratorRun>(
      `/api/v2/orchestrator/runs/${runId}`
    );
    return response.data;
  }

  async continueRun(runId: string): Promise<OrchestratorRun> {
    const response = await this.client.post<OrchestratorRun>(
      `/api/v2/orchestrator/runs/${runId}/continue`
    );
    return response.data;
  }

  async cancelRun(runId: string): Promise<OrchestratorRun> {
    const response = await this.client.post<OrchestratorRun>(
      `/api/v2/orchestrator/runs/${runId}/cancel`
    );
    return response.data;
  }

  async getRunSteps(runId: string): Promise<{ steps: OrchestratorStep[] }> {
    const response = await this.client.get(`/api/v2/orchestrator/runs/${runId}/steps`);
    return response.data;
  }

  // ==================== Negotiations (v2) ====================

  async startNegotiation(data: {
    document_id: string;
    goal: string;
    analysis_id?: string;
    auto_prioritize?: boolean;
  }): Promise<NegotiationStartResponse> {
    const response = await this.client.post<NegotiationStartResponse>(
      '/api/v2/negotiations/start',
      data
    );
    return response.data;
  }

  async getNegotiation(negotiationId: string): Promise<Negotiation> {
    const response = await this.client.get<Negotiation>(
      `/api/v2/negotiations/${negotiationId}`
    );
    return response.data;
  }

  async generateObjections(data: {
    negotiation_id: string;
    risk_ids?: string[];
    custom_instructions?: string;
  }): Promise<Objection[]> {
    const response = await this.client.post<Objection[]>(
      '/api/v2/negotiations/objections/generate',
      data
    );
    return response.data;
  }

  async selectObjections(data: {
    negotiation_id: string;
    selected_objection_ids: string[];
    priority_order?: string[];
  }): Promise<{ status: string; selected_count: number }> {
    const response = await this.client.post(
      '/api/v2/negotiations/objections/select',
      data
    );
    return response.data;
  }

  async preparePosition(data: {
    negotiation_id: string;
    strategy?: string;
    focus_areas?: string[];
  }): Promise<NegotiationPosition> {
    const response = await this.client.post<NegotiationPosition>(
      '/api/v2/negotiations/position',
      data
    );
    return response.data;
  }

  // ==================== Comments (v2) ====================

  async createComment(documentId: string, data: {
    content: string;
    anchor_type?: string;
    anchor_id?: string;
    parent_comment_id?: string;
  }): Promise<Comment> {
    const response = await this.client.post<Comment>(
      `/api/v2/documents/${documentId}/comments`,
      data
    );
    return response.data;
  }

  async listComments(documentId: string, params?: {
    anchor_type?: string;
    include_resolved?: boolean;
  }): Promise<Comment[]> {
    const response = await this.client.get<Comment[]>(
      `/api/v2/documents/${documentId}/comments`,
      { params }
    );
    return response.data;
  }

  async replyToComment(commentId: string, content: string): Promise<Comment> {
    const response = await this.client.post<Comment>(
      `/api/v2/comments/${commentId}/reply`,
      { content }
    );
    return response.data;
  }

  async resolveComment(commentId: string): Promise<Comment> {
    const response = await this.client.post<Comment>(
      `/api/v2/comments/${commentId}/resolve`
    );
    return response.data;
  }

  // ==================== Version Intelligence (v2) ====================

  async compareVersionsV2(data: {
    document_id: string;
    from_version_id: string;
    to_version_id: string;
    deep_analysis?: boolean;
  }): Promise<VersionCompareResult> {
    const response = await this.client.post<VersionCompareResult>(
      '/api/v2/versions/compare',
      data
    );
    return response.data;
  }

  async getMaterialChanges(comparisonId: string): Promise<MaterialChange[]> {
    const response = await this.client.get<MaterialChange[]>(
      `/api/v2/versions/compare/${comparisonId}/material-changes`
    );
    return response.data;
  }

  async getChangeRecommendations(comparisonId: string): Promise<Record<string, any>> {
    const response = await this.client.get(
      `/api/v2/versions/compare/${comparisonId}/recommendations`
    );
    return response.data;
  }

  async getVersionHistory(documentId: string): Promise<VersionHistoryItem[]> {
    const response = await this.client.get<VersionHistoryItem[]>(
      `/api/v2/versions/${documentId}/history`
    );
    return response.data;
  }

  // ==================== Workflow (v2) ====================

  async listWorkflowDefinitions(activeOnly: boolean = true): Promise<WorkflowDefinition[]> {
    const response = await this.client.get<WorkflowDefinition[]>(
      '/api/v2/workflow/definitions',
      { params: { active_only: activeOnly } }
    );
    return response.data;
  }

  async createWorkflowDefinition(data: {
    name: string;
    description?: string;
    document_type?: string;
    jurisdiction?: string;
    org_id?: string;
    conditions?: Record<string, any>;
    steps: Array<{ name: string; assignee_role?: string; sla_hours?: number; task_type?: string }>;
  }): Promise<WorkflowDefinition> {
    const response = await this.client.post<WorkflowDefinition>(
      '/api/v2/workflow/definitions',
      data
    );
    return response.data;
  }

  async startWorkflow(definitionId: string, documentId: string): Promise<WorkflowExecution> {
    const response = await this.client.post<WorkflowExecution>(
      '/api/v2/workflow/executions',
      { definition_id: definitionId, document_id: documentId }
    );
    return response.data;
  }

  async getDocumentWorkflows(documentId: string): Promise<WorkflowExecution[]> {
    const response = await this.client.get<WorkflowExecution[]>(
      `/api/v2/workflow/executions/${documentId}`
    );
    return response.data;
  }

  async getExecutionTasks(executionId: string): Promise<WorkflowTask[]> {
    const response = await this.client.get<WorkflowTask[]>(
      `/api/v2/workflow/executions/${executionId}/tasks`
    );
    return response.data;
  }

  async getMyWorkflowTasks(status: string = 'pending'): Promise<WorkflowTask[]> {
    const response = await this.client.get<WorkflowTask[]>(
      '/api/v2/workflow/tasks',
      { params: { status_filter: status } }
    );
    return response.data;
  }

  async completeWorkflowTask(taskId: string, decision: string, comment?: string): Promise<WorkflowTask> {
    const response = await this.client.post<WorkflowTask>(
      `/api/v2/workflow/tasks/${taskId}/complete`,
      { decision, comment }
    );
    return response.data;
  }

  async escalateWorkflowTask(taskId: string, reason?: string): Promise<WorkflowTask> {
    const response = await this.client.post<WorkflowTask>(
      `/api/v2/workflow/tasks/${taskId}/escalate`,
      { reason }
    );
    return response.data;
  }

  // ==================== Organizations (v2) ====================

  async listMyOrganizations(): Promise<Organization[]> {
    const response = await this.client.get<Organization[]>('/api/v2/organizations');
    return response.data;
  }

  async getOrganization(orgId: string): Promise<Organization> {
    const response = await this.client.get<Organization>(`/api/v2/organizations/${orgId}`);
    return response.data;
  }

  async createOrganization(data: {
    name: string; slug: string; description?: string; settings?: Record<string, any>;
  }): Promise<Organization> {
    const response = await this.client.post<Organization>('/api/v2/organizations', data);
    return response.data;
  }

  async listOrgMembers(orgId: string): Promise<OrgMembership[]> {
    const response = await this.client.get<OrgMembership[]>(`/api/v2/organizations/${orgId}/members`);
    return response.data;
  }

  async addOrgMember(orgId: string, data: {
    user_id: string; functional_role?: string; company_role?: string;
  }): Promise<OrgMembership> {
    const response = await this.client.post<OrgMembership>(
      `/api/v2/organizations/${orgId}/members`,
      { ...data, org_id: orgId }
    );
    return response.data;
  }

  // ==================== Policies (v2) ====================

  async listPolicies(level?: string): Promise<Policy[]> {
    const response = await this.client.get<Policy[]>('/api/v2/policies', { params: { level } });
    return response.data;
  }

  // ==================== Tools & Agents (v2) ====================

  async listTools(): Promise<ToolDefinition[]> {
    const response = await this.client.get<ToolDefinition[]>('/api/v2/tools');
    return response.data;
  }

  async listAgents(): Promise<AgentDefinition[]> {
    const response = await this.client.get<AgentDefinition[]>('/api/v2/agents');
    return response.data;
  }

  // ==================== Template Governance (v2) ====================

  async listTemplateVersions(templateId: string): Promise<TemplateVersion[]> {
    const response = await this.client.get<TemplateVersion[]>(`/api/v2/templates/${templateId}/versions`);
    return response.data;
  }

  async createTemplateVersion(templateId: string, data: { content: Record<string, unknown>; variables?: Record<string, unknown>[] | null; validation_rules?: Record<string, unknown> | null }): Promise<TemplateVersion> {
    const response = await this.client.post<TemplateVersion>(`/api/v2/templates/${templateId}/versions`, { ...data, template_id: templateId });
    return response.data;
  }

  async activateTemplateVersion(versionId: string): Promise<TemplateVersion> {
    const response = await this.client.post<TemplateVersion>(`/api/v2/templates/versions/${versionId}/activate`);
    return response.data;
  }

  async getActiveTemplateVersion(templateId: string): Promise<TemplateVersion> {
    const response = await this.client.get<TemplateVersion>(`/api/v2/templates/${templateId}/versions/active`);
    return response.data;
  }

  async listClausePolicies(orgId?: string, statusFilter?: string): Promise<ClausePolicy[]> {
    const response = await this.client.get<ClausePolicy[]>('/api/v2/clause-policies', { params: { org_id: orgId, status_filter: statusFilter } });
    return response.data;
  }

  async createClausePolicy(data: { org_id?: string | null; clause_type: string; status: string; alternative_clause_id?: string | null; risk_explanation?: string | null }): Promise<ClausePolicy> {
    const response = await this.client.post<ClausePolicy>('/api/v2/clause-policies', data);
    return response.data;
  }

  async checkClauseAllowed(clauseType: string, orgId?: string): Promise<ClauseCheckResult> {
    const response = await this.client.get<ClauseCheckResult>('/api/v2/clause-policies/check', { params: { clause_type: clauseType, org_id: orgId } });
    return response.data;
  }

  async listProhibitedClauses(orgId?: string): Promise<ClausePolicy[]> {
    const response = await this.client.get<ClausePolicy[]>('/api/v2/clause-policies/prohibited', { params: { org_id: orgId } });
    return response.data;
  }

  // ==================== Admin LLM Settings ====================

  async getLLMSettings(): Promise<LLMSettingsResponse> {
    const response = await this.client.get<LLMSettingsResponse>('/api/v2/admin/llm/settings');
    return response.data;
  }

  async updateLLMStageSetting(stageId: string, data: LLMStageSettingUpdate): Promise<void> {
    await this.client.put(`/api/v2/admin/llm/settings/${stageId}`, data);
  }

  async updateAllLLMSettings(data: Record<string, LLMStageSettingUpdate>): Promise<void> {
    await this.client.put('/api/v2/admin/llm/settings', data);
  }

  async updateLLMRouterMode(mode: string): Promise<void> {
    await this.client.put('/api/v2/admin/llm/router-mode', { mode });
  }

  async resetLLMSettings(): Promise<void> {
    await this.client.post('/api/v2/admin/llm/reset');
  }
}

// Export singleton instance
const api = new APIClient();
export default api;
