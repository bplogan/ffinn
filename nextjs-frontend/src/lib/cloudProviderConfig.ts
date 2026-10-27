/** Cloud provider registry for the Cloud Setup Wizard. */

export type CloudFieldType = 'text' | 'password' | 'textarea'

export interface CloudCredentialField {
  key: string
  label: string
  type?: CloudFieldType
  required?: boolean
  placeholder?: string
  hint?: string
}

export interface CloudProvisionField {
  key: string
  label: string
  required?: boolean
  placeholder?: string
  hint?: string
}

export interface CloudProviderDef {
  value: string
  label: string
  defaultRegion: string
  credentialFields: CloudCredentialField[]
  provisionFields: CloudProvisionField[]
}

const COMMON_PROVISION_FIELDS: CloudProvisionField[] = [
  { key: 'region', label: 'Region', required: true },
  { key: 'environment_name', label: 'Environment name', placeholder: 'ffinn' },
]

export const CLOUD_PROVIDERS: CloudProviderDef[] = [
  {
    value: 'azure',
    label: 'Azure',
    defaultRegion: 'eastus',
    credentialFields: [
      { key: 'tenant_id', label: 'Tenant ID', required: true },
      { key: 'client_id', label: 'Client ID', required: true },
      { key: 'client_secret', label: 'Client secret', type: 'password', required: true },
      { key: 'subscription_id', label: 'Subscription ID', required: true },
    ],
    provisionFields: [
      { key: 'region', label: 'Region', required: true },
      { key: 'resource_group', label: 'Resource group', placeholder: 'rg-ffinn' },
      { key: 'environment_name', label: 'Environment name', placeholder: 'ffinn' },
    ],
  },
  {
    value: 'aws',
    label: 'AWS',
    defaultRegion: 'us-east-1',
    credentialFields: [
      { key: 'access_key_id', label: 'Access key ID', required: true },
      { key: 'secret_access_key', label: 'Secret access key', type: 'password', required: true },
      { key: 'region', label: 'Region', placeholder: 'us-east-1' },
    ],
    provisionFields: COMMON_PROVISION_FIELDS,
  },
  {
    value: 'gcp',
    label: 'Google Cloud',
    defaultRegion: 'us-central1',
    credentialFields: [
      { key: 'project_id', label: 'Project ID', required: true, placeholder: 'my-gcp-project' },
      {
        key: 'service_account_json',
        label: 'Service account JSON',
        type: 'textarea',
        required: true,
        placeholder: '{"type": "service_account", ...}',
        hint: 'Paste the full JSON key file from GCP Console → IAM → Service accounts.',
      },
    ],
    provisionFields: COMMON_PROVISION_FIELDS,
  },
  {
    value: 'oci',
    label: 'Oracle Cloud',
    defaultRegion: 'us-ashburn-1',
    credentialFields: [
      { key: 'tenancy_ocid', label: 'Tenancy OCID', required: true },
      { key: 'user_ocid', label: 'User OCID', required: true },
      { key: 'fingerprint', label: 'API key fingerprint', required: true },
      {
        key: 'private_key',
        label: 'Private key (PEM)',
        type: 'textarea',
        required: true,
        hint: 'Paste the contents of your OCI API private key file.',
      },
      { key: 'region', label: 'Region', placeholder: 'us-ashburn-1' },
    ],
    provisionFields: [
      { key: 'region', label: 'Region', required: true },
      {
        key: 'compartment_ocid',
        label: 'Compartment OCID',
        placeholder: 'ocid1.compartment.oc1..',
        hint: 'Target compartment for provisioning resources.',
      },
      { key: 'environment_name', label: 'Environment name', placeholder: 'ffinn' },
    ],
  },
  {
    value: 'local',
    label: 'Local',
    defaultRegion: 'local',
    credentialFields: [],
    provisionFields: [
      { key: 'environment_name', label: 'Environment name', placeholder: 'ffinn' },
    ],
  },
]

export function getCloudProvider(value?: string): CloudProviderDef | undefined {
  return CLOUD_PROVIDERS.find(p => p.value === value)
}

/** Flat default values for react-hook-form covering all provider fields. */
export function cloudAuthDefaultValues(): Record<string, string> {
  const values: Record<string, string> = { provider: 'azure' }
  for (const provider of CLOUD_PROVIDERS) {
    for (const field of provider.credentialFields) {
      values[field.key] = field.key === 'region' ? provider.defaultRegion : ''
    }
  }
  return values
}

export function cloudProvisionDefaultValues(providerValue?: string): Record<string, string> {
  const provider = getCloudProvider(providerValue) ?? CLOUD_PROVIDERS[0]
  const values: Record<string, string> = {}
  for (const field of provider.provisionFields) {
    if (field.key === 'region') {
      values[field.key] = provider.defaultRegion
    } else if (field.key === 'environment_name') {
      values[field.key] = 'ffinn'
    } else {
      values[field.key] = ''
    }
  }
  return values
}

/** Build the credentials payload for a given provider from form values. */
export function buildCloudCredentials(
  providerValue: string,
  formValues: Record<string, string>,
): Record<string, string> {
  const provider = getCloudProvider(providerValue)
  if (!provider) return {}
  const creds: Record<string, string> = {}
  for (const field of provider.credentialFields) {
    const value = formValues[field.key]?.trim()
    if (value) creds[field.key] = value
  }
  return creds
}

/** Build the provision payload, routing provider-specific fields into `extra`. */
export function buildCloudProvisionPayload(
  providerValue: string,
  formValues: Record<string, string>,
): { region: string; resource_group?: string; environment_name?: string; extra: Record<string, string> } {
  const provider = getCloudProvider(providerValue)
  const region = formValues.region?.trim() || provider?.defaultRegion || 'local'
  const environment_name = formValues.environment_name?.trim() || 'ffinn'
  const extra: Record<string, string> = {}

  if (providerValue === 'azure') {
    return {
      region,
      resource_group: formValues.resource_group?.trim() || undefined,
      environment_name,
      extra,
    }
  }
  if (providerValue === 'oci') {
    const compartment = formValues.compartment_ocid?.trim()
    if (compartment) extra.compartment_ocid = compartment
    return { region, environment_name, extra }
  }
  if (providerValue === 'gcp') {
    return { region, environment_name, extra }
  }
  if (providerValue === 'local') {
    return { region: 'local', environment_name, extra }
  }
  // AWS and fallback
  return { region, environment_name, extra }
}
