'use client'

import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { clsx } from 'clsx'
import { CheckCircle2, ExternalLink, Loader2, RefreshCw, XCircle, Zap } from 'lucide-react'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { aiProvidersApi } from '@/lib/api'
import { PROVIDER_CATALOG, catalogEntry, isAzureProvider } from '@/lib/aiProviderFormMeta'
import AzureOpenAIFields from '@/components/ai-agent/AzureOpenAIFields'

/** Everything the user types to describe one AI provider. Shared by the wizard and Providers page. */
export interface ProviderDraft {
  type: string
  name: string
  apiKey: string
  baseUrl: string
  /** Model id. For Azure this is the underlying model; the routing id is `deployment`. */
  model: string
  deployment: string
}

export const EMPTY_PROVIDER_DRAFT: ProviderDraft = {
  type: 'openai', name: 'OpenAI', apiKey: '', baseUrl: '', model: '', deployment: '',
}

interface Props {
  value: ProviderDraft
  onChange: (patch: Partial<ProviderDraft>) => void
  /** Set when editing a saved provider: a blank key then means "keep the stored key". */
  providerId?: string
  /** Called whenever a Test finishes, so the parent can show/require the result. */
  onTested?: (ok: boolean) => void
}

function errText(err: unknown, fallback: string): string {
  if (!axios.isAxiosError(err)) return fallback
  const d = err.response?.data as { detail?: string; message?: string } | undefined
  return d?.detail || d?.message || fallback
}

export function providerDraftReady(d: ProviderDraft, editing = false): boolean {
  const entry = catalogEntry(d.type)
  if (!entry) return false
  if (entry.needsKey && !d.apiKey.trim() && !editing) return false
  if (entry.endpoint === 'required' && !d.baseUrl.trim()) return false
  if (isAzureProvider(d.type)) return !!d.deployment.trim()
  return !!d.model.trim()
}

