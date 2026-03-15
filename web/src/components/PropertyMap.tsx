'use client';

import { useEffect, useRef } from 'react';
import type { DivIcon, Map as LeafletMap, Marker as LeafletMarker } from 'leaflet';
import type { Property } from '@/lib/api';
import { useMapStore, useUIStore } from '@/lib/stores';
import { formatEur } from '@/lib/utils';

interface Props {
  properties: Property[];
}

function _asValidCoord(value: unknown, min: number, max: number): number | null {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  if (numeric < min || numeric > max) {
    return null;
  }
  return numeric;
}

function _propertyLatLng(prop: Property): [number, number] | null {
  const lat = _asValidCoord(prop.latitude, -90, 90);
  const lng = _asValidCoord(prop.longitude, -180, 180);
  if (lat == null || lng == null) {
    return null;
  }
  return [lat, lng];
}

function _isFiniteLatLng(value: [number, number] | null): value is [number, number] {
  return !!value && Number.isFinite(value[0]) && Number.isFinite(value[1]);
}

function _safeFlyTo(map: LeafletMap, latLng: [number, number] | null, requestedZoom: number): void {
  if (!_isFiniteLatLng(latLng)) {
    return;
  }

  const zoom = Number.isFinite(requestedZoom) ? requestedZoom : 13;
  try {
    map.flyTo(latLng, zoom, {
      animate: true,
      duration: 0.7,
    });
  } catch {
    // Prevent map runtime crashes from malformed coordinates in incoming data.
  }
}

function _escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function _hoverCardHtml(prop: Property): string {
  const imageUrl = prop.images?.[0]?.url;
  const title = _escapeHtml(prop.title || 'Property');
  const address = _escapeHtml(prop.address || 'Address unavailable');
  const ber = _escapeHtml(prop.ber_rating || 'n/a');
  const score = prop.llm_value_score != null ? prop.llm_value_score.toFixed(1) : 'n/a';
  const beds = prop.bedrooms != null ? `${prop.bedrooms} bed` : '-';
  const baths = prop.bathrooms != null ? `${prop.bathrooms} bath` : '-';
  const area = prop.floor_area_sqm != null ? `${prop.floor_area_sqm} m2` : '-';

  return `
    <div class="marker-hover-card-content">
      <div class="marker-hover-card-media">${
        imageUrl
          ? `<img src="${_escapeHtml(imageUrl)}" alt="${title}" />`
          : '<div class="marker-hover-card-fallback">No image</div>'
      }</div>
      <div class="marker-hover-card-body">
        <div class="marker-hover-card-price">${_escapeHtml(formatEur(prop.price))}</div>
        <div class="marker-hover-card-address">${address}</div>
        <div class="marker-hover-card-meta">${beds} | ${baths} | ${area}</div>
        <div class="marker-hover-card-meta">BER ${ber} | Value ${score}/10</div>
      </div>
    </div>
  `;
}

export default function PropertyMap({ properties }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef<Array<{ id: string; marker: LeafletMarker }>>([]);
  const { center, zoom, selectedPropertyId, setCenter, setZoom, selectProperty } = useMapStore();
  const { openDetail } = useUIStore();

  useEffect(() => {
    // Dynamic import — Leaflet requires window
    if (typeof window === 'undefined' || !mapRef.current) return;

    import('leaflet').then((L) => {
      if (mapInstanceRef.current) return;

      const safeCenter: [number, number] = [
        _asValidCoord(center[0], -90, 90) ?? 53.35,
        _asValidCoord(center[1], -180, 180) ?? -6.26,
      ];

      const map = L.map(mapRef.current!, {
        center: safeCenter,
        zoom: zoom,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18,
      }).addTo(map);

      map.on('moveend', () => {
        const c = map.getCenter();
        const nextLat = _asValidCoord(c.lat, -90, 90);
        const nextLng = _asValidCoord(c.lng, -180, 180);
        if (nextLat != null && nextLng != null) {
          setCenter([nextLat, nextLng]);
        }
        setZoom(map.getZoom());
      });

      mapInstanceRef.current = map;
    });

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Focus map when a property is selected from map/list interactions.
  useEffect(() => {
    if (!mapInstanceRef.current || !selectedPropertyId) return;

    const map = mapInstanceRef.current;
    const selectedMarker = markersRef.current.find((entry) => entry.id === selectedPropertyId);
    if (selectedMarker) {
      const ll = selectedMarker.marker.getLatLng();
      const latLng: [number, number] = [ll.lat, ll.lng];
      const targetZoom = Math.max(map.getZoom(), 13);
      _safeFlyTo(map, latLng, targetZoom);
      selectedMarker.marker.openPopup();
    }
  }, [selectedPropertyId]);

  // Update markers when properties change
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    import('leaflet').then((L) => {
      const map = mapInstanceRef.current;
      if (!map) {
        return;
      }

      // Clear existing markers
      markersRef.current.forEach(({ marker }) => marker.remove());
      markersRef.current = [];

      // Add new markers
      properties.forEach((prop) => {
        const latLng = _propertyLatLng(prop);
        if (!latLng) return;

        const isSelected = prop.id === selectedPropertyId;

        const icon: DivIcon = L.divIcon({
          className: 'custom-marker-wrapper',
          html: `<div class="property-marker-badge ${isSelected ? 'is-selected' : ''}">${formatEur(prop.price)}</div>`,
          iconSize: [96, 28],
          iconAnchor: [48, 14],
        });

        const marker = L.marker(latLng, { icon })
          .bindTooltip(_hoverCardHtml(prop), {
            className: 'marker-hover-card',
            direction: 'top',
            offset: [0, -16],
            opacity: 1,
            sticky: true,
          })
          .bindPopup(_hoverCardHtml(prop), {
            className: 'marker-hover-card marker-hover-card-popup',
            closeButton: false,
            autoPan: true,
            offset: [0, -10],
          })
          .addTo(map);

        marker.on('mouseover', () => {
          marker.openTooltip();
        });

        marker.on('mouseout', () => {
          marker.closeTooltip();
        });

        marker.on('click', () => {
          const targetZoom = Math.max(map.getZoom(), 13);
          const ll = marker.getLatLng();
          _safeFlyTo(map, [ll.lat, ll.lng], targetZoom);
          marker.openPopup();
          selectProperty(prop.id);
          openDetail(prop);
        });

        if (isSelected) {
          const targetZoom = Math.max(map.getZoom(), 13);
          const ll = marker.getLatLng();
          _safeFlyTo(map, [ll.lat, ll.lng], targetZoom);
          marker.openPopup();
        }

        markersRef.current.push({ id: prop.id, marker });
      });
    });
  }, [properties, selectedPropertyId]);

  return (
    <div ref={mapRef} className="w-full h-full" />
  );
}
