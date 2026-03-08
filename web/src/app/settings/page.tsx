'use client';

import { useEffect, useState } from 'react';
import { getLLMConfig, getLLMModels, type LLMModelOption, updateLLMConfig } from '@/lib/api';

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
  const [models, setModels] = useState<LLMModelOption[]>([]);
  const [modelsSource, setModelsSource] = useState<'api' | 'fallback'>('api');
  const [saveWarning, setSaveWarning] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let isMounted = true;

    getLLMConfig()
      .then((config) => {
        if (!isMounted) {
          return;
        }
        setProvider(config.provider);
        setModel(config.model);
      })
      .catch(console.error)
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    getLLMModels()
      .then((modelResponse) => {
        if (!isMounted) {
          return;
        }

        const apiModels = modelResponse.models;
        if (!apiModels.length) {
          setModels(FALLBACK_MODELS);
          setModelsSource('fallback');
          setModel((current) => current || FALLBACK_MODELS[0]?.id || '');
          return;
        }

        setModels(apiModels);
        setModelsSource('api');
        setModel((current) => current || modelResponse.default_model || apiModels[0]?.id || '');
      })
      .catch((error) => {
        console.error(error);
        if (!isMounted) {
          return;
        }

        setModels(FALLBACK_MODELS);
        setModelsSource('fallback');
        setModel((current) => current || FALLBACK_MODELS[0]?.id || '');
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
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      {/* LLM Configuration */}
      <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">LLM Provider</h2>

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
            <label className="block text-sm text-[var(--muted)] mb-1">Model</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={isLoading}
              className="w-full bg-[var(--background)] border border-[var(--card-border)] rounded px-3 py-2"
            >
              <option value="" disabled>{isLoading ? 'Loading models...' : 'Select an LLM model'}</option>
              {models.map((modelOption) => (
                <option key={modelOption.id} value={modelOption.id}>
                  {modelOption.label} ({modelOption.id})
                </option>
              ))}
              {model && !models.some((modelOption) => modelOption.id === model) ? (
                <option value={model}>{`Current custom model (${model})`}</option>
              ) : null}
            </select>
            <p className="text-xs text-[var(--muted)] mt-1">
              {modelsSource === 'api'
                ? 'Models shown are fetched from the API.'
                : 'Using built-in fallback models because the models endpoint is unavailable.'}
            </p>
          </div>

          <button
            onClick={handleSave}
            disabled={!model || isSaving || isLoading}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-800/50 disabled:cursor-not-allowed rounded text-sm font-medium transition-colors"
          >
            {isSaving ? 'Saving...' : saved ? '✓ Saved' : 'Save'}
          </button>

          {saveError ? (
            <div className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {saveError}
            </div>
          ) : null}

          {saveWarning ? (
            <div className="rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
              {saveWarning}
            </div>
          ) : null}
        </div>
      </div>

      {/* About */}
      <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-2">About</h2>
        <p className="text-sm text-[var(--muted)]">
          Irish Property Research Dashboard v0.1.0<br />
          Powered by AWS: Lambda, API Gateway, RDS PostgreSQL, Amazon Bedrock,
          SQS, and Amplify. Aggregates property listings from Daft.ie,
          MyHome.ie, PropertyPal, and the Property Price Register.
        </p>
      </div>
    </div>
  );
}