export default function ProviderSetupForm({ value, onChange, providerId, onTested }: Props) {
  const entry = catalogEntry(value.type) ?? PROVIDER_CATALOG[0]
  const azure = isAzureProvider(value.type)
  const editing = !!providerId

  const [models, setModels] = useState<string[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const requestSeq = useRef(0)

  const canFetchModels =
    !azure &&
    (entry.needsKey ? !!value.apiKey.trim() || editing : true) &&
    (entry.endpoint !== 'required' || !!value.baseUrl.trim())

  const fetchModels = async () => {
    const seq = ++requestSeq.current
    setModelsLoading(true)
    setModelsError(null)
    try {
      const res = await aiProvidersApi.listModels({
        provider_name: value.type,
        api_key: value.apiKey.trim() || undefined,
        provider_id: providerId,
        endpoint: value.baseUrl.trim() || undefined,
      })
      if (seq !== requestSeq.current) return
      setModels(res.models ?? [])
      setModelsError(res.error)
      if (!value.model.trim() && res.models?.length) {
        onChange({ model: res.models.includes(entry.modelPlaceholder) ? entry.modelPlaceholder : res.models[0] })
      }
    } catch (err) {
      if (seq !== requestSeq.current) return
      setModels([])
      setModelsError(errText(err, 'Could not load models.'))
    } finally {
      if (seq === requestSeq.current) setModelsLoading(false)
    }
  }

  // Load the live model list once there is enough to ask the provider (debounced while typing).
  useEffect(() => {
    setTestResult(null)
    if (!canFetchModels) {
      requestSeq.current++
      setModels([])
      setModelsError(null)
      setModelsLoading(false)
      return
    }
    const t = setTimeout(fetchModels, editing && !value.apiKey ? 0 : 700)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.type, value.apiKey, value.baseUrl, providerId, canFetchModels])

  const runTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await aiProvidersApi.testCredentials({
        provider_name: value.type,
        api_key: value.apiKey.trim() || undefined,
        provider_id: providerId,
        endpoint: value.baseUrl.trim() || undefined,
        model_name: (azure ? value.deployment : value.model).trim(),
      })
      setTestResult({ ok: res.success, message: res.message })
      onTested?.(res.success)
    } catch (err) {
      setTestResult({ ok: false, message: errText(err, 'The test request failed.') })
      onTested?.(false)
    } finally {
      setTesting(false)
    }
  }

  const pickType = (type: string) => {
    const next = catalogEntry(type)
    onChange({
      type,
      name: next?.label.replace(' (advanced)', '') ?? type,
      apiKey: '', baseUrl: '', model: '', deployment: '',
    })
  }

  return (
    <div className="space-y-5">
      {/* 1. Provider */}
      {!editing && (
        <div>
          <p className="label mb-2">Provider</p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {PROVIDER_CATALOG.map(p => (
              <button
                key={p.value}
                type="button"
                onClick={() => pickType(p.value)}
                className={clsx(
                  'flex items-start gap-3 p-3 rounded-xl border-2 text-left transition-all',
                  value.type === p.value
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-brand-300',
                )}
              >
                <div className={clsx(
                  'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0',
                  value.type === p.value ? 'bg-brand-500 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-500',
                )}>
                  <Zap size={13} />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white">{p.label}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 leading-snug">{p.hint}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 2. Credentials */}
      <div className="grid gap-4 md:grid-cols-2">
        {(entry.needsKey || entry.value === 'custom') && (
          <Input
            label={entry.needsKey ? 'API key' : 'API key (optional)'}
            type="password"
            autoComplete="off"
            placeholder={editing ? 'Leave blank to keep the saved key' : entry.keyPlaceholder}
            value={value.apiKey}
            onChange={e => onChange({ apiKey: e.target.value })}
            hint={
              editing
                ? 'Stored encrypted.'
                : undefined
            }
          />
        )}
        {entry.endpoint !== 'none' && (
          <Input
            label={azure ? 'Azure endpoint' : entry.endpoint === 'required' ? 'Base URL' : 'Base URL (optional)'}
            placeholder={entry.endpointPlaceholder}
            value={value.baseUrl}
            onChange={e => onChange({ baseUrl: e.target.value })}
            hint={azure ? 'Your resource URL. The resource name is not the deployment name.' : undefined}
          />
        )}
      </div>
      {entry.keyHelpUrl && !editing && (
        <a
          href={entry.keyHelpUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-brand-600 dark:text-brand-400 hover:underline -mt-2"
        >
          Where do I get a key? <ExternalLink size={11} />
        </a>
      )}

      {/* 3. Model */}
      {azure ? (
        <AzureOpenAIFields
          endpoint={value.baseUrl}
          apiKey={value.apiKey}
          deployment={value.deployment}
          model={value.model}
          providerId={providerId}
          onDeploymentChange={v => onChange({ deployment: v })}
          onModelChange={v => onChange({ model: v })}
        />
      ) : (
        <div className="space-y-1.5">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Input
                label="Model"
                list="provider-model-options"
                placeholder={entry.modelPlaceholder}
                value={value.model}
                onChange={e => onChange({ model: e.target.value })}
                autoComplete="off"
              />
              <datalist id="provider-model-options">
                {models.map(m => <option key={m} value={m} />)}
              </datalist>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={modelsLoading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
              disabled={!canFetchModels || modelsLoading}
              onClick={fetchModels}
              title="Reload the model list from the provider"
            >
              Reload
            </Button>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {modelsLoading && 'Loading models from the provider…'}
            {!modelsLoading && models.length > 0 && `${models.length} models available — click the field to pick one, or type any model id.`}
            {!modelsLoading && !models.length && !modelsError && (canFetchModels
              ? 'Type a model id.'
              : 'Enter your key and the available models will load here.')}
          </p>
          {modelsError && !modelsLoading && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              Could not load the model list: {modelsError} You can still type a model id.
            </p>
          )}
        </div>
      )}

      {/* 4. Name + test */}
      <Input
        label="Display name"
        value={value.name}
        onChange={e => onChange({ name: e.target.value })}
        hint="Only used to tell your providers apart."
      />

      <div className="space-y-2">
        <Button
          type="button"
          variant="secondary"
          icon={<CheckCircle2 size={15} />}
          loading={testing}
          disabled={!providerDraftReady(value, editing)}
          onClick={runTest}
        >
          Test connection
        </Button>
        {testResult && (
          <p
            role="status"
            className={clsx(
              'flex items-start gap-2 text-sm rounded-lg px-3 py-2 border',
              testResult.ok
                ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300'
                : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300',
            )}
          >
            {testResult.ok ? <CheckCircle2 size={16} className="mt-0.5 flex-shrink-0" /> : <XCircle size={16} className="mt-0.5 flex-shrink-0" />}
            <span>{testResult.message}</span>
          </p>
        )}
      </div>
    </div>
  )
}

/** Request body for POST/PUT /api/aiagent/providers built from a draft. */
export function providerDraftToPayload(d: ProviderDraft) {
  const azure = isAzureProvider(d.type)
  return {
    provider_name: d.type,
    display_name: d.name.trim() || undefined,
    api_key: d.apiKey.trim() || undefined,
    deployment_name: azure ? d.deployment.trim() || undefined : undefined,
    model_name: azure ? (d.model.trim() || d.deployment.trim() || undefined) : d.model.trim() || undefined,
    endpoint: d.baseUrl.trim() || undefined,
  }
}
