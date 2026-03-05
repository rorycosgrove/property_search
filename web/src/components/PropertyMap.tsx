'use client';

import { useEffect, useRef } from 'react';
import type { Property } from '@/lib/api';
import { useMapStore, useUIStore } from '@/lib/stores';
import { formatEur } from '@/lib/utils';

interface Props {
  properties: Property[];
}

export default function PropertyMap({ properties }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const { center, zoom, selectedPropertyId, setCenter, setZoom } = useMapStore();
  const { openDetail } = useUIStore();

  useEffect(() => {
    // Dynamic import — Leaflet requires window
    if (typeof window === 'undefined' || !mapRef.current) return;

    import('leaflet').then((L) => {
      if (mapInstanceRef.current) return;

      const map = L.map(mapRef.current!, {
        center: center,
        zoom: zoom,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18,
      }).addTo(map);

      map.on('moveend', () => {
        const c = map.getCenter();
        setCenter([c.lat, c.lng]);
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

  // Update markers when properties change
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    import('leaflet').then((L) => {
      const map = mapInstanceRef.current;

      // Clear existing markers
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      // Add new markers
      properties.forEach((prop) => {
        if (prop.latitude == null || prop.longitude == null) return;

        const isSelected = prop.id === selectedPropertyId;

        const icon = L.divIcon({
          className: 'custom-marker',
          html: `<div style="
            background: ${isSelected ? '#3399ff' : '#1a7af5'};
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
            border: 2px solid ${isSelected ? '#fff' : 'transparent'};
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          ">${formatEur(prop.price)}</div>`,
          iconSize: [0, 0],
          iconAnchor: [40, 20],
        });

        const marker = L.marker([prop.latitude, prop.longitude], { icon })
          .addTo(map)
          .on('click', () => openDetail(prop));

        markersRef.current.push(marker);
      });
    });
  }, [properties, selectedPropertyId]);

  return (
    <div ref={mapRef} className="w-full h-full" />
  );
}
