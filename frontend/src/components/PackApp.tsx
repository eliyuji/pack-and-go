"use client";

import dynamic from "next/dynamic";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { apiHealth, generateTrip, hydrateTrip, refineTrip } from "@/lib/api";
import {
  activityPins,
  clockFor,
  fallbackCenter,
  durationFor,
  heroImage,
  highlights,
  localTips,
  mapsLink,
  sameDistrict,
  shortAddress,
  sourceLinks,
  sortedActivities,
  sortedDays,
  tagsFromQuery,
  titleFromQuery,
} from "@/lib/trip";
import type { ChatMessage, SavedTrip, StructuredItinerary } from "@/lib/types";

const TripMap = dynamic(() => import("./TripMap"), { ssr: false });

const STARTERS = [
  "3-day trip in Taipei",
  "2-day trip in Tainan focused on food",
  "Peninsula weekend with parks",
];

const DIET = [
  { id: "veg", label: "Vegetarian", phrase: "vegetarian-friendly food" },
  { id: "vegan", label: "Vegan", phrase: "vegan food only" },
  { id: "halal", label: "Halal", phrase: "halal food" },
  { id: "gluten", label: "Gluten-free", phrase: "gluten-free options" },
];

const ACCESS = [
  { id: "wheelchair", label: "Wheelchair", phrase: "wheelchair accessible" },
  { id: "lowwalk", label: "Low walking", phrase: "low walking, short distances between stops" },
];

const SETTING = [
  { id: "indoor", label: "Mostly indoor", phrase: "prefer indoor activities" },
  { id: "outdoor", label: "Mostly outdoor", phrase: "prefer outdoor activities" },
  { id: "mix", label: "Indoor + outdoor", phrase: "mix of indoor and outdoor" },
];

const VIBE = [
  { id: "date", label: "Date ideas", phrase: "date ideas, romantic and intimate" },
  { id: "friends", label: "Friend hangout", phrase: "friend hangout, social and casual" },
  { id: "solo", label: "Solo", phrase: "good for traveling solo" },
  { id: "family", label: "Family", phrase: "family-friendly" },
];

const START_TIMES = ["08:00", "09:00", "10:00", "11:00"];
const DINNER_TIMES = ["17:00", "18:00", "19:00", "20:00"];
const END_TIMES = ["20:00", "21:00", "22:00", "23:00"];

const QUICK = [
  "Add more food experiences throughout",
  "Change Day 1 evening to something more cultural",
  "Make the trip more budget-friendly",
];

const STORAGE_KEY = "packandgo-trips";

type Screen = "chat" | "itineraries" | "profile";
type Tab = "itinerary" | "map" | "highlights" | "tips";

