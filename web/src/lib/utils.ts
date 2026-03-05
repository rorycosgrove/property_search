/**
 * Shared utility functions.
 */

/** Format a number as Euro currency */
export function formatEur(value: number | null | undefined): string {
  if (value == null) return 'POA';
  return new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value);
}

/** Format a date string */
export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('en-IE', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/** BER rating color mapping */
export function berColor(rating: string | null | undefined): string {
  if (!rating) return '#999';
  const r = rating.toUpperCase();
  if (r.startsWith('A')) return '#00A651';
  if (r.startsWith('B')) return '#8CC63F';
  if (r.startsWith('C')) return '#FFF200';
  if (r.startsWith('D')) return '#F7941D';
  if (r.startsWith('E')) return '#ED1C24';
  if (r === 'F') return '#BE1E2D';
  if (r === 'G') return '#7F1416';
  return '#999';
}

/** Irish county list for dropdowns */
export const COUNTIES = [
  'Carlow', 'Cavan', 'Clare', 'Cork', 'Donegal', 'Dublin',
  'Galway', 'Kerry', 'Kildare', 'Kilkenny', 'Laois', 'Leitrim',
  'Limerick', 'Longford', 'Louth', 'Mayo', 'Meath', 'Monaghan',
  'Offaly', 'Roscommon', 'Sligo', 'Tipperary', 'Waterford',
  'Westmeath', 'Wexford', 'Wicklow',
];

/** Truncate text to max length */
export function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen - 1) + '…';
}

/** Debounce function */
export function debounce<T extends (...args: any[]) => void>(fn: T, ms: number): T {
  let timer: NodeJS.Timeout;
  return ((...args: any[]) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  }) as T;
}
