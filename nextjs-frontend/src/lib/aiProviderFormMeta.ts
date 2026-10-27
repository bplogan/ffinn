/** Shared copy and helpers for AI provider configuration forms. */

export const AZURE_ENDPOINT_HINT =
  'https://YOUR-RESOURCE.openai.azure.com (no path, no trailing slash)'

export interface ProviderCatalogEntry {
  value: string
  label: string
  hint: string
  keyPlaceholder: string
  /** Where to create a key. */
  keyHelpUrl?: string
  /** 'none' = hide the field, 'optional' = show but may be blank, 'required' = must be filled. */
  endpoint: 'none' | 'optional' | 'required'
  endpointPlaceholder?: string
  needsKey: boolean
  /** Placeholder only; real choices come from the provider's live model list. */
  modelPlaceholder: string
}

/** One entry per provider card. Model lists are fetched live, never hardcoded here. */
export const PROVIDER_CATALOG: ProviderCatalogEntry[] = [
  {
    value: 'openai', label: 'OpenAI', hint: 'GPT models',
    keyPlaceholder: 'sk-...', keyHelpUrl: 'https://platform.openai.com/api-keys',
    endpoint: 'none', needsKey: true, modelPlaceholder: 'gpt-4o',
  },
  {
    value: 'anthropic', label: 'Anthropic', hint: 'Claude models',
    keyPlaceholder: 'sk-ant-...', keyHelpUrl: 'https://console.anthropic.com/settings/keys',
    endpoint: 'none', needsKey: true, modelPlaceholder: 'claude-sonnet-5-5',
  },
  {
    value: 'google', label: 'Google Gemini', hint: 'Gemini models, free tier available',
    keyPlaceholder: 'AIza...', keyHelpUrl: 'https://aistudio.google.com/apikey',
    endpoint: 'none', needsKey: true, modelPlaceholder: 'gemini-2.0-flash',
  },
  {
    value: 'github-models', label: 'GitHub Models', hint: 'Use a GitHub token',
    keyPlaceholder: 'ghp_... / github_pat_...', keyHelpUrl: 'https://github.com/settings/tokens',
    endpoint: 'none', needsKey: true, modelPlaceholder: 'gpt-4o',
  },
  {
    value: 'ollama', label: 'Ollama (local)', hint: 'Free, runs on your own machine',
    keyPlaceholder: '',
    endpoint: 'optional', endpointPlaceholder: 'http://localhost:11434',
    needsKey: false, modelPlaceholder: 'llama3.2',
  },
  {
    value: 'custom', label: 'OpenAI-compatible', hint: 'LM Studio, vLLM, OpenRouter, etc.',
    keyPlaceholder: 'API key (if the server needs one)',
    endpoint: 'required', endpointPlaceholder: 'https://api.example.com/v1',
    needsKey: false, modelPlaceholder: 'model-id',
  },
  {
    value: 'azure', label: 'Azure OpenAI (advanced)', hint: 'Needs an endpoint and a deployment name',
    keyPlaceholder: 'Azure API key',
    endpoint: 'required', endpointPlaceholder: AZURE_ENDPOINT_HINT,
    needsKey: true, modelPlaceholder: '',
  },
]

export function catalogEntry(type?: string): ProviderCatalogEntry | undefined {
  const t = normalizeProviderType(type)
  return PROVIDER_CATALOG.find(p => p.value === t)
}

export function normalizeProviderType(type?: string): string {
  const t = (type || '').toLowerCase()
  if (t === 'azure-openai' || t === 'azureopenai') return 'azure'
  if (t === 'google-gemini' || t === 'gemini') return 'google'
  if (t === 'github_models' || t === 'githubmodels') return 'github-models'
  return t
}

export function isAzureProvider(type?: string): boolean {
  const t = normalizeProviderType(type)
  return t === 'azure'
}

/** Resource slug from an Azure OpenAI endpoint, e.g. "contoso-openai". */
export function azureResourceNameFromEndpoint(endpoint?: string): string | null {
  if (!endpoint?.trim()) return null
  try {
    const url = endpoint.trim().startsWith('http') ? endpoint.trim() : `https://${endpoint.trim()}`
    const host = new URL(url).hostname
    if (!host.endsWith('.openai.azure.com')) return null
    return host.replace('.openai.azure.com', '') || null
  } catch {
    return null
  }
}

