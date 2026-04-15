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

export interface ContractRecommendationDecisionSummary {
  accepted: number;
  rejected: number;
  pending: number;
  total: number;
}

export interface ContractRecommendationDecisionResponse {
  contract_id: string;
  recommendation_id: number;
  decision: 'accepted' | 'rejected';
  summary: ContractRecommendationDecisionSummary;
  message: string;
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

export interface QuotaResponse {
  contracts_used: number;
  contracts_limit: number;
  llm_used: number;
  llm_limit: number;
  subscription_tier: string;
}

export interface PersonalStats {
  total_contracts: number;
  month_contracts: number;
  contracts_today: number;
  llm_requests_today: number;
  total_risks: number;
  risks_by_severity: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  subscription_tier: string;
}

export interface GroupStats {
  org_id: string;
  total_members: number;
  total_contracts: number;
  month_contracts: number;
  total_risks: number;
  per_member: Array<{
    user_id: string;
    name: string;
    contracts_count: number;
  }>;
}

export interface DemoLinkResponse {
  token: string;
  url: string;
  expires_at: string;
  max_contracts: number;
  max_llm_requests: number;
}

export interface GenerationContractTypeOption {
  code: string;
  name: string;
  source: string;
  has_template: boolean;
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

// Company Conditions types
export interface CompanyCondition {
  id: string;
  user_id: string;
  category: string;
  title: string;
  description: string | null;
  condition_text: string;
  priority: number;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface CompanyConditionCreate {
  category: string;
  title: string;
  description?: string;
  condition_text: string;
  priority?: number;
  is_active?: boolean;
}

export interface CompanyConditionUpdate {
  category?: string;
  title?: string;
  description?: string;
  condition_text?: string;
  priority?: number;
  is_active?: boolean;
}

export interface ConditionListResponse {
  conditions: CompanyCondition[];
  total: number;
  page: number;
  page_size: number;
}

export interface ConditionCategory {
  value: string;
  label: string;
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
  agent_id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  agent_type: string | null;
  specialization: string;
  capabilities: string[] | null;
  tools: string[] | null;
  allowed_tools: string[] | null;
  task_types: string[] | null;
  autonomy_level: string;
  confidence_threshold: number;
  model_profile: Record<string, any> | null;
  active: boolean;
  version: string;
  created_at: string;
}

export interface AgentDefinitionUpdate {
  allowed_tools?: string[];
  autonomy_level?: string;
  confidence_threshold?: number;
  model_profile?: Record<string, any>;
  active?: boolean;
  description?: string;
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
// ==================== Integration Types ====================

export interface WebhookConfig {
  id: string;
  name: string;
  integration_type: string;
  config: {
    url: string;
    secret?: string;
    event_filter?: string[];
  };
  active: boolean;
  org_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WebhookDelivery {
  id: string;
  config_id: string;
  event_type: string;
  status: 'pending' | 'delivered' | 'failed';
  response_code?: number | null;
  attempts: number;
  delivered_at?: string | null;
  created_at: string;
}

export interface DomainEvent {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  payload?: Record<string, any> | null;
  emitted_by?: string | null;
  created_at: string;
}

export interface EventTypeInfo {
  name: string;
  entity_type: string;
  description: string;
  severity: 'info' | 'warning' | 'critical';
}

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

// ==================== Core Contract Types ====================

export interface Contract {
  id: string;
  file_name: string;
  status: string;
  contract_type?: string;
  progress?: number;
  progress_message?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ContractUploadResponse {
  contract_id: string;
  file_name: string;
  status: string;
}

export interface AnalysisResultRequest {
  contract_id: string;
  analysis_type?: string;
  use_rag?: boolean;
}

export interface StreamAnalysisRequest {
  contract_id: string;
}

export interface AnalysisResultResponse {
  contract: Contract;
  analysis: {
    id?: string;
    version?: number;
    risks: any[];
    recommendations: any[];
    recommendation_summary: {
      accepted: number;
      rejected: number;
      pending: number;
      total: number;
    };
    required_fields: any[];
    analysis_context: Record<string, any>;
  } | null;
}

// ==================== Document Comment (renamed to avoid DOM Comment collision) ====================

export interface DocumentComment {
  id: string;
  document_id: string;
  author_id: string;
  content: string;
  parent_id?: string;
  parent_comment_id?: string;
  section?: string;
  status: string;
  created_at: string;
  updated_at: string;
  author_name?: string;
  author_role?: string;
  replies?: DocumentComment[];
}

// ==================== Graph-RAG ====================

export interface GraphAskRequest {
  query: string;
  document_ids?: string[];
  layers?: string[];
  top_k?: number;
  max_context_chars?: number;
}

export interface GraphAskResponse {
  context_text: string;
  system_prompt: string;
  sources: Array<{ node_id: string; document_id: string; text: string }>;
  confidence: string;
  metadata: Record<string, unknown>;
}

export interface GraphSearchRequest {
  query: string;
  document_ids?: string[];
  layers?: string[];
  top_k?: number;
}

export interface GraphSearchResult {
  node_id: string;
  document_id: string;
  number: string;
  node_type: string;
  title: string;
  text: string;
  score: number;
  match_type: string;
}

export interface GraphSearchResponse {
  results: GraphSearchResult[];
  count: number;
  query: string;
}

export interface GraphIngestRequest {
  text: string;
  title: string;
  layer: 'contract' | 'npa';
  contract_id?: string;
  legal_document_id?: string;
}

export interface GraphIngestResponse {
  document_id: string;
  title: string;
  nodes_count: number;
  edges_count: number;
  entities_count: number;
  fact_edges_count: number;
  errors: string[];
  warnings: string[];
}

export interface GraphDocumentSummary {
  id: string;
  title: string;
  layer: string;
  document_type: string;
  nodes_count: number;
  edges_count: number;
  created_at?: string;
}

export interface GraphDocumentTree {
  document: {
    id: string;
    title: string;
    layer: string;
    document_type: string;
    status: string;
    nodes_count: number;
    edges_count: number;
  };
  tree: GraphTreeNode[];
}

export interface GraphTreeNode {
  node_id: string;
  type: string;
  number: string;
  title: string;
  text_preview: string;
  children?: GraphTreeNode[];
}

export interface GraphNodeDetail {
  node_id: string;
  document_id: string;
  node_type: string;
  number: string;
  title: string;
  text: string;
  level: number;
  path?: Array<{ node_id: string; type: string; number: string; title: string }>;
  children?: Array<{ node_id: string; type: string; number: string; text: string }>;
  entities?: Array<{ type: string; value: string }>;
  references?: Array<{ target_id: string; edge_type: string; evidence: string }>;
}

export interface GraphStats {
  documents_total?: number;
  nodes_total?: number;
  edges_total?: number;
  entities_total?: number;
  by_layer?: Record<string, number>;
  document_id?: string;
  title?: string;
  layer?: string;
  status?: string;
  nodes_count?: number;
  edges_count?: number;
  entities_count?: number;
  pending_candidates?: number;
  by_node_type?: Record<string, number>;
}

export interface GraphEntitySummary {
  monetary: Array<{ value: string; amount?: number; currency?: string; node_id: string }>;
  dates: Array<{ value: string; date?: string; date_type?: string; node_id: string }>;
  norm_refs: Array<{ value: string; norm_code?: string; article?: string; node_id: string }>;
  clause_types: Array<{ value: string; node_id: string }>;
  contract_types: Array<{ value: string; node_id: string }>;
}

export interface GraphCandidateEdge {
  id: string;
  source_id: string;
  target_id: string;
  proposed_type: string;
  proposed_class: string;
  rationale: string;
  confidence: number;
  created_at?: string;
}

export interface ProposeEdgeRequest {
  source_id: string;
  target_id: string;
  proposed_type: string;
  proposed_class: 'analytical' | 'risk_signal';
  rationale: string;
  evidence?: string;
  confidence?: number;
}
