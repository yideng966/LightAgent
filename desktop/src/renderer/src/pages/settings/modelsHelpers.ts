import type { ModelEntry, ModelOption, ModelProvider, ModelsData } from '../../types'
import { localizedLabel } from '../../i18n'

// Normalize a string|{value,hint} entry into a uniform option shape.
export function normEntry(e: ModelEntry): ModelOption {
  return typeof e === 'string' ? { value: e } : e
}

export function normEntries(arr?: ModelEntry[]): ModelOption[] {
  return (arr || []).map(normEntry)
}

// Resolve a human label for a provider id, falling back to the id itself.
// Handles expanded custom ids ("custom:<id>") via the providers overview.
export function providerLabel(data: ModelsData | null, id: string): string {
  if (!id) return ''
  const p = data?.providers?.find((x) => x.id === id)
  if (p) return localizedLabel(p.label) || id
  return id
}

export function findProvider(data: ModelsData | null, id: string): ModelProvider | undefined {
  return data?.providers?.find((x) => x.id === id)
}

// Resolve the model list for a capability+provider, mirroring the web console:
//   1. capability-scoped provider_models[id] (vision/image/asr/tts/embedding)
//   2. provider_models['custom'] for expanded custom:<id> providers
//   3. fall back to the vendor's generic models[] (chat has no provider_models)
export function resolveModels(
  data: ModelsData | null,
  providerId: string,
  providerModels?: Record<string, ModelEntry[]>
): ModelOption[] {
  if (!providerId) return []
  if (providerModels?.[providerId]) return normEntries(providerModels[providerId])
  if (providerId.startsWith('custom:') && providerModels?.['custom']) {
    return normEntries(providerModels['custom'])
  }
  return normEntries(findProvider(data, providerId)?.models)
}

// Voices for a tts provider may be a flat list or, for linkai, keyed by model.
export function resolveVoices(
  provider: string,
  model: string,
  voicesMap?: Record<string, ModelEntry[] | Record<string, ModelEntry[]>>
): ModelOption[] {
  const raw = voicesMap?.[provider]
  if (!raw) return []
  if (Array.isArray(raw)) return normEntries(raw)
  // keyed by model (linkai)
  const byModel = raw as Record<string, ModelEntry[]>
  return normEntries(byModel[model] || [])
}

export const CUSTOM_OPTION = '__custom__'
