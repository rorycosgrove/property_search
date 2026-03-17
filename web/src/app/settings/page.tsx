'use client';

import { useEffect, useState } from 'react';
import {
  diagnoseListingByExternalId,
  getBackendDiscoveryActivity,
  getBackendFeedActivity,
  getBackendHealthSummary,
  getBackendRecentErrors,
  getBackendSourceStatus,
  getLLMConfig,
  getLLMHealth,
  getLLMModels,
  type BackendDiscoveryActivity,
  type BackendFeedActivity,
  type BackendHealthSummary,
  type BackendLogEntry,
  type BackendSourceStatus,
  type ListingDiagnoseResult,
  type LLMHealth,
  type LLMModelOption,
  repairListingByExternalId,
  updateLLMConfig,
} from '@/lib/api';

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
  const [backendFeedActivity, setBackendFeedActivity] = useState<BackendFeedActivity[]>([]);
  const [backendSourceStatus, setBackendSourceStatus] = useState<BackendSourceStatus[]>([]);
  const [backendDiscoveryActivity, setBackendDiscoveryActivity] = useState<BackendDiscoveryActivity[]>([]);
  const [backendHealth, setBackendHealth] = useState<BackendHealthSummary | null>(null);
  const [backendErrors, setBackendErrors] = useState<BackendLogEntry[]>([]);
  const [backendLogsLoading, setBackendLogsLoading] = useState(true);
  const [backendLogsError, setBackendLogsError] = useState<string | null>(null);
  const [backendLogLevel, setBackendLogLevel] = useState<'ERROR' | 'WARNING' | 'ALL'>('ALL');
  const [diagnosticExternalId, setDiagnosticExternalId] = useState('6437639');
  const [diagnosticListingUrl, setDiagnosticListingUrl] = useState('https://www.daft.ie/for-sale/house-lighthouse-ballydesmond-co-cork/6437639');
  const [diagnosticSimilarIds, setDiagnosticSimilarIds] = useState('6007301,6326209,6450670,5787846');
  const [diagnosticHours, setDiagnosticHours] = useState(168);
  const [diagnosticMaxProbeSources, setDiagnosticMaxProbeSources] = useState(25);
  const [diagnosticProbeMaxPages, setDiagnosticProbeMaxPages] = useState(120);
  const [diagnosticInFlight, setDiagnosticInFlight] = useState<'diagnose' | 'repair' | null>(null);
  const [diagnosticError, setDiagnosticError] = useState<string | null>(null);
  const [diagnosticResult, setDiagnosticResult] = useState<ListingDiagnoseResult | null>(null);

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

  useEffect(() => {
    let mounted = true;

    const loadBackendDiagnostics = async () => {
      try {
        if (mounted) {
          setBackendLogsError(null);
        }

        const selectedLevel = backendLogLevel === 'ALL' ? undefined : backendLogLevel;
        const [feed, sources, discovery, healthSummary, errors] = await Promise.all([
          getBackendFeedActivity(10),
          getBackendSourceStatus(),
          getBackendDiscoveryActivity(5),
          getBackendHealthSummary(),
          getBackendRecentErrors(25, selectedLevel),
        ]);

        if (!mounted) {
          return;
        }

        setBackendFeedActivity(feed);
        setBackendSourceStatus(sources);
        setBackendDiscoveryActivity(discovery);
        setBackendHealth(healthSummary);
        setBackendErrors(errors);
      } catch (error) {
        if (!mounted) {
          return;
        }
        const message = error instanceof Error ? error.message : 'Unable to load backend diagnostics.';
        setBackendLogsError(message);
      } finally {
        if (mounted) {
          setBackendLogsLoading(false);
        }
      }
    };

    void loadBackendDiagnostics();
    const timer = setInterval(loadBackendDiagnostics, 15000);

    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, [backendLogLevel]);

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

  const runListingDiagnostic = async (mode: 'diagnose' | 'repair') => {
    const externalId = diagnosticExternalId.trim();
    if (!externalId) {
      setDiagnosticError('External ID is required.');
      return;
    }

    try {
      setDiagnosticInFlight(mode);
      setDiagnosticError(null);
      const options = {
        adapterName: 'daft',
        hours: diagnosticHours,
        maxProbeSources: diagnosticMaxProbeSources,
        listingUrl: diagnosticListingUrl.trim() || undefined,
        probeMaxPages: diagnosticProbeMaxPages,
        similarIds: diagnosticSimilarIds
          .split(',')
          .map((value) => value.trim())
          .filter((value) => /^\d{4,}$/.test(value)),
      };
      const result = mode === 'diagnose'
        ? await diagnoseListingByExternalId(externalId, options)
        : await repairListingByExternalId(externalId, options);
      setDiagnosticResult(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to run listing diagnostic.';
      setDiagnosticError(message);
    } finally {
      setDiagnosticInFlight(null);
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
                        ? 'border-[var(--accent)] bg-[var(--accent-soft)]'
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

      <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6 space-y-5">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-lg font-semibold">Backend Status</h2>
            <p className="text-sm text-[var(--muted)] mt-1">Live feed refresh, discovery, and ingestion diagnostics.</p>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-[var(--muted)]">Errors</label>
            <select
              value={backendLogLevel}
              onChange={(e) => setBackendLogLevel(e.target.value as 'ERROR' | 'WARNING' | 'ALL')}
              className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1 text-xs"
            >
              <option value="ALL">Warnings + Errors</option>
              <option value="ERROR">Errors only</option>
              <option value="WARNING">Warnings only</option>
            </select>
          </div>
        </div>

        {backendLogsError ? (
          <div className="rounded border border-[var(--danger)]/40 bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)]">
            {backendLogsError}
          </div>
        ) : null}

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <StatusCard label="Scrapes (24h)" value={String(backendHealth?.scrape_runs_24h ?? 0)} tone="neutral" />
          <StatusCard
            label="Geocode Success"
            value={`${backendHealth?.geocode_success_rate?.toFixed(1) ?? '0.0'}%`}
            tone={(backendHealth?.geocode_success_rate ?? 0) >= 80 ? 'ok' : 'warn'}
          />
          <StatusCard
            label="Scrape Queue"
            value={backendHealth?.queue_config.scrape_queue_configured ? 'Configured' : 'Inline mode'}
            tone={backendHealth?.queue_config.scrape_queue_configured ? 'ok' : 'warn'}
          />
          <StatusCard
            label="Recent Error"
            value={backendHealth?.last_error?.event_type || 'None'}
            tone={backendHealth?.last_error?.event_type ? 'warn' : 'ok'}
          />
        </div>

        <section>
          <h3 className="text-sm font-semibold mb-2">Recent Feed Refresh Activity</h3>
          <div className="overflow-auto border border-[var(--card-border)] rounded-md">
            <table className="w-full text-sm">
              <thead className="bg-[var(--background)] text-[var(--muted)]">
                <tr>
                  <th className="text-left px-3 py-2">Source</th>
                  <th className="text-left px-3 py-2">Fetched</th>
                  <th className="text-left px-3 py-2">New</th>
                  <th className="text-left px-3 py-2">Updated</th>
                  <th className="text-left px-3 py-2">Geocode</th>
                  <th className="text-left px-3 py-2">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {backendFeedActivity.map((row) => (
                  <tr key={row.id} className="border-t border-[var(--card-border)]">
                    <td className="px-3 py-2">{row.source_name || row.source_id || 'Unknown'}</td>
                    <td className="px-3 py-2">{row.total_fetched}</td>
                    <td className="px-3 py-2">{row.new}</td>
                    <td className="px-3 py-2">{row.updated}</td>
                    <td className="px-3 py-2">{(row.geocode_success_rate ?? 0).toFixed(1)}%</td>
                    <td className="px-3 py-2 text-[var(--muted)]">{row.timestamp ? new Date(row.timestamp).toLocaleString() : '-'}</td>
                  </tr>
                ))}
                {!backendFeedActivity.length && !backendLogsLoading ? (
                  <tr>
                    <td className="px-3 py-3 text-[var(--muted)]" colSpan={6}>No recent feed refresh activity.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold mb-2">Source Status</h3>
          <div className="flex flex-wrap gap-2">
            {backendSourceStatus.slice(0, 12).map((source) => (
              <span
                key={source.id}
                className={[
                  'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs',
                  source.status === 'active'
                    ? 'border-emerald-300 text-emerald-700'
                    : source.status === 'warning'
                      ? 'border-amber-300 text-amber-700'
                      : 'border-red-300 text-red-700',
                ].join(' ')}
                title={source.last_error || 'No errors'}
              >
                <span>{source.name}</span>
                <span>errors: {source.error_count}</span>
              </span>
            ))}
            {!backendSourceStatus.length && !backendLogsLoading ? (
              <span className="text-sm text-[var(--muted)]">No sources found.</span>
            ) : null}
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold mb-2">Recent Discovery Runs</h3>
          <ul className="space-y-2">
            {backendDiscoveryActivity.map((item) => (
              <li key={item.id} className="rounded border border-[var(--card-border)] px-3 py-2">
                <p className="text-sm font-medium">{item.event_type}</p>
                <p className="text-xs text-[var(--muted)] mt-1">{item.timestamp ? new Date(item.timestamp).toLocaleString() : '-'}</p>
                <p className="text-xs mt-1">{item.message}</p>
              </li>
            ))}
            {!backendDiscoveryActivity.length && !backendLogsLoading ? (
              <li className="text-sm text-[var(--muted)]">No discovery activity logged yet.</li>
            ) : null}
          </ul>
        </section>

        <section>
          <h3 className="text-sm font-semibold mb-2">Recent Errors & Warnings</h3>
          <div className="space-y-2 max-h-72 overflow-auto pr-1">
            {backendErrors.map((entry) => (
              <div key={entry.id} className="rounded border border-[var(--card-border)] px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-[var(--muted)]">
                  {entry.level} · {entry.event_type}
                </p>
                <p className="text-sm mt-1">{entry.message}</p>
                <p className="text-xs text-[var(--muted)] mt-1">{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '-'}</p>
              </div>
            ))}
            {!backendErrors.length && !backendLogsLoading ? (
              <p className="text-sm text-[var(--muted)]">No recent warnings or errors.</p>
            ) : null}
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold mb-2">Missed Listing Diagnostic (Daft)</h3>
          <p className="text-xs text-[var(--muted)] mb-3">
            Diagnose why a listing ID was missed and optionally trigger one-click repair ingestion.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
            <div className="md:col-span-2">
              <label className="block text-xs text-[var(--muted)] mb-1">External ID</label>
              <input
                type="text"
                value={diagnosticExternalId}
                onChange={(e) => setDiagnosticExternalId(e.target.value)}
                className="w-full bg-[var(--background)] border border-[var(--card-border)] rounded px-3 py-2 text-sm"
                placeholder="e.g. 6437639"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-[var(--muted)] mb-1">Listing URL (optional, recommended)</label>
              <input
                type="text"
                value={diagnosticListingUrl}
                onChange={(e) => setDiagnosticListingUrl(e.target.value)}
                className="w-full bg-[var(--background)] border border-[var(--card-border)] rounded px-3 py-2 text-sm"
                placeholder="https://www.daft.ie/for-sale/.../6437639"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-[var(--muted)] mb-1">Similar Listing IDs (optional, comma separated)</label>
              <input
                type="text"
                value={diagnosticSimilarIds}
                onChange={(e) => setDiagnosticSimilarIds(e.target.value)}
                className="w-full bg-[var(--background)] border border-[var(--card-border)] rounded px-3 py-2 text-sm"
                placeholder="6007301,6326209,6450670,5787846"
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--muted)] mb-1">Log Hours</label>
              <input
                type="number"
                min={1}
                max={720}
                value={diagnosticHours}
                onChange={(e) => setDiagnosticHours(Number(e.target.value) || 168)}
                className="w-full bg-[var(--background)] border border-[var(--card-border)] rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--muted)] mb-1">Max Probe Sources</label>
              <input
                type="number"
                min={1}
                max={60}
                value={diagnosticMaxProbeSources}
                onChange={(e) => setDiagnosticMaxProbeSources(Number(e.target.value) || 25)}
                className="w-full bg-[var(--background)] border border-[var(--card-border)] rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--muted)] mb-1">Probe Max Pages</label>
              <input
                type="number"
                min={5}
                max={300}
                value={diagnosticProbeMaxPages}
                onChange={(e) => setDiagnosticProbeMaxPages(Number(e.target.value) || 120)}
                className="w-full bg-[var(--background)] border border-[var(--card-border)] rounded px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2 mb-3">
            <button
              onClick={() => {
                void runListingDiagnostic('diagnose');
              }}
              disabled={diagnosticInFlight !== null}
              className="px-3 py-2 bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)] disabled:opacity-60 disabled:cursor-not-allowed rounded text-sm"
            >
              {diagnosticInFlight === 'diagnose' ? 'Running Diagnose...' : 'Diagnose'}
            </button>
            <button
              onClick={() => {
                void runListingDiagnostic('repair');
              }}
              disabled={diagnosticInFlight !== null}
              className="px-3 py-2 border border-[var(--card-border)] bg-[var(--background)] hover:bg-[var(--card-bg)] disabled:opacity-60 disabled:cursor-not-allowed rounded text-sm"
            >
              {diagnosticInFlight === 'repair' ? 'Running Repair...' : 'Diagnose + Repair'}
            </button>
          </div>

          {diagnosticError ? (
            <div className="rounded border border-[var(--danger)]/40 bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)] mb-3">
              {diagnosticError}
            </div>
          ) : null}

          {diagnosticResult ? (
            <div className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                <StatusCard label="Diagnosis" value={diagnosticResult.diagnosis.status || 'unknown'} tone={diagnosticResult.diagnosis.status === 'repaired' ? 'ok' : 'warn'} />
                <StatusCard label="Probe Match" value={diagnosticResult.probe?.matched ? 'Matched live' : 'No live match'} tone={diagnosticResult.probe?.matched ? 'ok' : 'warn'} />
                <StatusCard label="Persisted Matches" value={String(diagnosticResult.persisted_matches?.length || 0)} tone="neutral" />
                <StatusCard label="URL Matches" value={String(diagnosticResult.persisted_url_matches?.length || 0)} tone="neutral" />
              </div>

              <div className="rounded border border-[var(--card-border)] bg-[var(--background)] px-3 py-2 text-xs text-[var(--muted)]">
                <p>Reason: {diagnosticResult.diagnosis.reason || 'n/a'}</p>
                <p className="mt-1">Recommended action: {diagnosticResult.diagnosis.recommended_action || 'n/a'}</p>
                <p className="mt-1">Repair status: {diagnosticResult.repair?.status || 'n/a'}</p>
              </div>

              <details className="rounded border border-[var(--card-border)] bg-[var(--background)]">
                <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium">Raw diagnostic payload</summary>
                <pre className="px-3 pb-3 text-xs whitespace-pre-wrap break-words text-[var(--muted)]">
                  {JSON.stringify(diagnosticResult, null, 2)}
                </pre>
              </details>
            </div>
          ) : null}
        </section>
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
