'use client';

import { useEffect, useMemo, useState, type FormEvent } from 'react';
import {
  createSavedSearch,
  deleteSavedSearch,
  getSavedSearches,
  type NotifyMethod,
  type SavedSearch,
  updateSavedSearch,
} from '@/lib/api';
import { COUNTIES, formatDate } from '@/lib/utils';
import { LoadingRows } from '@/components/LoadingState';

const PROPERTY_TYPE_OPTIONS = ['house', 'apartment', 'duplex', 'bungalow', 'site'];

type FormState = {
  id: string | null;
  name: string;
  county: string;
  minPrice: string;
  maxPrice: string;
  minBedrooms: string;
  keywords: string;
  notifyNew: boolean;
  notifyDrops: boolean;
  notifyMethod: NotifyMethod;
  email: string;
  isActive: boolean;
};

const EMPTY_FORM: FormState = {
  id: null,
  name: '',
  county: '',
  minPrice: '',
  maxPrice: '',
  minBedrooms: '',
  keywords: '',
  notifyNew: true,
  notifyDrops: true,
  notifyMethod: 'in_app',
  email: '',
  isActive: true,
};

export default function SavedSearchesPage() {
  const [items, setItems] = useState<SavedSearch[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSavedSearches();
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load saved searches');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      if (a.is_active !== b.is_active) {
        return a.is_active ? -1 : 1;
      }
      const at = new Date(a.updated_at || a.created_at || 0).getTime();
      const bt = new Date(b.updated_at || b.created_at || 0).getTime();
      return bt - at;
    });
  }, [items]);

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 2200);
  };

  const buildPayload = () => {
    const keywordList = form.keywords
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean);

    return {
      name: form.name.trim(),
      criteria: {
        counties: form.county ? [form.county] : undefined,
        min_price: form.minPrice ? Number(form.minPrice) : undefined,
        max_price: form.maxPrice ? Number(form.maxPrice) : undefined,
        min_bedrooms: form.minBedrooms ? Number(form.minBedrooms) : undefined,
        keywords: keywordList.length > 0 ? keywordList : undefined,
        property_types: PROPERTY_TYPE_OPTIONS,
      },
      notify_new_listings: form.notifyNew,
      notify_price_drops: form.notifyDrops,
      notify_method: form.notifyMethod,
      email: form.email.trim() || undefined,
    };
  };

  const validateForm = (): string | null => {
    if (!form.name.trim()) {
      return 'Name is required.';
    }
    if (form.notifyMethod !== 'in_app' && !form.email.trim()) {
      return 'Email is required for email notifications.';
    }
    return null;
  };

  const resetForm = () => {
    setForm(EMPTY_FORM);
    setError(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const validation = validateForm();
    if (validation) {
      setError(validation);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      if (form.id) {
        await updateSavedSearch(form.id, {
          ...buildPayload(),
          is_active: form.isActive,
        });
        showToast('Saved search updated.');
      } else {
        await createSavedSearch(buildPayload());
        showToast('Saved search created.');
      }
      resetForm();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save search');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (item: SavedSearch) => {
    setForm({
      id: item.id,
      name: item.name,
      county: item.criteria.counties?.[0] || '',
      minPrice: item.criteria.min_price != null ? String(item.criteria.min_price) : '',
      maxPrice: item.criteria.max_price != null ? String(item.criteria.max_price) : '',
      minBedrooms: item.criteria.min_bedrooms != null ? String(item.criteria.min_bedrooms) : '',
      keywords: item.criteria.keywords?.join(', ') || '',
      notifyNew: item.notify_new_listings,
      notifyDrops: item.notify_price_drops,
      notifyMethod: item.notify_method,
      email: item.email || '',
      isActive: item.is_active,
    });
    setError(null);
  };

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await deleteSavedSearch(id);
      if (form.id === id) {
        resetForm();
      }
      showToast('Saved search deleted.');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete search');
    }
  };

  const handleToggleActive = async (item: SavedSearch) => {
    setError(null);
    try {
      await updateSavedSearch(item.id, { is_active: !item.is_active });
      showToast(item.is_active ? 'Search paused.' : 'Search activated.');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update status');
    }
  };

  return (
    <div className="page-shell page-shell-wide rise-in">
      <section className="page-hero">
        <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Automation</p>
        <h1 className="mt-2 text-3xl lg:text-4xl">Saved Searches</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)] lg:text-base">
          Configure recurring search criteria and notification channels. This route directly manages
          the saved-search API endpoints for create, update, pause, and delete actions.
        </p>
      </section>

      {toast ? (
        <div className="mt-4 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-2 text-sm text-[var(--foreground)]">
          {toast}
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 rounded-lg border border-[var(--danger)]/35 bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)]">
          {error}
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <section className="page-section-card">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-xl">{form.id ? 'Edit saved search' : 'Create saved search'}</h2>
            {form.id ? (
              <button type="button" onClick={resetForm} className="ui-btn ui-btn-secondary text-sm">
                New search
              </button>
            ) : null}
          </div>

          <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-3">
            <input
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="Name (for example: Dublin family homes under 600k)"
              className="ui-input"
            />

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <select
                value={form.county}
                onChange={(e) => setForm((prev) => ({ ...prev, county: e.target.value }))}
                className="ui-select"
              >
                <option value="">Any county</option>
                {COUNTIES.map((county) => (
                  <option key={county} value={county}>{county}</option>
                ))}
              </select>
              <input
                type="number"
                value={form.minPrice}
                onChange={(e) => setForm((prev) => ({ ...prev, minPrice: e.target.value }))}
                placeholder="Min price"
                className="ui-input"
              />
              <input
                type="number"
                value={form.maxPrice}
                onChange={(e) => setForm((prev) => ({ ...prev, maxPrice: e.target.value }))}
                placeholder="Max price"
                className="ui-input"
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <input
                type="number"
                value={form.minBedrooms}
                onChange={(e) => setForm((prev) => ({ ...prev, minBedrooms: e.target.value }))}
                placeholder="Minimum bedrooms"
                className="ui-input"
              />
              <input
                value={form.keywords}
                onChange={(e) => setForm((prev) => ({ ...prev, keywords: e.target.value }))}
                placeholder="Keywords (comma separated)"
                className="ui-input"
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="flex items-center gap-2 rounded-lg border border-[var(--card-border)] bg-[var(--surface)] px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.notifyNew}
                  onChange={(e) => setForm((prev) => ({ ...prev, notifyNew: e.target.checked }))}
                />
                Notify on new listings
              </label>
              <label className="flex items-center gap-2 rounded-lg border border-[var(--card-border)] bg-[var(--surface)] px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.notifyDrops}
                  onChange={(e) => setForm((prev) => ({ ...prev, notifyDrops: e.target.checked }))}
                />
                Notify on price drops
              </label>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <select
                value={form.notifyMethod}
                onChange={(e) => setForm((prev) => ({ ...prev, notifyMethod: e.target.value as NotifyMethod }))}
                className="ui-select"
              >
                <option value="in_app">In-app only</option>
                <option value="email">Email only</option>
                <option value="both">In-app + email</option>
              </select>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
                placeholder="Notification email"
                className="ui-input"
              />
            </div>

            {form.id ? (
              <label className="flex items-center gap-2 rounded-lg border border-[var(--card-border)] bg-[var(--surface)] px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.isActive}
                  onChange={(e) => setForm((prev) => ({ ...prev, isActive: e.target.checked }))}
                />
                Search is active
              </label>
            ) : null}

            <button type="submit" disabled={saving} className="ui-btn ui-btn-primary disabled:opacity-50">
              {saving ? 'Saving...' : form.id ? 'Update search' : 'Create search'}
            </button>
          </form>
        </section>

        <section className="page-section-card">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-xl">Existing saved searches</h2>
            <span className="rounded-full border border-[var(--card-border)] px-2.5 py-1 text-xs text-[var(--muted)]">
              {items.length} total
            </span>
          </div>

          {loading ? (
            <LoadingRows rows={6} />
          ) : sortedItems.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">No saved searches yet.</p>
          ) : (
            <div className="space-y-3">
              {sortedItems.map((item) => (
                <article key={item.id} className="rounded-lg border border-[var(--card-border)] bg-[var(--surface)] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold">{item.name}</p>
                      <p className="text-xs text-[var(--muted)] mt-0.5">
                        {item.criteria.counties?.join(', ') || 'Any county'}
                        {item.criteria.min_price != null ? ` | min ${item.criteria.min_price}` : ''}
                        {item.criteria.max_price != null ? ` | max ${item.criteria.max_price}` : ''}
                        {item.criteria.min_bedrooms != null ? ` | ${item.criteria.min_bedrooms}+ beds` : ''}
                      </p>
                      <p className="text-xs text-[var(--muted)] mt-0.5">
                        Method: {item.notify_method} | Created: {formatDate(item.created_at)}
                      </p>
                    </div>
                    <span
                      className={[
                        'rounded-full border px-2 py-0.5 text-[11px]',
                        item.is_active
                          ? 'border-emerald-300/50 bg-emerald-200/35 text-emerald-700'
                          : 'border-stone-300/70 bg-stone-100 text-stone-600',
                      ].join(' ')}
                    >
                      {item.is_active ? 'Active' : 'Paused'}
                    </span>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <button type="button" onClick={() => handleEdit(item)} className="ui-btn ui-btn-secondary text-sm">
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleToggleActive(item)}
                      className="ui-btn ui-btn-soft text-sm"
                    >
                      {item.is_active ? 'Pause' : 'Activate'}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDelete(item.id)}
                      className="ui-btn border border-[var(--danger)]/40 bg-[var(--danger)]/10 text-[var(--danger)] text-sm"
                    >
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
