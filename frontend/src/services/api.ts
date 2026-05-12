/**
 * API Service for Contract-AI-System
 *
 * Handles all HTTP requests to the FastAPI backend
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import { toast } from 'react-hot-toast';

// Types — re-exported from api.types.ts for backward compatibility
export * from './api.types';
import type {
  User, LoginRequest, RegisterRequest, AuthResponse, AgentDefinitionUpdate,
  Contract, ContractUploadResponse, AnalysisResultResponse,
  AnalysisResultRequest, StreamAnalysisRequest,
  QuotaResponse, DemoActivateRequest, DemoLinkResponse,
  DigitalContract, VerificationResult, HashChainResponse, DAGResponse,
  ContractRecommendationDecisionResponse, GenerationContractTypeOption,
  DashboardData, PersonalStats, GroupStats,
  ClauseLibraryResponse, ClauseStats, ExtractedClause,
  ConditionListResponse, ConditionCategory, CompanyCondition,
  CompanyConditionCreate, CompanyConditionUpdate,
  Counterparty, CounterpartyCreate, CounterpartyUpdate,
  CounterpartyListResponse, CounterpartyTypeOption,
  CounterpartyLookupRequest, CounterpartyLookupResponse,
  CounterpartyContractsResponse,
  ContractParty, ContractPartyCreate, ContractPartyUpdate, ContractPartiesResponse,
  ContractRelation, ContractRelationCreate, ContractRelationUpdate,
  ContractRelatedBundle, RelationTypeOption, PartyRoleOption,
  ContractRelationType,
  ContractUploadOptions, ParentCandidate, FindParentResponse,
  ContractListItem, ContractListResponse, ContractGroup,
  VerificationReport, VerificationsListResponse,
  RiskPredictionRequest, RiskPredictionResponse, RiskFeedbackRequest, ModelStatus,
  ContractVersionInfo, CompareResult, VersionCompareResult, MaterialChange, VersionHistoryItem,
  AISession, AIMessage, AIContext, AIAction,
  OrchestratorRun, OrchestratorStep,
  NegotiationStartResponse, Negotiation, Objection, NegotiationPosition,
  WorkflowDefinition, WorkflowExecution, WorkflowTask,
  Organization, OrgMembership,
  Policy, ToolDefinition, AgentDefinition, TemplateVersion,
  ClausePolicy, ClauseCheckResult,
  LLMSettingsResponse, LLMStageSettingUpdate,
  WebhookConfig, WebhookDelivery, DomainEvent, EventTypeInfo,
  GraphAskRequest, GraphAskResponse, GraphSearchRequest, GraphSearchResponse,
  GraphIngestRequest, GraphIngestResponse, GraphDocumentSummary, GraphDocumentTree,
  GraphNodeDetail, GraphStats, GraphEntitySummary, GraphCandidateEdge,
  ProposeEdgeRequest,
} from './api.types';


export interface RAGCollectionStat {
  name: string;
  label: string;
  chunk_count: number;
  doc_count: number;
}

export interface RAGDocument {
  doc_id: string;
  title: string;
  collection: string;
  doc_type: string | null;
  chunks: number;
  uploaded_by: string | null;
  created_at: string | null;
}

export interface RAGUploadResult {
  ok: boolean;
  doc_id: string;
  title: string;
  collection: string;
  chunks: number;
}

// API Client
class APIClient {
  private client: AxiosInstance;
  // refreshPromise declared near refreshToken() method

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

    // Request interceptor: Add auth token + org context
    this.client.interceptors.request.use(
      (config) => {
        const token = this.getAccessToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        // Inject organization context from orgStore
        try {
          const orgStorage = typeof window !== 'undefined'
            ? JSON.parse(localStorage.getItem('org-storage') || '{}')
            : {};
          const orgId = orgStorage?.state?.selectedOrgId;
          if (orgId) {
            config.headers['X-Organization-Id'] = orgId;
          }
        } catch {}
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
  setAccessToken(accessToken: string) {
    if (typeof window === 'undefined') return;
    // Security: do NOT store token in localStorage (XSS risk).
    // Token lives only in Zustand in-memory store.
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
    if (response.data?.access_token) {
      this.setAccessToken(response.data.access_token);
    }
    if (typeof window !== 'undefined' && response.data?.user && response.data?.access_token) {
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

  async getQuota(): Promise<QuotaResponse> {
    const response = await this.client.get<QuotaResponse>('/api/v1/auth/quota');
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

  private refreshPromise: Promise<boolean> | null = null;

  async refreshToken(): Promise<boolean> {
    // Deduplicate concurrent refresh calls — all callers await the same promise
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = (async () => {
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

        return true;
      } catch (error) {
        return false;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
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

  async uploadContract(
    file: File,
    optionsOrMetadata?: ContractUploadOptions | Record<string, any>,
  ): Promise<ContractUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    if (optionsOrMetadata) {
      const opts = optionsOrMetadata as ContractUploadOptions;
      // Известные form-поля backend'а: добавляем явно по имени.
      const formFields: Array<keyof ContractUploadOptions> = [
        'document_type',
        'counterparty_id',
        'parent_contract_id',
        'relation_type',
        'custom_label',
        'custom_prompt',
        'auto_find_parent',
      ];
      let used = false;
      for (const key of formFields) {
        const value = opts[key];
        if (value !== undefined && value !== null && value !== '') {
          formData.append(key, String(value));
          used = true;
        }
      }
      // Backward-compat: если переданы только legacy-поля — оборачиваем в metadata.
      if (!used) {
        formData.append('metadata', JSON.stringify(optionsOrMetadata));
      }
    }

    const response = await this.client.post<ContractUploadResponse>(
      '/api/v1/contracts/upload',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      },
    );

    return response.data;
  }

  async findContractParent(contractId: string): Promise<FindParentResponse> {
    const response = await this.client.post<FindParentResponse>(
      `/api/v1/contracts/${contractId}/find-parent`,
    );
    return response.data;
  }

  async analyzeContract(contractId: string, options?: { analysis_perspective?: string }): Promise<any> {
    const response = await this.client.post('/api/v1/contracts/analyze', {
      contract_id: contractId,
      analysis_perspective: options?.analysis_perspective,
    });
    return response.data;
  }

  async cancelAnalysis(contractId: string): Promise<any> {
    const response = await this.client.post(`/api/v1/contracts/${contractId}/analyze/cancel`);
    return response.data;
  }

  async getContract(contractId: string): Promise<any> {
    const response = await this.client.get(`/api/v1/contracts/${contractId}`);
    return response.data;
  }

  async setRecommendationDecision(
    contractId: string,
    recommendationId: number,
    decision: 'accepted' | 'rejected'
  ): Promise<ContractRecommendationDecisionResponse> {
    const response = await this.client.post<ContractRecommendationDecisionResponse>(
      `/api/v1/contracts/${contractId}/recommendations/${recommendationId}/decision`,
      { decision }
    );
    return response.data;
  }

  async listContracts(params?: {
    page?: number;
    limit?: number;
    page_size?: number;
    status?: string;
    contract_type?: string;
    search?: string;
    cursor?: string;
    q?: string;
    document_type?: string;
    relation_type?: string;
    parent_contract_id?: string;
    counterparty_id?: string;
    counterparty_inn?: string;
    contract_date_from?: string;
    contract_date_to?: string;
    amount_from?: number;
    amount_to?: number;
    currency?: string;
    group_by?: 'counterparty' | 'parent';
  }): Promise<ContractListResponse> {
    // Backend ожидает page_size, фронт исторически шлёт limit; маппим обе.
    const mapped: Record<string, any> = { ...(params || {}) };
    if (params?.limit !== undefined && params.page_size === undefined) {
      mapped.page_size = params.limit;
      delete mapped.limit;
    }
    const response = await this.client.get<ContractListResponse>('/api/v1/contracts', { params: mapped });
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

  async getGenerationContractTypes(): Promise<GenerationContractTypeOption[]> {
    const response = await this.client.get<GenerationContractTypeOption[]>('/api/v1/contracts/generate/types');
    return response.data;
  }

  async listTemplates(contractType?: string): Promise<Array<{
    id: string;
    name: string;
    contract_type: string;
    version?: string;
    source_file_name?: string;
  }>> {
    const params = contractType ? { contract_type: contractType } : {};
    const response = await this.client.get('/api/v1/contracts/templates', { params });
    return response.data;
  }

  async getTemplateStatus(contractId: string): Promise<{
    has_template: boolean;
    template_id?: string;
    template_name?: string;
    contract_type?: string;
  }> {
    const response = await this.client.get(`/api/v1/contracts/${contractId}/template-status`);
    return response.data;
  }

  async saveAsTemplate(contractId: string, data: {
    name: string;
    contract_type: string;
  }): Promise<{
    template_id: string;
    name: string;
    contract_type: string;
    message: string;
  }> {
    const response = await this.client.post(`/api/v1/contracts/${contractId}/save-as-template`, data);
    return response.data;
  }

  async exportContract(
    contractId: string,
    format: string,
    options?: {
      allowLossyConversion?: boolean;
    }
  ): Promise<Blob> {
    const response = await this.client.get(
      `/api/v1/contracts/${contractId}/export`,
      {
        params: {
          format,
          allow_lossy_conversion: options?.allowLossyConversion || false,
        },
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

  async getPersonalStats(): Promise<PersonalStats> {
    const response = await this.client.get<PersonalStats>('/api/v1/analytics/personal');
    return response.data;
  }

  async getGroupStats(orgId: string): Promise<GroupStats> {
    const response = await this.client.get<GroupStats>('/api/v1/analytics/group', {
      params: { org_id: orgId }
    });
    return response.data;
  }

  // ==================== Organizations ====================

  async getMyOrganizations(): Promise<any[]> {
    const response = await this.client.get('/api/v2/organizations');
    return response.data;
  }

  async getOrgMembers(orgId: string): Promise<any[]> {
    const response = await this.client.get(`/api/v2/organizations/${orgId}/members`);
    return response.data;
  }

  async inviteMember(orgId: string, data: { email: string; functional_role: string; company_role?: string }): Promise<any> {
    const response = await this.client.post(`/api/v2/organizations/${orgId}/invite`, data);
    return response.data;
  }

  async updateMemberRole(orgId: string, userId: string, data: { functional_role: string }): Promise<any> {
    const response = await this.client.patch(`/api/v2/organizations/${orgId}/members/${userId}`, data);
    return response.data;
  }

  async removeMember(orgId: string, userId: string): Promise<void> {
    await this.client.delete(`/api/v2/organizations/${orgId}/members/${userId}`);
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

  // ==================== Company Conditions ====================

  async getConditions(params?: {
    page?: number;
    page_size?: number;
    category?: string;
    is_active?: boolean;
  }): Promise<ConditionListResponse> {
    const response = await this.client.get<ConditionListResponse>(
      '/api/v1/conditions',
      { params }
    );
    return response.data;
  }

  async getConditionCategories(): Promise<ConditionCategory[]> {
    const response = await this.client.get<ConditionCategory[]>('/api/v1/conditions/categories');
    return response.data;
  }

  async createCondition(data: CompanyConditionCreate): Promise<CompanyCondition> {
    const response = await this.client.post<CompanyCondition>('/api/v1/conditions', data);
    return response.data;
  }

  async updateCondition(id: string, data: CompanyConditionUpdate): Promise<CompanyCondition> {
    const response = await this.client.put<CompanyCondition>(`/api/v1/conditions/${id}`, data);
    return response.data;
  }

  async deleteCondition(id: string): Promise<void> {
    await this.client.delete(`/api/v1/conditions/${id}`);
  }

  // ==================== Counterparties ====================

  async listCounterparties(params?: {
    page?: number;
    page_size?: number;
    search?: string;
    type?: string;
    status?: string;
  }): Promise<CounterpartyListResponse> {
    const response = await this.client.get<CounterpartyListResponse>(
      '/api/v1/counterparties',
      { params }
    );
    return response.data;
  }

  async getCounterpartyTypes(): Promise<CounterpartyTypeOption[]> {
    const response = await this.client.get<CounterpartyTypeOption[]>(
      '/api/v1/counterparties/types'
    );
    return response.data;
  }

  async getCounterparty(id: string): Promise<Counterparty> {
    const response = await this.client.get<Counterparty>(`/api/v1/counterparties/${id}`);
    return response.data;
  }

  async createCounterparty(data: CounterpartyCreate): Promise<Counterparty> {
    const response = await this.client.post<Counterparty>('/api/v1/counterparties', data);
    return response.data;
  }

  async updateCounterparty(id: string, data: CounterpartyUpdate): Promise<Counterparty> {
    const response = await this.client.patch<Counterparty>(
      `/api/v1/counterparties/${id}`,
      data
    );
    return response.data;
  }

  async archiveCounterparty(id: string, hard = false): Promise<{ ok: boolean; message: string }> {
    const response = await this.client.delete<{ ok: boolean; message: string }>(
      `/api/v1/counterparties/${id}`,
      { params: { hard } }
    );
    return response.data;
  }

  async lookupCounterparty(data: CounterpartyLookupRequest): Promise<CounterpartyLookupResponse> {
    const response = await this.client.post<CounterpartyLookupResponse>(
      '/api/v1/counterparties/lookup',
      data
    );
    return response.data;
  }

  async listCounterpartyContracts(id: string): Promise<CounterpartyContractsResponse> {
    const response = await this.client.get<CounterpartyContractsResponse>(
      `/api/v1/counterparties/${id}/contracts`
    );
    return response.data;
  }

  // ==================== Contract Relations & Parties ====================

  async getRelationTypes(): Promise<RelationTypeOption[]> {
    const response = await this.client.get<RelationTypeOption[]>(
      '/api/v1/contracts/relation-types'
    );
    return response.data;
  }

  async getPartyRoles(): Promise<PartyRoleOption[]> {
    const response = await this.client.get<PartyRoleOption[]>(
      '/api/v1/contracts/party-roles'
    );
    return response.data;
  }

  async getContractParties(contractId: string): Promise<ContractPartiesResponse> {
    const response = await this.client.get<ContractPartiesResponse>(
      `/api/v1/contracts/${contractId}/parties`
    );
    return response.data;
  }

  async addContractParty(contractId: string, data: ContractPartyCreate): Promise<ContractParty> {
    const response = await this.client.post<ContractParty>(
      `/api/v1/contracts/${contractId}/parties`,
      data
    );
    return response.data;
  }

  async updateContractParty(
    contractId: string,
    partyId: string,
    data: ContractPartyUpdate
  ): Promise<ContractParty> {
    const response = await this.client.patch<ContractParty>(
      `/api/v1/contracts/${contractId}/parties/${partyId}`,
      data
    );
    return response.data;
  }

  async removeContractParty(contractId: string, partyId: string): Promise<{ ok: boolean; message: string }> {
    const response = await this.client.delete<{ ok: boolean; message: string }>(
      `/api/v1/contracts/${contractId}/parties/${partyId}`
    );
    return response.data;
  }

  async getContractParents(contractId: string): Promise<ContractRelation[]> {
    const response = await this.client.get<ContractRelation[]>(
      `/api/v1/contracts/${contractId}/parents`
    );
    return response.data;
  }

  async getContractDerivatives(
    contractId: string,
    relationType?: ContractRelationType
  ): Promise<ContractRelation[]> {
    const response = await this.client.get<ContractRelation[]>(
      `/api/v1/contracts/${contractId}/derivatives`,
      { params: relationType ? { relation_type: relationType } : undefined }
    );
    return response.data;
  }

  async getContractRelated(contractId: string): Promise<ContractRelatedBundle> {
    const response = await this.client.get<ContractRelatedBundle>(
      `/api/v1/contracts/${contractId}/related`
    );
    return response.data;
  }

  async linkContractParent(
    contractId: string,
    data: ContractRelationCreate
  ): Promise<ContractRelation> {
    const response = await this.client.post<ContractRelation>(
      `/api/v1/contracts/${contractId}/relations`,
      data
    );
    return response.data;
  }

  async updateContractRelation(
    contractId: string,
    relationId: string,
    data: ContractRelationUpdate
  ): Promise<ContractRelation> {
    const response = await this.client.patch<ContractRelation>(
      `/api/v1/contracts/${contractId}/relations/${relationId}`,
      data
    );
    return response.data;
  }

  async unlinkContractRelation(
    contractId: string,
    relationId: string
  ): Promise<{ ok: boolean; message: string }> {
    const response = await this.client.delete<{ ok: boolean; message: string }>(
      `/api/v1/contracts/${contractId}/relations/${relationId}`
    );
    return response.data;
  }

  async verifyAgainstParent(
    contractId: string,
    relationId?: string
  ): Promise<VerificationReport> {
    const response = await this.client.post<VerificationReport>(
      `/api/v1/contracts/${contractId}/verify-against-parent`,
      undefined,
      { params: relationId ? { relation_id: relationId } : undefined, timeout: 120_000 }
    );
    return response.data;
  }

  async listVerifications(
    contractId: string,
    relationId?: string,
    limit = 20
  ): Promise<VerificationsListResponse> {
    const response = await this.client.get<VerificationsListResponse>(
      `/api/v1/contracts/${contractId}/verifications`,
      { params: { relation_id: relationId, limit } }
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
    const data = response.data;
    if (Array.isArray(data)) {
      return { sessions: data, total: data.length };
    }
    return data;
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

  async updateAgent(agentId: string, data: AgentDefinitionUpdate): Promise<AgentDefinition> {
    const response = await this.client.patch<AgentDefinition>(`/api/v2/agents/${agentId}`, data);
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

  // ==================== Integrations (v2) ====================

  async listWebhooks(orgId?: string): Promise<WebhookConfig[]> {
    const response = await this.client.get<WebhookConfig[]>(
      '/api/v2/integrations/webhooks',
      { params: orgId ? { org_id: orgId } : undefined }
    );
    return response.data;
  }

  async createWebhook(data: {
    name: string;
    url: string;
    secret?: string;
    event_filter?: string[];
    org_id?: string;
  }): Promise<WebhookConfig> {
    const response = await this.client.post<WebhookConfig>(
      '/api/v2/integrations/webhooks',
      data
    );
    return response.data;
  }

  async deactivateWebhook(configId: string): Promise<void> {
    await this.client.delete(`/api/v2/integrations/webhooks/${configId}`);
  }

  async getWebhookDeliveries(configId: string, limit: number = 50): Promise<WebhookDelivery[]> {
    const response = await this.client.get<WebhookDelivery[]>(
      `/api/v2/integrations/webhooks/${configId}/deliveries`,
      { params: { limit } }
    );
    return response.data;
  }

  async retryFailedDeliveries(limit: number = 50): Promise<{ retried: number }> {
    const response = await this.client.post<{ retried: number }>(
      '/api/v2/integrations/webhooks/retry',
      null,
      { params: { limit } }
    );
    return response.data;
  }

  async listDomainEvents(params?: {
    entity_type?: string;
    entity_id?: string;
    event_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<DomainEvent[]> {
    const response = await this.client.get<DomainEvent[]>(
      '/api/v2/integrations/events',
      { params }
    );
    return response.data;
  }

  async listEventTypes(): Promise<EventTypeInfo[]> {
    const response = await this.client.get<EventTypeInfo[]>(
      '/api/v2/integrations/events/types'
    );
    return response.data;
  }

  // ==================== Graph-RAG ====================

  async graphAsk(body: GraphAskRequest): Promise<GraphAskResponse> {
    const response = await this.client.post<GraphAskResponse>('/api/v2/graph/ask', body);
    return response.data;
  }

  async graphSearch(body: GraphSearchRequest): Promise<GraphSearchResponse> {
    const response = await this.client.post<GraphSearchResponse>('/api/v2/graph/search', body);
    return response.data;
  }

  async graphIngest(body: GraphIngestRequest): Promise<GraphIngestResponse> {
    const response = await this.client.post<GraphIngestResponse>('/api/v2/graph/ingest', body);
    return response.data;
  }

  async graphListDocuments(layer?: string, limit?: number): Promise<{ documents: GraphDocumentSummary[]; count: number }> {
    const response = await this.client.get<{ documents: GraphDocumentSummary[]; count: number }>(
      '/api/v2/graph/documents',
      { params: { layer, limit } }
    );
    return response.data;
  }

  async graphGetDocument(documentId: string, maxDepth?: number): Promise<GraphDocumentTree> {
    const response = await this.client.get<GraphDocumentTree>(
      `/api/v2/graph/documents/${documentId}`,
      { params: { max_depth: maxDepth } }
    );
    return response.data;
  }

  async graphGetNode(nodeId: string, includeContext?: boolean): Promise<GraphNodeDetail> {
    const response = await this.client.get<GraphNodeDetail>(
      `/api/v2/graph/nodes/${nodeId}`,
      { params: { include_context: includeContext } }
    );
    return response.data;
  }

  async graphStats(documentId?: string): Promise<GraphStats> {
    const response = await this.client.get<GraphStats>(
      '/api/v2/graph/stats',
      { params: { document_id: documentId } }
    );
    return response.data;
  }

  async graphEntitySummary(documentId: string): Promise<GraphEntitySummary> {
    const response = await this.client.get<GraphEntitySummary>(
      `/api/v2/graph/entities/${documentId}`
    );
    return response.data;
  }

  async graphNormReferences(documentId: string, normCode?: string): Promise<{ references: unknown[]; count: number; by_npa: Record<string, number> }> {
    const response = await this.client.get(
      `/api/v2/graph/references/${documentId}`,
      { params: { norm_code: normCode } }
    );
    return response.data;
  }

  async graphProposeEdge(body: ProposeEdgeRequest): Promise<{ candidate_id: string; status: string; message: string }> {
    const response = await this.client.post('/api/v2/graph/candidates', body);
    return response.data;
  }

  async graphReviewCandidate(candidateId: string, result: 'accepted' | 'rejected' | 'modified', comment?: string): Promise<Record<string, unknown>> {
    const response = await this.client.post(`/api/v2/graph/candidates/${candidateId}/review`, { result, comment });
    return response.data;
  }

  async graphPendingCandidates(limit?: number): Promise<{ candidates: GraphCandidateEdge[]; count: number }> {
    const response = await this.client.get<{ candidates: GraphCandidateEdge[]; count: number }>(
      '/api/v2/graph/candidates/pending',
      { params: { limit } }
    );
    return response.data;
  }

  // ── RAG Admin ──────────────────────────────────────────────────────────────

  async getRagStats(): Promise<{ collections: RAGCollectionStat[] }> {
    const response = await this.client.get('/api/v1/rag/stats');
    return response.data;
  }

  async listRagDocuments(collection: string): Promise<{ documents: RAGDocument[]; total: number }> {
    const response = await this.client.get('/api/v1/rag/documents', { params: { collection } });
    return response.data;
  }

  async uploadRagDocument(file: File, collection: string, docType?: string): Promise<RAGUploadResult> {
    const formData = new FormData();
    formData.append('file', file);
    const params: Record<string, string> = { collection };
    if (docType) params.doc_type = docType;
    const response = await this.client.post('/api/v1/rag/documents', formData, {
      params,
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  async deleteRagDocument(docId: string, collection: string): Promise<{ ok: boolean; deleted_chunks: number }> {
    const response = await this.client.delete(`/api/v1/rag/documents/${docId}`, { params: { collection } });
    return response.data;
  }
}

// Export singleton instance
const api = new APIClient();
export default api;
