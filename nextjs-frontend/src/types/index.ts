// ===== Auth =====
export interface LoginRequest { usernameOrEmail: string; password: string; tenantId?: string }
export interface RegisterRequest { firstName: string; lastName: string; email: string; password: string; tenantName?: string }
export interface AuthTokens { access_token: string; token_type: string; expires_in?: number }
export interface LoginResponse extends AuthTokens { user: User; requiresTwoFactor?: boolean; tenants?: TenantSummary[] }

// ===== User =====
export interface User {
  id: string
  userName: string
  email: string
  firstName?: string
  lastName?: string
  fullName?: string
  tenantId?: string
  tenantName?: string
  roles?: string[]
  permissions?: string[]
  isEmailConfirmed?: boolean
  phoneNumber?: string
  profilePictureUrl?: string
  createdAt?: string
  isImpersonating?: boolean
  impersonatorUserId?: string
  impersonatorUserName?: string
}

export interface UserListItem {
  id: string
  userName: string
  email: string
  firstName?: string
  lastName?: string
  fullName?: string
  isActive?: boolean
  createdAt?: string
  roles?: string[]
}

export interface CreateUserRequest {
  firstName: string
  lastName: string
  email: string
  userName?: string
  password?: string
  isActive?: boolean
  roleIds?: string[]
}

export interface UpdateUserRequest extends Partial<CreateUserRequest> { id: string }

// ===== Roles =====
export interface Role {
  id: string
  name: string
  displayName?: string
  description?: string
  isStatic?: boolean
  isDefault?: boolean
  permissionCount?: number
}

export interface CreateRoleRequest { name: string; displayName?: string; description?: string; isDefault?: boolean }

// ===== Permissions =====
export interface Permission { name: string; displayName?: string; parentName?: string }
export interface PermissionGroup { name: string; displayName?: string; permissions: Permission[]; children?: PermissionGroup[] }

// ===== Tenant =====
export interface Tenant {
  id: string
  name: string
  tenancyName: string
  isActive?: boolean
  editionId?: string
  editionName?: string
  createdAt?: string
}
export interface TenantSummary { id: string; name: string; tenancyName: string }
export interface CreateTenantRequest { name: string; tenancyName: string; adminEmail: string; adminPassword: string; isActive?: boolean }

// ===== Pagination =====
export interface PagedResult<T> { items: T[]; totalCount: number; total_count?: number; pageIndex?: number; page?: number; pageSize?: number; page_size?: number; total_pages?: number }
export interface PagedRequest { maxResultCount?: number; skipCount?: number; filter?: string; sorting?: string }

// ===== Audit Logs =====
export interface AuditLog {
  id: string
  userId?: string
  userName?: string
  tenantId?: string
  impersonatorUserId?: string
  serviceName?: string
  methodName?: string
  parameters?: string
  returnValue?: string
  executionTime?: string
  executionDuration?: number
  clientIpAddress?: string
  clientName?: string
  browserInfo?: string
  exception?: string
  httpStatusCode?: number
}

// ===== Subscription =====
export interface PlanPricing { monthly: number; yearly: number; currency: string }
export interface PlanFeature { id: string; name: string; description?: string; included?: boolean; enabled?: boolean; limit?: number }
export interface SubscriptionPlan {
  id: string
  name: string
  /** snake_case from backend */
  display_name?: string
  /** camelCase alias */
  displayName?: string
  description?: string
  /** legacy flat price field */
  price?: number
  /** snake_case from backend */
  price_monthly?: number
  price_annually?: number
  currency?: string
  trialDays?: number
  billingCycle?: 'monthly' | 'yearly'
  billingPeriod?: 'monthly' | 'yearly'
  /** nested pricing (from .NET backend) */
  pricing?: PlanPricing
  features?: (string | PlanFeature)[]
  /** snake_case from backend */
  is_active?: boolean
  is_public?: boolean
  /** camelCase alias */
  isActive?: boolean
  isDefault?: boolean
  isPopular?: boolean
  /** alias for isPopular */
  isRecommended?: boolean
  /** snake_case from backend */
  max_users?: number
  max_storage_gb?: number
  sort_order?: number
  stripe_price_id_monthly?: string
  stripe_price_id_annually?: string
  paypal_plan_id_monthly?: string
  paypal_plan_id_annually?: string
  /** camelCase aliases */
  maxUsers?: number
  maxStorage?: number
  sortOrder?: number
  stripePriceId?: string
}