export interface AzureDeploymentOption {
  deployment_name: string
  model: string
}

export function formatAzureDeploymentOption(d: AzureDeploymentOption): string {
  if (!d.model || d.model.toLowerCase() === d.deployment_name.toLowerCase()) {
    return d.deployment_name
  }
  return `${d.deployment_name} (model: ${d.model})`
}

export function azureModelsMatch(deployment: string, model: string): boolean {
  const dep = deployment.trim()
  const mdl = model.trim()
  return !!dep && !!mdl && dep.toLowerCase() === mdl.toLowerCase()
}

export function providerDeploymentField(type?: string, resourceName?: string | null): {
  label: string
  placeholder: string
  hint: string
} | null {
  if (!isAzureProvider(type)) return null
  const resource = resourceName || 'your-resource'
  return {
    label: 'Deployment name',
    placeholder: 'e.g. my-gpt5-deployment',
    hint:
      `The name Azure uses to route API requests — from Portal → ${resource} → Model deployments → Deployment name.`,
  }
}

export function providerModelField(type?: string): {
  label: string
  placeholder: string
  hint: string
} {
  if (isAzureProvider(type)) {
    return {
      label: 'Model product',
      placeholder: 'e.g. gpt-5',
      hint: 'Optional label for ffinn when it differs from the deployment name (e.g. deployment prod-chat → model gpt-5).',
    }
  }
  return {
    label: 'Model',
    placeholder: 'gpt-4o',
    hint: 'Model ID from your provider (OpenAI model name, Claude model ID, etc.).',
  }
}

export function providerEndpointField(type?: string): {
  label: string
  placeholder: string
  hint?: string
} | null {
  const t = normalizeProviderType(type)
  if (t === 'azure') {
    return {
      label: 'Azure endpoint',
      placeholder: AZURE_ENDPOINT_HINT,
      hint: 'Your Azure OpenAI resource URL. The resource name in this URL is not the deployment name.',
    }
  }
  if (t === 'ollama') {
    return {
      label: 'Base URL',
      placeholder: 'http://localhost:11434',
    }
  }
  if (t === 'custom' || t === 'github-models') {
    return {
      label: 'Base URL',
      placeholder: t === 'github-models'
        ? 'https://models.inference.ai.azure.com'
        : 'https://api.example.com/v1',
    }
  }
  return {
    label: 'Base URL',
    placeholder: 'https://api.openai.com/v1',
    hint: 'Optional — for custom or Azure endpoints.',
  }
}

export function azureFieldWarnings(
  endpoint: string,
  deployment: string,
  model: string,
): string[] {
  const warnings: string[] = []
  const dep = deployment.trim()
  const mdl = model.trim()
  const resource = azureResourceNameFromEndpoint(endpoint)

  if (resource && dep && dep.toLowerCase() === resource.toLowerCase()) {
    warnings.push(
      `"${dep}" is your resource name (from https://${resource}.openai.azure.com), not a deployment name. ` +
      `Open Azure Portal → ${resource} → Model deployments and copy a name from the Deployment name column (e.g. gpt-5-mini, prod-chat).`,
    )
  }
  if (dep && /^(gpt-|o[0-9]|claude|text-embedding)/i.test(dep) && !mdl) {
    warnings.push('This looks like a model product name. The deployment name is usually a custom label you chose in Azure.')
  }
  return warnings
}

export function azureNamesTableRows(endpoint?: string): Array<{ portalLabel: string; example: string; ffinnField: string }> {
  const resource = azureResourceNameFromEndpoint(endpoint) || 'your-resource'
  return [
    { portalLabel: 'Resource name', example: resource, ffinnField: 'Endpoint URL only' },
    { portalLabel: 'Deployment name', example: 'prod-chat (your label in Azure)', ffinnField: 'Deployment name' },
    { portalLabel: 'Model', example: 'gpt-5', ffinnField: 'Model product (only if different)' },
    { portalLabel: 'Display name', example: 'Anything you like', ffinnField: 'Display name (ffinn only)' },
  ]
}
