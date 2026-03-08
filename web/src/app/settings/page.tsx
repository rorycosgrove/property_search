'use client';

import { useEffect, useState } from 'react';
import { getLLMConfig, getLLMHealth, getLLMModels, type LLMHealth, type LLMModelOption, updateLLMConfig } from '@/lib/api';

const FALLBACK_MODELS: LLMModelOption[] = [
  { id: 'amazon.titan-text-express-v1', label: 'Amazon Titan Text Express' },
  { id: 'amazon.titan-text-lite-v1', label: 'Amazon Titan Text Lite' },
  { id: 'amazon.nova-micro-v1:0', label: 'Amazon Nova Micro' },
  { id: 'amazon.nova-lite-v1:0', label: 'Amazon Nova Lite' },
  { id: 'amazon.nova-pro-v1:0', label: 'Amazon Nova Pro' },
  { id: 'anthropic.claude-3-haiku-20240307-v1:0', label: 'Anthropic Claude 3 Haiku' },
  { id: 'anthropic.claude-3-sonnet-20240229-v1:0', label: 'Anthropic Claude 3 Sonnet' },
  { id: 'anthropic.claude-3-5-sonnet-20240620-v1:0', label: 'Anthropic Claude 3.5 Sonnet' },
];

export default function SettingsPage() {
  const [provider, setProvider] = useState('bedrock');
  const [model, setModel] = useState('');
  const [health, setHealth] = useState<LLMHealth | null>(null);
  const [models, setModels] = useState<LLMModelOption[]>([]);
  const [modelsSource, setModelsSource] = useState<'api' | 'fallback'>('api');
  const [saveWarning, setSaveWarning] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let isMounted = true;

    Promise.allSettled([getLLMConfig(), getLLMModels(), getLLMHealth()])
      .then(([configResult, modelsResult, healthResult]) => {
        if (!isMounted) {
          return;
        }

        if (configResult.status === 'fulfilled') {
          setProvider(configResult.value.provider);
          setModel(configResult.value.model);
        }

        if (modelsResult.status === 'fulfilled') {
          const apiModels = modelsResult.value.models;
          if (!apiModels.length) {
            setModels(FALLBACK_MODELS);
            setModelsSource('fallback');
            setModel((current) => current || FALLBACK_MODELS[0]?.id || '');
          } else {
            setModels(apiModels);
            setModelsSource('api');
            setModel((current) => current || modelsResult.value.default_model || apiModels[0]?.id || '');
          }
        } else {
          setModels(FALLBACK_MODELS);
          setModelsSource('fallback');
          setModel((current) => current || FALLBACK_MODELS[0]?.id || '');
        }

        if (healthResult.status === 'fulfilled') {
          setHealth(healthResult.value);
        }
      })
      .catch(console.error)
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSave = async () => {
    if (!model || isSaving) {
      return;
    }

    try {
      setIsSaving(true);
      setSaveError(null);
      setSaveWarning(null);

      const result = await updateLLMConfig(provider, model || undefined);
      setSaveWarning(result.warning || null);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save LLM settings.';
      setSaveError(message);
      setSaved(false);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6 rise-in">
      <div className="rounded-xl border border-[var(--card-border)] ai-glass p-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">AI Control Center</p>
        <h1 className="text-2xl font-bold mt-1">Tune Atlas AI for your decision workflow</h1>
        <p className="text-sm text-[var(--muted)] mt-2">Choose your model, check readiness, and keep analysis quality high.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatusCard label="Provider" value={provider || 'n/a'} tone="neutral" />
        <StatusCard label="Readiness" value={health?.healthy ? 'Ready' : 'Attention needed'} tone={health?.healthy ? 'ok' : 'warn'} />
        <StatusCard label="Inference profile" value={health?.inference_profile_configured ? 'Configured' : 'Not configured'} tone={health?.inference_profile_configured ? 'ok' : 'warn'} />
      </div>

      <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Model Selection</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-[var(--muted)] mb-1">Provider</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-[var(--background)] border border-[var(--card-border)] rounded px-3 py-2"
            >
              <option value="bedrock">Amazon Bedrock (Cloud)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-[var(--muted)] mb-2">Model</label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {models.map((modelOption) => {
                const selected = modelOption.id === model;
                return (
                  <button
                    key={modelOption.id}
                    type="button"
                    onClick={() => setModel(modelOption.id)}
                    className={[
                      'text-left rounded-lg border px-3 py-3 transition-colors',
                      selected
                        ? 'border-[var(--accent)] bg-cyan-900/10'
                        : 'border-[var(--card-border)] bg-[var(--background)] hover:border-[var(--accent)]',
                    ].join(' ')}
                  >
                    <p className="text-sm font-semibold">{modelOption.label}</p>
                    <p className="text-xs text-[var(--muted)] mt-1 break-all">{modelOption.id}</p>
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-[var(--muted)] mt-2">
              {modelsSource === 'api'
                ? 'Live model list loaded from API.'
                : 'Using built-in fallback models because the models endpoint is unavailable.'}
            </p>
          </div>

          <button
            onClick={handleSave}
            disabled={!model || isSaving || isLoading}
            className="px-4 py-2 bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)] disabled:opacity-60 disabled:cursor-not-allowed rounded text-sm font-medium transition-colors"
          >
            {isSaving ? 'Saving...' : saved ? '✓ Saved' : 'Save'}
          </button>

          {saveError ? (
            <div className="rounded border border-[var(--danger)]/40 bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)]">
              {saveError}
            </div>
          ) : null}

          {saveWarning ? (
            <div className="rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-700">
              {saveWarning}
            </div>
          ) : null}

          {health?.reason ? (
            <div className="rounded border border-[var(--card-border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--muted)]">
              Health reason: {health.reason}
            </div>
          ) : null}
        </div>
      </div>

      <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-2">About</h2>
        <p className="text-sm text-[var(--muted)]">
          Atlas AI Property Decisions v0.1.0<br />
          Powered by AWS: Lambda, API Gateway, RDS PostgreSQL, Amazon Bedrock,
          SQS, and Amplify. Aggregates property listings from Daft.ie,
          MyHome.ie, PropertyPal, and the Property Price Register.
        </p>
      </div>
    </div>
  );
}

function StatusCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'neutral' | 'ok' | 'warn';
}) {
  const toneClasses = {
    neutral: 'border-[var(--card-border)] text-[var(--foreground)]',
    ok: 'border-emerald-300 text-emerald-700',
    warn: 'border-amber-300 text-amber-700',
  }[tone];

  return (
    <div className={`rounded-lg border bg-[var(--card-bg)] p-3 ${toneClasses}`}>
      <p className="text-xs uppercase tracking-wide opacity-80">{label}</p>
      <p className="text-sm font-semibold mt-1">{value}</p>
    </div>
  );
}
