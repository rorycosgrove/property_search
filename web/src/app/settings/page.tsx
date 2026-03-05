'use client';

import { useEffect, useState } from 'react';
import { getLLMConfig, updateLLMConfig } from '@/lib/api';

export default function SettingsPage() {
  const [provider, setProvider] = useState('ollama');
  const [model, setModel] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getLLMConfig().then((config) => {
      setProvider(config.provider);
      setModel(config.model);
    }).catch(console.error);
  }, []);

  const handleSave = async () => {
    await updateLLMConfig(provider, model || undefined);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
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
              <option value="ollama">Ollama (Local)</option>
              <option value="openai">OpenAI (Cloud)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-[var(--muted)] mb-1">Model</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={provider === 'ollama' ? 'llama3.1:8b' : 'gpt-4o-mini'}
              className="w-full bg-[var(--background)] border border-[var(--card-border)] rounded px-3 py-2"
            />
            <p className="text-xs text-[var(--muted)] mt-1">
              {provider === 'ollama'
                ? 'Run `ollama pull llama3.1:8b` to download the model'
                : 'Set OPENAI_API_KEY in .env to use OpenAI'}
            </p>
          </div>

          <button
            onClick={handleSave}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-700 rounded text-sm font-medium transition-colors"
          >
            {saved ? '✓ Saved' : 'Save'}
          </button>
        </div>
      </div>

      {/* About */}
      <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-2">About</h2>
        <p className="text-sm text-[var(--muted)]">
          Irish Property Research Dashboard v0.1.0<br />
          Aggregates property listings from Daft.ie, MyHome.ie, PropertyPal,
          and the Property Price Register. Provides map visualization,
          price tracking, alerts, and AI-powered insights.
        </p>
      </div>
    </div>
  );
}
