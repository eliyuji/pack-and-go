import type { StructuredItinerary, TripResponse } from "./types";

const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

const GENERATE_MS = 120_000;

async function postJson<T>(path: string, body: unknown, timeoutMs: number): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BACKEND}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("The API timed out. Keep uvicorn on :8000 and try again.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail || body.error || res.statusText;
  } catch {
    return res.statusText || "Request failed";
  }
}

export async function generateTrip(query: string): Promise<TripResponse> {
  return postJson<TripResponse>("/itinerary/v2", { query }, GENERATE_MS);
}

export async function refineTrip(
  query: string,
  feedback: string,
  current: StructuredItinerary,
): Promise<TripResponse> {
  return postJson<TripResponse>(
    "/itinerary/refine",
    { query, feedback, current_itinerary: current },
    GENERATE_MS,
  );
}

export async function hydrateTrip(
  current: StructuredItinerary,
): Promise<StructuredItinerary> {
  const data = await postJson<{ structured?: StructuredItinerary }>(
    "/places/hydrate",
    { current_itinerary: current },
    60_000,
  );
  return data.structured || current;
}

export async function apiHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
