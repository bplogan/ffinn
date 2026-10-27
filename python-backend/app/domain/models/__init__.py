"""Domain models package."""
from app.domain.models.identity import (
    IdentityUser, IdentityRole, IdentityUserRole, IdentityUserClaim,
    IdentityUserToken, IdentityRoleClaim, PermissionGrant,
    EmailConfirmationToken, PasswordResetToken, SsoConfiguration, SsoAuthState,
    TwoFactorAuth, UserDelegation,
)
from app.domain.models.tenant import Tenant, TenantOnboarding, TeamInvitation
from app.domain.models.subscription import (
    Edition, SubscriptionPlan, PlanFeature, TenantSubscription,
    EnhancedTenantSubscription, BillingHistory, SubscriptionPayment, InvoiceInfo,
)
from app.domain.models.ai_agent import (
    AIAgentConfiguration, AIAgentGeneration, AIAgentProgressEvent,
    AIAgentQueueItem, AIProviderConfiguration, CustomDomain,
    AIConversation, AIMessage, AIAttachment,
)
from app.domain.models.audit import AuditLog
from app.domain.models.misc import (
    AppSetting, FeatureDefinition, FeatureValue, PlanFeatureFlag,
    FeatureFlag, FileUpload, DashboardLayout, ContactMessage,
)
from app.domain.models.cloud_setup import (
    CloudSetupProgress, CloudProviderCredentials, GitHubIntegration,
)
from app.domain.models.notifications import NotificationConfiguration

# AI-generated model imports — DO NOT REMOVE THIS COMMENT
from app.domain.models.projects import ProjectStatus

__all__ = [
    "IdentityUser", "IdentityRole", "IdentityUserRole", "IdentityUserClaim",
    "IdentityUserToken", "IdentityRoleClaim", "PermissionGrant",
    "EmailConfirmationToken", "PasswordResetToken", "SsoConfiguration", "SsoAuthState",
    "TwoFactorAuth", "UserDelegation",
    "Tenant", "TenantOnboarding", "TeamInvitation",
    "Edition", "SubscriptionPlan", "PlanFeature", "TenantSubscription",
    "EnhancedTenantSubscription", "BillingHistory", "SubscriptionPayment", "InvoiceInfo",
    "AIAgentConfiguration", "AIAgentGeneration", "AIAgentProgressEvent",
    "AIAgentQueueItem", "AIProviderConfiguration", "CustomDomain",
    "AIConversation", "AIMessage", "AIAttachment",
    "AuditLog",
    "AppSetting", "FeatureDefinition", "FeatureValue", "PlanFeatureFlag",
    "FeatureFlag", "FileUpload", "DashboardLayout", "ContactMessage",
    "CloudSetupProgress", "CloudProviderCredentials", "GitHubIntegration",
    "NotificationConfiguration",
    "ProjectStatus",
]