export interface Subscription {
  id: string
  userId?: string
  tenantId?: string
  planId?: string
  planName?: string
  status?: string
  startDate?: string
  endDate?: string
  trialEndDate?: string
  currentPeriodEnd?: string
  paymentProvider?: 'stripe' | 'paypal'
  payment_provider?: string
}

// ===== AI Agent =====
export interface AIAgent {
  id: string
  name: string
  description?: string
  instructions?: string
  model?: string
  providerId?: string
  isActive?: boolean
  createdAt?: string
}

/** Maps to backend AIAgentConfiguration model */
export type AgentKind = 'build' | 'assistant'

export interface AIAgentConfig {
  id: string
  name?: string
  /** 'build' generates code; 'assistant' is a chat agent. */
  kind?: AgentKind
  /** The framework's build agent: always present, cannot be removed. */
  is_default?: boolean
  description?: string | null
  system_prompt?: string | null
  temperature?: number | null
  avatar?: string | null
  source_control_type?: string
  source_control_provider?: string
  repository_url?: string
  /** Saved AI provider this agent uses (keys live on the provider, not the agent). */
  provider_id?: string | null
  ai_provider?: string
  ai_model?: string
  azure_deployment_name?: string
  ai_endpoint?: string
  azure_openai_endpoint?: string
  is_active?: boolean
  staging_workflow_id?: string
  release_workflow_id?: string
  created_at?: string
}

export interface AIProvider {
  id: string
  name: string
  display_name?: string
  provider_name?: string
  /** legacy camelCase alias */
  type?: string
  isActive?: boolean
  is_active?: boolean
  apiKeyConfigured?: boolean
  models?: string[]
  model_name?: string
  deployment_name?: string
  extra_config?: { deployment_name?: string; model?: string }
  endpoint?: string
  endpoint_url?: string
}

export type GenerationTargetScope = 'host' | 'tenant'

export interface ChatAttachmentSummary {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  readable?: boolean
}

export interface ChatConversation {
  id: string
  agent_id: string
  title: string
  created_at?: string | null
  updated_at?: string | null
}

export interface ChatMessage {
  id: string
  conversation_id?: string
  role: 'user' | 'assistant'
  content: string
  attachments: ChatAttachmentSummary[]
  model?: string | null
  tokens_used?: number | null
  error?: string | null
  created_at?: string | null
  /** Client-only: reply still arriving. */
  streaming?: boolean
}

export type ChatStreamEvent =
  | { type: 'user_message'; message: ChatMessage; title: string }
  | { type: 'assistant_start'; message_id: string }
  | { type: 'token'; text: string }
  | { type: 'done'; message: ChatMessage }
  | { type: 'error'; message: string }

/** Full generation record returned by /api/aiagent/generations */
export interface AIGeneration {
  id: string
  config_id?: string
  configuration_id?: string
  feature_name?: string
  user_prompt: string
  target_scope?: GenerationTargetScope
  status: string
  branch_name?: string
  commit_sha?: string
  pr_number?: number
  pr_url?: string
  pull_request_number?: number
  pull_request_url?: string
  staging_url?: string
  staging_frontend_url?: string
  pipeline_url?: string
  build_url?: string
  error_message?: string
  tokens_used?: number
  estimated_cost?: number
  generated_files?: Record<string, string>
  validation_errors?: string[]
  code_review_status?: string
  scheduled_release_at?: string
  ai_model?: string
  provider_override?: string
  model_override?: string
  created_at?: string
  updated_at?: string
}

/** Progress event from /api/aiagent/generations/{id}/progress */
export interface GenerationProgressEvent {
  id: string
  event_type: string
  message: string
  step?: string
  created_at?: string
}

