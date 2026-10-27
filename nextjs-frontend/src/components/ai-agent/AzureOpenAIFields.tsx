'use client'

import { useEffect, useMemo, useState } from 'react'
import type { UseFormRegisterReturn } from 'react-hook-form'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { aiProvidersApi } from '@/lib/api'
import {
  type AzureDeploymentOption,
  azureFieldWarnings,
  azureModelsMatch,
  azureNamesTableRows,
  formatAzureDeploymentOption,
  providerDeploymentField,
  providerModelField,
} from '@/lib/aiProviderFormMeta'
import toast from 'react-hot-toast'
import { RefreshCw, CheckCircle2 } from 'lucide-react'
import axios from 'axios'

function apiErrorMessage(err: unknown, fallback: string): string {
  if (!axios.isAxiosError(err)) return fallback
  const data = err.response?.data as { message?: string; detail?: string } | undefined
  return data?.detail || data?.message || fallback
}

interface AzureOpenAIFieldsProps {
  endpoint: string
  apiKey: string
  deployment: string
  model: string
  onDeploymentChange: (value: string) => void
  onModelChange: (value: string) => void
  providerId?: string
  deploymentRegister?: UseFormRegisterReturn
  modelRegister?: UseFormRegisterReturn
}

export default function AzureOpenAIFields({
  endpoint,
  apiKey,
  deployment,
  model,
  onDeploymentChange,
  onModelChange,
  providerId,
  deploymentRegister,
  modelRegister,
}: AzureOpenAIFieldsProps) {
  const [deployments, setDeployments] = useState<AzureDeploymentOption[]>([])
  const [loadingDeployments, setLoadingDeployments] = useState(false)
  const [manualEdit, setManualEdit] = useState(false)
  const [showSeparateModel, setShowSeparateModel] = useState(false)

  const resourceName = useMemo(() => {
    try {
      const url = endpoint.trim().startsWith('http') ? endpoint.trim() : `https://${endpoint.trim()}`
      const host = new URL(url).hostname
      if (host.endsWith('.openai.azure.com')) return host.replace('.openai.azure.com', '')
    } catch { /* ignore */ }
    return null
  }, [endpoint])

  const deploymentField = providerDeploymentField('azure', resourceName)
  const modelField = providerModelField('azure')
  const modelsMatch = azureModelsMatch(deployment, model)
  const usePickerPrimary = deployments.length > 0 && !manualEdit
  const showModelInput = showSeparateModel || !modelsMatch

  const warnings = azureFieldWarnings(endpoint, deployment, model)
  const tableRows = azureNamesTableRows(endpoint)

  useEffect(() => {
    if (!modelsMatch) setShowSeparateModel(true)
  }, [modelsMatch])

  const loadDeployments = async () => {
    if (!endpoint.trim()) {
      toast.error('Enter your Azure endpoint first.')
      return
    }
    if (!apiKey.trim() && !providerId) {
      toast.error('Enter your API key to load deployments from Azure.')
      return
    }
    setLoadingDeployments(true)
    try {
      const result = await aiProvidersApi.listAzureDeployments({
        endpoint: endpoint.trim(),
        api_key: apiKey.trim() || undefined,
        provider_id: providerId,
      })
      const rows = result.deployments ?? []
      setDeployments(rows)
      setManualEdit(false)
      if (!rows.length) {
        toast.error('No deployments found. Check endpoint and API key in Azure Portal.')
      } else {
        toast.success(`Found ${rows.length} deployment${rows.length === 1 ? '' : 's'} on this resource.`)
      }
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Could not load deployments from Azure.'))
    } finally {
      setLoadingDeployments(false)
    }
  }

  const pickDeployment = (name: string) => {
    if (!name) {
      onDeploymentChange('')
      onModelChange('')
      return
    }
    const match = deployments.find(d => d.deployment_name === name)
    onDeploymentChange(name)
    onModelChange(match?.model || name)
    setShowSeparateModel(!!match && !azureModelsMatch(name, match.model))
  }

  const handleDeploymentInput = (value: string) => {
    onDeploymentChange(value)
    if (modelsMatch || !showSeparateModel) onModelChange(value)
  }

  return (
    <div className="space-y-4">
      <details className="rounded-lg border border-gray-200 dark:border-gray-700 text-xs group">
        <summary className="px-3 py-2 cursor-pointer bg-gray-50 dark:bg-gray-800/80 font-medium text-gray-700 dark:text-gray-300 list-none flex items-center justify-between">
          <span>What are resource, deployment, and model names?</span>
          <span className="text-gray-400 group-open:rotate-180 transition-transform">▾</span>
        </summary>
        <table className="w-full border-t border-gray-200 dark:border-gray-700">
          <thead>
            <tr className="text-left text-gray-500">
              <th className="px-3 py-2 font-medium">Azure Portal</th>
              <th className="px-3 py-2 font-medium">Example</th>
              <th className="px-3 py-2 font-medium">ffinn field</th>
            </tr>
          </thead>
          <tbody>
            {tableRows.map(row => (
              <tr key={row.portalLabel} className="border-t border-gray-100 dark:border-gray-800">
                <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{row.portalLabel}</td>
                <td className="px-3 py-2 font-mono text-gray-600 dark:text-gray-400">{row.example}</td>
                <td className="px-3 py-2 text-gray-900 dark:text-white">{row.ffinnField}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      {resourceName && (
        <div className="p-3 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 text-xs text-blue-900 dark:text-blue-100 space-y-1">
          <p>
            <span className="font-semibold font-mono">{resourceName}</span> is your{' '}
            <span className="font-semibold">resource name</span> (from the endpoint URL).
          </p>
          <p className="text-blue-800/90 dark:text-blue-200/90">
            It is <span className="font-semibold">not</span> your deployment name. In Azure Portal go to{' '}
            <span className="font-mono">{resourceName}</span> → <span className="font-semibold">Model deployments</span>{' '}
            and use the <span className="font-semibold">Deployment name</span> column — or pick from the list below after loading.
          </p>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          icon={<RefreshCw size={14} />}
          loading={loadingDeployments}
          onClick={loadDeployments}
        >
          Load deployments from Azure
        </Button>
        <span className="text-xs text-gray-500 pb-1">
          Lists deployment names on resource{resourceName ? ` ${resourceName}` : ''} — not the resource name itself.
        </span>
      </div>

      {deployments.length > 0 && (
        <div className="space-y-1.5">
          <label className="label">Deployment *</label>
          <select
            className="input-field"
            value={deployment}
            onChange={e => pickDeployment(e.target.value)}
          >
            <option value="">Select deployment…</option>
            {deployments.map(d => (
              <option key={d.deployment_name} value={d.deployment_name}>
                {formatAzureDeploymentOption(d)}
              </option>
            ))}
          </select>
        </div>
      )}

      {usePickerPrimary && deployment && (
        <div className="p-3 rounded-lg border border-success-200 dark:border-success-800 bg-success-50 dark:bg-success-900/20 space-y-1">
          <p className="text-sm text-success-800 dark:text-success-200 flex items-center gap-2">
            <CheckCircle2 size={16} />
            Azure API will use deployment <span className="font-mono font-semibold">{deployment}</span>
          </p>
          {modelsMatch ? (
            <p className="text-xs text-success-700/80 dark:text-success-300/80">
              Azure reports the same name for the underlying model — you do not need a separate model field.
            </p>
          ) : (
            <p className="text-xs text-success-700/80 dark:text-success-300/80">
              Underlying model product: <span className="font-mono">{model}</span> (for reference in ffinn only).
            </p>
          )}
          <button
            type="button"
            className="text-xs text-brand-600 dark:text-brand-400 hover:underline"
            onClick={() => setManualEdit(true)}
          >
            Edit deployment name manually
          </button>
        </div>
      )}

      {(!usePickerPrimary || manualEdit) && (
        <Input
          {...(deploymentRegister ?? {})}
          label={
            <span className="inline-flex items-center gap-2 flex-wrap">
              {deploymentField?.label} *
              <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
                Sent to Azure API
              </span>
            </span>
          }
          placeholder={deploymentField?.placeholder}
          hint={deploymentField?.hint}
          value={deploymentRegister ? undefined : deployment}
          onChange={
            deploymentRegister
              ? e => {
                  deploymentRegister.onChange(e)
                  handleDeploymentInput(e.target.value)
                }
              : e => handleDeploymentInput(e.target.value)
          }
        />
      )}

      {manualEdit && deployments.length > 0 && (
        <button
          type="button"
          className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          onClick={() => setManualEdit(false)}
        >
          ← Back to deployment picker
        </button>
      )}

      {(!usePickerPrimary || manualEdit) && !showModelInput && modelsMatch && (
        <button
          type="button"
          className="text-xs text-brand-600 dark:text-brand-400 hover:underline"
          onClick={() => setShowSeparateModel(true)}
        >
          Model product differs from deployment name
        </button>
      )}

      {showModelInput && (!usePickerPrimary || manualEdit || showSeparateModel) && (
        <Input
          {...(modelRegister ?? {})}
          label={
            <span className="inline-flex items-center gap-2 flex-wrap">
              {modelField.label}
              <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                Reference in ffinn
              </span>
            </span>
          }
          placeholder={modelField.placeholder}
          hint={modelField.hint}
          value={modelRegister ? undefined : model}
          onChange={modelRegister ? undefined : e => onModelChange(e.target.value)}
        />
      )}

      {warnings.map(msg => (
        <div
          key={msg}
          className="p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-200"
        >
          {msg}
        </div>
      ))}
    </div>
  )
}
