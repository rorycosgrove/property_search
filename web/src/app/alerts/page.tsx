'use client';

import { useEffect, useState } from 'react';
import { getAlerts, acknowledgeAlert, acknowledgeAllAlerts, getUnreadAlertCount, type Alert } from '@/lib/api';
import { formatDate } from '@/lib/utils';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filter, setFilter] = useState<string>('');
  const [page, setPage] = useState(1);

  const loadAlerts = async () => {
    const params: Record<string, any> = { page, size: 30 };
    if (filter) params.alert_type = filter;
    const data = await getAlerts(params);
    setAlerts(data.items);
    setTotal(data.total);
    const unread = await getUnreadAlertCount();
    setUnreadCount(unread.count);
  };

  useEffect(() => {
    loadAlerts();
  }, [filter, page]);

  const handleAcknowledge = async (id: string) => {
    await acknowledgeAlert(id);
    loadAlerts();
  };

  const handleAckAll = async () => {
    await acknowledgeAllAlerts();
    loadAlerts();
  };

  const severityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-400';
      case 'high': return 'text-orange-400';
      case 'medium': return 'text-yellow-400';
      default: return 'text-[var(--muted)]';
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Alerts</h1>
          {unreadCount > 0 && (
            <p className="text-sm text-brand-400">{unreadCount} unread</p>
          )}
        </div>
        <div className="flex gap-2">
          <select
            value={filter}
            onChange={(e) => { setFilter(e.target.value); setPage(1); }}
            className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1.5 text-sm"
          >
            <option value="">All Types</option>
            <option value="new_listing">New Listing</option>
            <option value="price_drop">Price Drop</option>
            <option value="price_increase">Price Increase</option>
            <option value="sale_agreed">Sale Agreed</option>
            <option value="back_on_market">Back on Market</option>
          </select>
          <button
            onClick={handleAckAll}
            className="px-3 py-1.5 text-sm bg-brand-600 hover:bg-brand-700 rounded transition-colors"
          >
            Mark All Read
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className={`bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4 flex items-start gap-3 ${
              !alert.acknowledged ? 'border-l-2 border-l-brand-500' : ''
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
                className="text-xs px-2 py-1 border border-[var(--card-border)] rounded hover:bg-[var(--card-border)] transition-colors"
              >
                Dismiss
              </button>
            )}
          </div>
        ))}

        {alerts.length === 0 && (
          <p className="text-center py-12 text-[var(--muted)]">No alerts</p>
        )}
      </div>
    </div>
  );
}