/** Legacy alias — kept for history page backward compat */
export interface AIGenerationHistory {
  id: string
  agentId?: string
  agentName?: string
  /** feature_name from backend */
  feature_name?: string
  /** user_prompt from backend */
  user_prompt?: string
  /** legacy alias */
  prompt?: string
  response?: string
  model?: string
  ai_model?: string
  tokens_used?: number
  durationMs?: number
  created_at?: string
  status?: string
}

export interface CustomDomain {
  id: string
  domain: string
  isVerified?: boolean
  status?: string
  /** backend returns last_verified_at */
  last_verified_at?: string
  /** legacy camelCase alias */
  verifiedAt?: string
  tenantId?: string
  tenant_id?: string
  createdAt?: string
  created_at?: string
  is_active?: boolean
}

// ===== Settings =====
export interface AppSetting { key: string; value?: string; description?: string; isEncrypted?: boolean }

// ===== SSO =====
export interface SsoConfiguration {
  id: string
  tenant_id?: string
  provider: 'OIDC' | 'SAML' | string
  provider_name: string
  client_id?: string
  client_secret?: string
  metadata_url?: string
  metadata_xml?: string
  is_enabled?: boolean
  auto_provision_users?: boolean
  default_role?: string
  created_at?: string
  updated_at?: string
  // legacy camelCase aliases
  providerName?: string
  clientId?: string
  clientSecret?: string
  metadataUrl?: string
  isActive?: boolean
  authority?: string
  redirectUri?: string
}

export interface SsoProvider {
  id: string
  provider: string
  provider_name: string
  is_enabled?: boolean
}

export interface ExternalSsoProvider {
  id: string
  name: string
  provider: string
  login_url: string
}

// ===== Cloud Setup =====
export interface CloudSetupProgress {
  setup_id: string
  status: string
  current_step: number
  total_steps: number
  steps_completed: string[]
  steps_pending: string[]
  cloud_provider?: string
  cloud_authenticated?: boolean
  cloud_provisioned?: boolean
  github_authenticated?: boolean
  github_configured?: boolean
  app_settings_saved?: boolean
  completed_at?: string
  created_at?: string
  updated_at?: string
}

// ===== Notifications =====
export interface NotificationConfiguration {
  id?: string
  tenantId?: string
  smsEnabled?: boolean
  twilioAccountSid?: string
  twilioFromNumber?: string
  hasTwilioAuthToken?: boolean
  pushEnabled?: boolean
  pushProvider?: 'firebase' | 'twilio'
  firebaseProjectId?: string
  hasFirebaseCredentials?: boolean
  twilioNotifyServiceSid?: string
}

// ===== Team Invitation =====
export interface TeamInvitation {
  id: string
  email: string
  roleId?: string
  roleName?: string
  tenantId?: string
  status?: string
  createdAt?: string
  expiresAt?: string
}

// ===== Dashboard =====
export interface DashboardStats {
  totalUsers?: number
  totalTenants?: number
  activeSubscriptions?: number
  aiGenerations?: number
  userGrowth?: number
  revenueTotal?: number
}

export interface ActivityItem {
  id: string
  userId?: string
  userName?: string
  action?: string
  resource?: string
  createdAt?: string
}

// ===== Feature Flags =====
export interface FeatureFlag {
  id?: string
  name: string
  description?: string | null
  is_enabled?: boolean
  isEnabled?: boolean
  rollout_percentage?: number
  rolloutPercentage?: number
  created_at?: string
  updated_at?: string
}

// ===== Editions =====
export interface EditionFeature {
  id: string
  edition_id: string
  feature_name: string
  display_name: string
  feature_value?: string | null
  is_included: boolean
  sort_order: number
}

export interface Edition {
  id: string
  display_name: string
  is_free: boolean
  price_monthly: number
  price_annually: number
  currency: string
  sort_order: number
  is_public: boolean
  trial_day_count?: number | null
  is_trial_active: boolean
  features: EditionFeature[]
  created_at?: string
  updated_at?: string
  /** Loaded separately on demand */
  tenant_count?: number
}

// ===== Onboarding =====
export interface OnboardingStep {
  id?: string
  key: string
  title: string
  description?: string
  isCompleted?: boolean
  order?: number
}