export default function PackApp() {
  const [screen, setScreen] = useState<Screen>("chat");
  const [tab, setTab] = useState<Tab>("itinerary");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Where to, how many days, and who you are with? Add diet, access, indoor/outdoor, and when you want to start, eat dinner, and wrap the day.",
    },
  ]);
  const [structured, setStructured] = useState<StructuredItinerary | null>(null);
  const [formatted, setFormatted] = useState("");
  const [openDay, setOpenDay] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [apiUp, setApiUp] = useState<boolean | null>(null);
  const [saved, setSaved] = useState<SavedTrip[]>([]);
  const [constraints, setConstraints] = useState<string[]>([]);
  const [setting, setSetting] = useState("");
  const [vibe, setVibe] = useState("");
  const [startTime, setStartTime] = useState("");
  const [dinnerTime, setDinnerTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const hydratedRef = useRef(false);

  useEffect(() => {
    apiHealth().then(setApiUp);
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setSaved(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);

  const days = sortedDays(structured || undefined);
  const currentDay = days.find((d) => Number(d.day) === openDay) || days[0];
  const activities = sortedActivities(currentDay);
  const pins = useMemo(() => activityPins(activities), [activities]);
  const vlogs = sourceLinks(structured?.sources);

  const slotClocks = {
    morning: startTime || undefined,
    evening: dinnerTime || undefined,
    night: dinnerTime || undefined,
  };

  function withConstraints(text: string) {
    const extras = [
      ...DIET.filter((c) => constraints.includes(c.id)).map((c) => c.phrase),
      ...ACCESS.filter((c) => constraints.includes(c.id)).map((c) => c.phrase),
      SETTING.find((c) => c.id === setting)?.phrase,
      VIBE.find((c) => c.id === vibe)?.phrase,
      startTime ? `start the day around ${startTime}` : "",
      dinnerTime ? `dinner around ${dinnerTime}` : "",
      endTime ? `end the day around ${endTime}` : "",
    ].filter(Boolean);
    if (!extras.length) return text;
    return `${text.trim()}, ${extras.join(", ")}`;
  }

  function toggleConstraint(id: string) {
    setConstraints((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  function pickOne(current: string, next: string, setValue: (value: string) => void) {
    setValue(current === next ? "" : next);
  }

  useEffect(() => {
    if (!structured || hydratedRef.current) return;
    const needs = (structured.itinerary || []).some((day) =>
      (day.activities || []).some((act) =>
        (act.food_options || []).some(
          (option) => option.place_id && (option.lat == null || option.lon == null),
        ),
      ),
    );
    if (!needs) return;
    hydratedRef.current = true;
    hydrateTrip(structured)
      .then(setStructured)
      .catch(() => {
        hydratedRef.current = false;
      });
  }, [structured]);

  async function send(text: string, applyConstraints = false) {
    const trimmed = (applyConstraints ? withConstraints(text) : text).trim();
    if (!trimmed || busy) return;
    setDraft("");
    setError("");
    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setBusy(true);
    try {
      if (!structured) {
        hydratedRef.current = true;
        const data = await generateTrip(trimmed);
        const next = await hydrateTrip({
          ...(data.structured || {}),
          sources: data.structured?.sources?.length
            ? data.structured.sources
            : data.sources,
        });
        setQuery(trimmed);
        setStructured(next);
        setFormatted(data.itinerary || "");
        setOpenDay(Number(next.itinerary?.[0]?.day) || 1);
        setTab("itinerary");
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content:
              "Here is your itinerary. Adjust one slot from chat, or use a suggestion below.",
          },
        ]);
      } else {
        const data = await refineTrip(query, trimmed, structured);
        const next = await hydrateTrip(data.structured || structured);
        setStructured(next);
        setFormatted(data.itinerary || formatted);
        const label = data.modification?.type
          ? `Updated (${data.modification.type}${
              data.modification.target_day
                ? `, day ${data.modification.target_day}`
                : ""
            }).`
          : "Updated itinerary.";
        setMessages((m) => [...m, { role: "assistant", content: label }]);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      setMessages((m) => [...m, { role: "assistant", content: message }]);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft, !structured);
  }

  function persistTrip() {
    if (!structured || !query) return;
    const trip: SavedTrip = {
      id: `${Date.now()}`,
      query,
      structured,
      formatted,
      savedAt: new Date().toISOString(),
    };
    const next = [trip, ...saved.filter((t) => t.query !== query)].slice(0, 12);
    setSaved(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  async function shareTrip() {
    const text = formatted || titleFromQuery(query);
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* ignore */
    }
  }

  function openSaved(trip: SavedTrip) {
    setQuery(trip.query);
    setStructured(trip.structured);
    setFormatted(trip.formatted);
    setOpenDay(Number(trip.structured.itinerary?.[0]?.day) || 1);
    setScreen("chat");
    setTab("itinerary");
  }

  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">Pack &amp; Go</div>
        <nav>
          <button
            className={screen === "chat" ? "active" : ""}
            onClick={() => setScreen("chat")}
          >
            Chat
          </button>
          <button
            className={screen === "itineraries" ? "active" : ""}
            onClick={() => setScreen("itineraries")}
          >
            Itineraries
          </button>
          <button
            className={screen === "profile" ? "active" : ""}
            onClick={() => setScreen("profile")}
          >
            Profile
          </button>
        </nav>
        <p className="rail-note">
          {apiUp === false
            ? "API offline — start uvicorn on :8000"
            : "Streamlit demo stays on :8501"}
        </p>
      </aside>

      {screen === "itineraries" && (
        <main className="workspace">
          <h1>Saved this browser</h1>
          {!saved.length && <p className="muted">Save a generated trip to see it here.</p>}
          <ul className="saved-list">
            {saved.map((trip) => (
              <li key={trip.id}>
                <button onClick={() => openSaved(trip)}>{trip.query}</button>
              </li>
            ))}
          </ul>
        </main>
      )}

      {screen === "profile" && (
        <main className="workspace">
          <h1>Profile</h1>
          <p className="muted">
            Local demo — no accounts. Trips live in this browser. The Streamlit
            app is the rollback UI.
          </p>
        </main>
      )}

      {screen === "chat" && (
        <>
          <section className="chat-col">
            <h2>Plan a trip</h2>
            <div className="thread">
              {messages.map((msg, i) => (
                <div key={i} className={`bubble ${msg.role}`}>
                  {msg.content}
                </div>
              ))}
              {busy && <div className="bubble assistant">Working on it…</div>}
            </div>
            <div className="chips">
              {!structured && (
                <>
                  <p className="chip-label">Vibe</p>
                  <div className="chip-row">
                    {VIBE.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={vibe === item.id ? "picked" : ""}
                        disabled={busy}
                        onClick={() => pickOne(vibe, item.id, setVibe)}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <p className="chip-label">Diet</p>
                  <div className="chip-row">
                    {DIET.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={constraints.includes(item.id) ? "picked" : ""}
                        disabled={busy}
                        onClick={() => toggleConstraint(item.id)}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <p className="chip-label">Access</p>
                  <div className="chip-row">
                    {ACCESS.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={constraints.includes(item.id) ? "picked" : ""}
                        disabled={busy}
                        onClick={() => toggleConstraint(item.id)}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <p className="chip-label">Indoor / outdoor</p>
                  <div className="chip-row">
                    {SETTING.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={setting === item.id ? "picked" : ""}
                        disabled={busy}
                        onClick={() => pickOne(setting, item.id, setSetting)}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <p className="chip-label">Start the day</p>
                  <div className="chip-row">
                    {START_TIMES.map((item) => (
                      <button
                        key={item}
                        type="button"
                        className={startTime === item ? "picked" : ""}
                        disabled={busy}
                        onClick={() => pickOne(startTime, item, setStartTime)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  <p className="chip-label">Dinner</p>
                  <div className="chip-row">
                    {DINNER_TIMES.map((item) => (
                      <button
                        key={item}
                        type="button"
                        className={dinnerTime === item ? "picked" : ""}
                        disabled={busy}
                        onClick={() => pickOne(dinnerTime, item, setDinnerTime)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  <p className="chip-label">End the day</p>
                  <div className="chip-row">
                    {END_TIMES.map((item) => (
                      <button
                        key={item}
                        type="button"
                        className={endTime === item ? "picked" : ""}
                        disabled={busy}
                        onClick={() => pickOne(endTime, item, setEndTime)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  <p className="chip-label">Start a trip</p>
                </>
              )}
              {(structured ? QUICK : STARTERS).map((item) => (
                <button
                  key={item}
                  type="button"
                  disabled={busy}
                  onClick={() => void send(item, !structured)}
                >
                  {item}
                </button>
              ))}
            </div>
            <form onSubmit={onSubmit} className="composer">
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={
                  structured
                    ? "Tell me what to change…"
                    : "e.g. 3-day trip in Tainan, date ideas"
                }
              />
              <button type="submit" disabled={busy || !draft.trim()}>
                Send
              </button>
            </form>
          </section>

          <main className="workspace trip">
            {!structured ? (
              <div className="empty-hero">
                <h1>Your itinerary will land here</h1>
                <p>
                  Try Taipei, Tainan, Taichung, or a Peninsula weekend. Keep
                  Streamlit on :8501 if you want the old demo.
                </p>
              </div>
            ) : (
              <>
                <header
                  className="hero"
                  style={{ backgroundImage: `url(${heroImage(query)})` }}
                >
                  <div className="hero-fade">
                    <p className="eyebrow">AI generated</p>
                    <h1>{titleFromQuery(query)}</h1>
                    <div className="tags">
                      {tagsFromQuery(query).map((tag) => (
                        <span key={tag}>{tag}</span>
                      ))}
                    </div>
                    <div className="hero-actions">
                      <button type="button" onClick={persistTrip}>
                        Save
                      </button>
                      <button type="button" onClick={() => void shareTrip()}>
                        Copy itinerary
                      </button>
                    </div>
                  </div>
                </header>

                <div className="tabs">
                  {(
                    [
                      ["itinerary", "Itinerary"],
                      ["map", "Map"],
                      ["highlights", "Highlights"],
                      ["tips", "Local tips"],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      className={tab === id ? "active" : ""}
                      onClick={() => setTab(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {error && <p className="banner">{error}</p>}

                {tab === "itinerary" && (
                  <div className="board">
                    <div className="timeline">
                      {days.map((day) => {
                        const n = Number(day.day);
                        const open = n === Number(currentDay?.day);
                        return (
                          <section key={n} className="day-block">
                            <button
                              className="day-toggle"
                              onClick={() => setOpenDay(n)}
                            >
                              Day {n}
                              {open ? " · open" : ""}
                            </button>
                            {open && (
                              <>
                                <div className="stop stop-head">
                                  <div>Time</div>
                                  <div>Activity</div>
                                  <div>Location</div>
                                  <div>Food</div>
                                </div>
                                {activities.map((act, i) => {
                                  const stopUrl = mapsLink(act.place);
                                  const stopName = act.place?.name;
                                  return (
                                    <article key={`${n}-${i}`} className="stop">
                                      <div className="when">
                                        <span>{clockFor(act.time, slotClocks)}</span>
                                        <small>{act.time}</small>
                                      </div>
                                      <div className="what">
                                        <h3>{act.activity}</h3>
                                        <p>{durationFor(act.time)}</p>
                                      </div>
                                      <div className="where">
                                        {stopName && stopUrl ? (
                                          <a
                                            href={stopUrl}
                                            target="_blank"
                                            rel="noreferrer"
                                          >
                                            <strong>{stopName}</strong>
                                          </a>
                                        ) : (
                                          <p className="muted">No mapped place yet</p>
                                        )}
                                      </div>
                                      <div className="eats">
                                        {(act.food_options || []).slice(0, 3).map((food) => {
                                          const nearby = sameDistrict(food, act.place);
                                          const line = [
                                            food.rating ? `${food.rating}★` : "",
                                            food.district,
                                            shortAddress(food.address),
                                          ]
                                            .filter(Boolean)
                                            .join(" · ");
                                          return (
                                            <a
                                              key={food.name}
                                              href={food.maps_url || mapsLink(food)}
                                              target="_blank"
                                              rel="noreferrer"
                                            >
                                              <strong>{food.name}</strong>
                                              {line ? <span>{line}</span> : null}
                                              {nearby ? (
                                                <span className="same-district">
                                                  Same district as this stop
                                                </span>
                                              ) : null}
                                            </a>
                                          );
                                        })}
                                        {!act.food_options?.length && act.food && (
                                          <p>{act.food}</p>
                                        )}
                                      </div>
                                    </article>
                                  );
                                })}
                              </>
                            )}
                          </section>
                        );
                      })}
                    </div>
                    <div className="map-pane">
                      <TripMap
                        key={`board-${openDay}-${pins.length}`}
                        pins={pins}
                        fallback={fallbackCenter(query)}
                      />
                    </div>
                  </div>
                )}

                {tab === "map" && (
                  <div className="map-pane tall">
                    <TripMap
                      key={`tab-${openDay}-${pins.length}`}
                      pins={pins}
                      fallback={fallbackCenter(query)}
                    />
                  </div>
                )}

                {tab === "highlights" && (
                  <ul className="tips">
                    {highlights(structured).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}

                {tab === "tips" && (
                  <ul className="tips">
                    {localTips(structured).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}

                {vlogs.length > 0 && (
                  <section className="sources">
                    <h2>From these vlogs</h2>
                    <p className="muted">
                      Retrieved transcript chunks from these YouTube videos.
                    </p>
                    <ul>
                      {vlogs.map((vlog) => (
                        <li key={vlog.id}>
                          <a href={vlog.url} target="_blank" rel="noreferrer">
                            youtube.com/watch?v={vlog.id}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </>
            )}
          </main>
        </>
      )}
    </div>
  );
}
