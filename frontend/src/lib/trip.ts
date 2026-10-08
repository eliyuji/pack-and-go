import type { Activity, DayPlan, FoodOption, StructuredItinerary } from "./types";

const SLOT_CLOCK: Record<string, string> = {
  morning: "08:00",
  afternoon: "13:00",
  evening: "18:00",
  night: "18:00",
};

const SLOT_HOURS: Record<string, string> = {
  morning: "2–3 hrs",
  afternoon: "2–3 hrs",
  evening: "2 hrs",
  night: "2 hrs",
};

export function slotKey(time?: string): string {
  return (time || "").trim().toLowerCase();
}

export function clockFor(
  time?: string,
  clocks?: Partial<Record<string, string>>,
): string {
  const key = slotKey(time);
  return clocks?.[key] || SLOT_CLOCK[key] || "12:00";
}

export function durationFor(time?: string): string {
  return SLOT_HOURS[slotKey(time)] || "1–2 hrs";
}

export function sortedDays(structured?: StructuredItinerary): DayPlan[] {
  return [...(structured?.itinerary || [])].sort(
    (a, b) => Number(a.day || 0) - Number(b.day || 0),
  );
}

export function sortedActivities(day?: DayPlan): Activity[] {
  const order = { morning: 0, afternoon: 1, evening: 2, night: 3 };
  return [...(day?.activities || [])].sort(
    (a, b) =>
      (order[slotKey(a.time) as keyof typeof order] ?? 9) -
      (order[slotKey(b.time) as keyof typeof order] ?? 9),
  );
}

export function titleFromQuery(query: string): string {
  const cleaned = query.trim().replace(/\s+/g, " ");
  if (!cleaned) return "Your trip";
  return cleaned.replace(/^./, (c) => c.toUpperCase());
}

export function tagsFromQuery(query: string): string[] {
  const q = query.toLowerCase();
  const tags: string[] = [];
  const days = q.match(/(\d+)\s*-?\s*day/);
  if (days) tags.push(`${days[1]} days`);
  for (const word of [
    "tainan",
    "taipei",
    "taichung",
    "peninsula",
    "palo alto",
    "food",
    "parks",
    "culture",
    "nightlife",
  ]) {
    if (q.includes(word)) tags.push(word.replace(/\b\w/g, (c) => c.toUpperCase()));
  }
  return tags.slice(0, 5);
}

const CITY_CENTER: Record<string, [number, number]> = {
  tainan: [22.9997, 120.227],
  taipei: [25.033, 121.5654],
  taichung: [24.1477, 120.6736],
  peninsula: [37.4419, -122.143],
  "palo alto": [37.4419, -122.143],
  fremont: [37.5483, -121.9886],
  "bay area": [37.4419, -122.143],
};

export function fallbackCenter(query: string): [number, number] | null {
  const q = query.toLowerCase();
  for (const [name, center] of Object.entries(CITY_CENTER)) {
    if (q.includes(name)) return center;
  }
  return null;
}

export function heroImage(query: string): string {
  const q = query.toLowerCase();
  if (q.includes("tainan")) {
    return "https://images.unsplash.com/photo-1590077428593-a55bb267af97?auto=format&fit=crop&w=1600&q=80";
  }
  if (q.includes("taipei")) {
    return "https://images.unsplash.com/photo-1470004914212-05527e49370b?auto=format&fit=crop&w=1600&q=80";
  }
  if (q.includes("taichung")) {
    return "https://images.unsplash.com/photo-1598935892638-0d6660d0c0c0?auto=format&fit=crop&w=1600&q=80";
  }
  if (
    q.includes("peninsula") ||
    q.includes("palo alto") ||
    q.includes("fremont") ||
    q.includes("bay area")
  ) {
    return "https://images.unsplash.com/photo-1501594907352-04cda38ebc29?auto=format&fit=crop&w=1600&q=80";
  }
  return "https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=1600&q=80";
}

function asCoord(value: unknown): number | null {
  if (value == null || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export function withCoords(place?: FoodOption | null): FoodOption | null {
  if (!place) return null;
  const lat = asCoord(place.lat);
  const lon = asCoord(place.lon);
  if (lat == null || lon == null) return null;
  return { ...place, lat, lon };
}

export function mapsLink(place?: FoodOption | null, fallbackName?: string): string | undefined {
  if (place?.maps_url) return place.maps_url;
  const name = place?.name || fallbackName;
  if (!name && !place?.place_id) return undefined;
  const query = encodeURIComponent(name || "");
  let url = `https://www.google.com/maps/search/?api=1&query=${query}`;
  if (place?.place_id) {
    url += `&query_place_id=${encodeURIComponent(place.place_id)}`;
  }
  return url;
}

export function sourceLinks(sources?: string[]): { id: string; url: string }[] {
  const seen = new Set<string>();
  const links: { id: string; url: string }[] = [];
  for (const raw of sources || []) {
    const trimmed = String(raw || "").trim();
    if (!trimmed) continue;
    if (/^https?:\/\//i.test(trimmed)) {
      const id = trimmed.replace(/^https?:\/\/(www\.)?youtube\.com\/watch\?v=/i, "");
      if (seen.has(trimmed)) continue;
      seen.add(trimmed);
      links.push({ id: id.slice(0, 18), url: trimmed });
      continue;
    }
    const id = trimmed.replace(/\.txt$/i, "").split("/").pop() || trimmed;
    if (!id || seen.has(id)) continue;
    seen.add(id);
    links.push({ id, url: `https://www.youtube.com/watch?v=${id}` });
  }
  return links.slice(0, 8);
}

export function shortAddress(address?: string): string {
  if (!address) return "";
  const first = address.split(",")[0]?.trim() || address.trim();
  return first.length > 42 ? `${first.slice(0, 40)}…` : first;
}

export function sameDistrict(food?: FoodOption | null, stop?: FoodOption | null): boolean {
  const a = (food?.district || "").trim().toLowerCase();
  const b = (stop?.district || "").trim().toLowerCase();
  return Boolean(a && b && a === b);
}

export function activityPins(activities: Activity[]): FoodOption[] {
  const pins: FoodOption[] = [];
  for (const activity of activities) {
    const place = typeof activity.place === "object" ? activity.place : undefined;
    const stop = withCoords(place);
    if (stop) {
      pins.push({ ...stop, name: activity.activity || stop.name, kind: "stop" });
    }
    for (const option of activity.food_options || []) {
      const food = withCoords(option);
      if (food) pins.push({ ...food, kind: "food" });
    }
  }
  return pins;
}

export function highlights(structured?: StructuredItinerary): string[] {
  const days = sortedDays(structured);
  const items: string[] = [];
  for (const day of days) {
    for (const act of sortedActivities(day)) {
      if (act.activity) items.push(act.activity);
    }
  }
  return items.slice(0, 4);
}

export function localTips(structured?: StructuredItinerary): string[] {
  const districts = new Set<string>();
  for (const day of sortedDays(structured)) {
    for (const act of day.activities || []) {
      for (const option of act.food_options || []) {
        if (option.district) districts.add(option.district);
      }
    }
  }
  const named = [...districts].slice(0, 4);
  if (!named.length) {
    return [
      "Eat where the day already is — the food list prefers that district.",
      "Refine one slot at a time from chat so the rest of the trip stays put.",
    ];
  }
  return [
    `Food pins cluster in ${named.join(", ")}.`,
    "Open a Maps link on your phone for walking directions.",
    "If a slot feels touristy, ask chat to swap just that time.",
  ];
}
