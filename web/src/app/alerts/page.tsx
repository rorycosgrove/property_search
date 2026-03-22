'use client';

import { useEffect, useState } from 'react';
import {
  getAlerts,
  acknowledgeAlert,
  acknowledgeAllAlerts,
  getUnreadAlertCount,
  getAlertStats,
  type Alert,
  type AlertStats,
} from '@/lib/api';
import { formatDate } from '@/lib/utils';
import { LoadingCardGrid, LoadingRows } from '@/components/LoadingState';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [stats, setStats] = useState<AlertStats | null>(null);
  const [filter, setFilter] = useState<string>('');
  const [showAcknowledged, setShowAcknowledged] = useState<boolean>(false);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAlerts = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | boolean | undefined> = {
        page,
        size: 30,
        acknowledged: showAcknowledged ? undefined : false,
      };
      if (filter) params.alert_type = filter;

      const [data, unread, summary] = await Promise.all([
        getAlerts(params),
        getUnreadAlertCount(),
        getAlertStats(),
      ]);

      setAlerts(data.items);
      setTotal(data.total);
      setUnreadCount(unread.count);
      setStats(summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAlerts();
  }, [filter, page, showAcknowledged]);

  const handleAcknowledge = async (id: string) => {
    await acknowledgeAlert(id);
    void loadAlerts();
  };

  const handleAckAll = async () => {
    await acknowledgeAllAlerts();
    void loadAlerts();
  };

  const severityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'text-red-500';
      case 'high':
        return 'text-orange-500';
      case 'medium':
        return 'text-amber-600';
      default: return 'text-[var(--muted)]';
    }
  };

  return (
    <div className="page-shell page-shell-regular rise-in">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Action Queue</p>
          <h1 className="text-2xl lg:text-3xl font-bold">Market alerts and AI priorities</h1>
          {unreadCount > 0 && (
            <p className="text-sm text-[var(--accent)]">{unreadCount} unread alerts need review</p>
          )}
        </div>
        <div className="flex w-full flex-wrap gap-2 lg:w-auto">
          <select
            value={filter}
            onChange={(e) => { setFilter(e.target.value); setPage(1); }}
            className="ui-select"
          >
            <option value="">All Types</option>
            <option value="new_listing">New Listing</option>
            <option value="price_drop">Price Drop</option>
            <option value="price_increase">Price Increase</option>
            <option value="sale_agreed">Sale Agreed</option>
            <option value="back_on_market">Back on Market</option>
          </select>
          <button
            onClick={() => {
              setShowAcknowledged((v) => !v);
              setPage(1);
            }}
            className="ui-btn ui-btn-secondary"
          >
            {showAcknowledged ? 'Hide read' : 'Include read'}
          </button>
          <button
            onClick={handleAckAll}
            className="ui-btn ui-btn-primary"
          >
            Mark All Read
          </button>
        </div>
      </div>

      <div className="page-hero ai-glass mb-4 text-sm">
        Atlas tip: handle critical price-drop and back-on-market alerts first, then queue a compare analysis against your current shortlist.
      </div>

      {stats && (
        <section className="mb-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
          <div className="soft-card rounded-2xl p-3">
            <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">Open now</p>
            <p className="mt-1 text-xl font-semibold">{stats.total_unacknowledged}</p>
          </div>
          {stats.by_type.slice(0, 4).map((item) => (
            <div key={item.type} className="soft-card rounded-2xl p-3">
              <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">{item.type.replace(/_/g, ' ')}</p>
              <p className="mt-1 text-base font-semibold">{item.unacknowledged} open</p>
              <p className="text-xs text-[var(--muted)]">{item.total} total</p>
            </div>
          ))}
        </section>
      )}

      {loading && !stats ? (
        <section className="mb-5">
          <LoadingCardGrid cards={5} />
        </section>
      ) : null}

      {error && (
        <div className="mb-4 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)]">
          {error}
        </div>
      )}

      <div className="space-y-2">
        {loading && alerts.length === 0 ? <LoadingRows rows={6} /> : null}

        {loading && alerts.length > 0 ? (
          <p className="text-sm text-[var(--muted)]">Refreshing alerts...</p>
        ) : null}

        {alerts.map((alert) => (
          <div
            key={alert.id}
            className={`bg-[var(--card-bg)] border border-[var(--card-border)] rounded-xl p-4 flex items-start gap-3 ${
              !alert.acknowledged ? 'border-l-2 border-l-[var(--accent)]' : ''
            }`}
          >
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs font-semibold uppercase ${severityColor(alert.severity)}`}>
                  {alert.severity}
                </span>
                <span className="text-xs text-[var(--muted)] capitalize">
                  {alert.alert_type.replace(/_/g, ' ')}
                </span>
              </div>
              <h3 className="text-sm font-medium">{alert.title}</h3>
              <p className="text-xs text-[var(--muted)] mt-0.5">{formatDate(alert.created_at)}</p>
            </div>
            {!alert.acknowledged && (
              <button
                onClick={() => handleAcknowledge(alert.id)}
                className="ui-btn ui-btn-secondary text-xs"
              >
                Dismiss
              </button>
            )}
          </div>
        ))}

        {!loading && alerts.length === 0 && (
          <p className="text-center py-12 text-[var(--muted)]">No alerts</p>
        )}
      </div>

      <div className="mt-5 flex items-center justify-between text-xs text-[var(--muted)]">
        <p>{total} alerts in this view</p>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="ui-btn ui-btn-secondary text-xs disabled:opacity-40"
          >
            Prev
          </button>
          <span className="self-center">Page {page}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={alerts.length < 30}
            className="ui-btn ui-btn-secondary text-xs disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
