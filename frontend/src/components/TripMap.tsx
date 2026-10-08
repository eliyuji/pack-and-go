"use client";

import { useEffect } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { withCoords } from "@/lib/trip";
import type { FoodOption } from "@/lib/types";

function numberedIcon(n: number, kind?: string) {
  return L.divIcon({
    className: kind === "food" ? "pg-pin food" : "pg-pin",
    html: `<span>${kind === "food" ? "F" : n}</span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function FitAndResize({ points }: { points: [number, number][] }) {
  const map = useMap();
  const key = points.map((p) => p.join(",")).join("|");

  useEffect(() => {
    const resize = () => map.invalidateSize();
    resize();
    const t = window.setTimeout(resize, 80);
    window.addEventListener("resize", resize);
    if (points.length === 1) map.setView(points[0], 13);
    else if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), { padding: [28, 28] });
    }
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("resize", resize);
    };
  }, [map, key]);

  return null;
}

export default function TripMap({
  pins,
  fallback,
}: {
  pins: FoodOption[];
  fallback?: [number, number] | null;
}) {
  const located = pins.map(withCoords).filter((p): p is FoodOption => p != null);
  const points = located.map((p) => [Number(p.lat), Number(p.lon)] as [number, number]);
  const center = points[0] || fallback;

  if (!center) {
    return (
      <div className="empty-map">
        No coordinates for this day yet. Generate a trip in Taipei, Tainan,
        Taichung, or the Peninsula.
      </div>
    );
  }

  return (
    <MapContainer
      center={center}
      zoom={13}
      className="trip-map"
      scrollWheelZoom
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitAndResize points={points.length ? points : [center]} />
      {located.filter((p) => p.kind !== "food").length > 1 && (
        <Polyline
          positions={located
            .filter((p) => p.kind !== "food")
            .map((p) => [Number(p.lat), Number(p.lon)] as [number, number])}
          pathOptions={{ color: "#7c3aed", weight: 3 }}
        />
      )}
      {located.map((pin, i) => (
        <Marker
          key={`${pin.name}-${i}`}
          position={[Number(pin.lat), Number(pin.lon)]}
          icon={numberedIcon(i + 1, pin.kind)}
        >
          <Popup>
            <strong>{pin.name}</strong>
            {pin.district ? <div>{pin.district}</div> : null}
            {pin.maps_url ? (
              <a href={pin.maps_url} target="_blank" rel="noreferrer">
                Open in Google Maps
              </a>
            ) : null}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
