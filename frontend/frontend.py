import os
import re
import html
import pandas as pd
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 120

DESTINATIONS = [
    {
        "city": "Paris",
        "label": "3-5 days",
        "image": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=600&h=800",
    },
    {
        "city": "Tokyo",
        "label": "3-5 days",
        "image": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=600&h=800",
    },
    {
        "city": "Bali",
        "label": "3-5 days",
        "image": "https://images.unsplash.com/photo-1575573330964-db3dad170190?auto=format&fit=crop&w=600&h=800",
    },
    {
        "city": "New York",
        "label": "3-5 days",
        "image": "https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?auto=format&fit=crop&w=600&h=800",
    },
]

st.set_page_config(
    page_title="Pack & Go",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

defaults = {
    "page": "home",
    "itinerary_generated": False,
    "current_itinerary": None,
    "structured_itinerary": None,
    "original_query": "",
    "conversation_history": [],
    "last_modification": None,
    "recent_itineraries": [],
    "selected_city": None,
    "seed_step": 0,
    "seed_days": None,
    "seed_vibe": None,
    "seed_messages": [],
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: Inter, sans-serif; }

    .stApp {
        background: radial-gradient(1200px 600px at 10% -10%, #3b2a6e 0%, transparent 50%),
                    radial-gradient(900px 500px at 100% 0%, #5b2d8e 0%, transparent 45%),
                    linear-gradient(180deg, #1a1028 0%, #120c1c 100%);
        color: #f7f4ff;
    }

    header[data-testid="stHeader"] { background: transparent; }
    #MainMenu, footer { visibility: hidden; }
    .block-container { padding-top: 1.2rem; max-width: 1180px; }

    .top-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.5rem;
    }
    .brand {
        font-size: 1.35rem;
        font-weight: 700;
        color: #fff;
        letter-spacing: 0.01em;
    }
    .hero-title {
        font-size: 2.6rem;
        font-weight: 700;
        color: #fff;
        margin: 1.2rem 0 0.35rem 0;
    }
    .hero-sub {
        color: rgba(255,255,255,0.78);
        font-size: 1.15rem;
        margin-bottom: 1.6rem;
    }
    .section-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin: 2rem 0 0.8rem 0;
        color: #fff;
    }
    .section-head h3 { margin: 0; font-size: 1.15rem; font-weight: 600; }
    .muted { color: rgba(255,255,255,0.55); font-size: 0.92rem; }

    .dest-caption {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(16,10,28,0.72);
        backdrop-filter: blur(10px);
        border-radius: 0 0 18px 18px;
        padding: 0.7rem 0.9rem;
        margin-top: -8px;
        position: relative;
        z-index: 1;
    }
    .dest-caption strong { color: #fff; display: block; }
    .dest-caption span { color: rgba(255,255,255,0.7); font-size: 0.85rem; }
    [data-testid="stImage"] img {
        border-radius: 18px 18px 0 0;
        object-fit: cover;
        width: 100%;
        height: 260px;
    }

    .itinerary-card {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.08);
        padding: 1.4rem 1.5rem;
        border-radius: 20px;
        margin: 0.8rem 0;
        color: #f4f0ff;
    }
    .day-header {
        color: #e2d4ff;
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
        padding-bottom: 0.45rem;
        border-bottom: 2px solid rgba(196, 132, 252, 0.5);
    }
    .slot-label {
        font-weight: 600;
        color: #d8b4fe;
        margin-top: 0.9rem;
        font-size: 1rem;
    }
    .activity-item {
        background: rgba(255,255,255,0.08);
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin: 0.55rem 0;
        border-left: 3px solid #c084fc;
        color: #f7f4ff;
    }
    .slot-panel, .food-panel {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 0.95rem 1.05rem;
        min-height: 7.5rem;
        color: #f7f4ff;
    }
    .slot-kicker {
        color: #d8b4fe;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }
    .food-chip {
        background: rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 0.45rem 0.6rem;
        margin: 0.35rem 0 0 0;
        font-size: 0.88rem;
    }
    .food-chip a { color: #e9d5ff; }
    .recent-card {
        background: rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        margin-bottom: 0.7rem;
        color: #fff;
    }

    .stTextInput > div > div > input {
        background: rgba(20, 14, 36, 0.85) !important;
        color: #fff !important;
        border-radius: 999px !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        padding: 0.95rem 1.2rem !important;
    }
    .stTextInput > div > div > input::placeholder { color: rgba(255,255,255,0.45); }

    div[data-testid="stChatInput"] textarea {
        background: rgba(20, 14, 36, 0.9);
        color: #fff;
        border-radius: 16px;
    }

    .stButton > button {
        background: linear-gradient(90deg, #7c3aed 0%, #db2777 100%);
        color: white;
        font-weight: 600;
        border-radius: 999px;
        border: none;
        padding: 0.55rem 1.2rem;
        box-shadow: 0 8px 24px rgba(124, 58, 237, 0.35);
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        border: none;
        color: white;
    }
    .stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.08);
        box-shadow: none;
        color: rgba(255,255,255,0.88);
        font-weight: 500;
        border: 1px solid rgba(255,255,255,0.12);
    }
    .stButton > button[kind="secondary"]:hover {
        color: #fff;
        background: rgba(255,255,255,0.14);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_modification(mod):
    if not mod:
        return ""
    change_type = mod.get("type")
    day = mod.get("target_day")
    time_slot = mod.get("target_time")
    if change_type == "modify_activity" and day:
        slot = f" {time_slot}" if time_slot else ""
        return f"Updated Day {day}{slot}"
    if change_type == "modify_day" and day:
        return f"Updated Day {day}"
    if change_type == "add_preference":
        return "Updated itinerary based on your feedback"
    if change_type == "regenerate_all":
        return "Regenerated the full itinerary"
    return "Updated itinerary"


def generate_itinerary_request(query):
    try:
        response = requests.post(
            f"{BACKEND_URL}/itinerary/v2",
            json={"query": query},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            payload = response.json()
            if payload.get("error"):
                return None, payload["error"]
            return payload, None
        try:
            detail = response.json().get("detail", "")
        except Exception:
            detail = response.text
        return None, detail or "We couldn't generate your itinerary. Is the API running?"
    except requests.exceptions.Timeout:
        return None, "Request timed out. Please try again."
    except requests.exceptions.ConnectionError:
        return None, f"Could not connect to {BACKEND_URL}"
    except Exception as exc:
        return None, str(exc)


def refine_itinerary_request(feedback):
    try:
        response = requests.post(
            f"{BACKEND_URL}/itinerary/refine",
            json={
                "query": st.session_state.original_query,
                "feedback": feedback,
                "current_itinerary": st.session_state.structured_itinerary,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json(), None
        try:
            detail = response.json().get("detail", "")
        except Exception:
            detail = response.text
        return None, detail or "Failed to update itinerary"
    except Exception as exc:
        return None, str(exc)


def looks_complete(text: str) -> bool:
    lowered = text.lower()
    has_days = bool(re.search(r"\b(\d+\s*-?\s*day|week|weekend)\b", lowered))
    has_place = any(
        city.lower() in lowered for city in [d["city"] for d in DESTINATIONS]
    ) or bool(re.search(r"\b(in|to)\s+[A-Z]", text))
    has_vibe = any(
        word in lowered
        for word in ("food", "culture", "outdoor", "night", "museum", "mix", "beach")
    )
    return has_days and (has_place or st.session_state.selected_city) and (has_vibe or len(text.split()) >= 8)


def parse_days(text: str) -> str:
    lowered = text.lower()
    if "week" in lowered:
        return "7-day"
    match = re.search(r"(\d+)\s*-?\s*day", lowered)
    if match:
        return f"{match.group(1)}-day"
    if "5" in lowered or "five" in lowered:
        return "5-day"
    if "3" in lowered or "three" in lowered:
        return "3-day"
    return "3-day"


def parse_vibe(text: str) -> str:
    lowered = text.lower()
    found = [
        label
        for key, label in (
            ("food", "food"),
            ("culture", "culture"),
            ("museum", "culture"),
            ("outdoor", "outdoors"),
            ("nature", "outdoors"),
            ("night", "nightlife"),
            ("mix", "a mix of experiences"),
        )
        if key in lowered
    ]
    if found:
        unique = list(dict.fromkeys(found))
        return " and ".join(unique)
    return text.strip() or "a mix of experiences"


def compose_query(city: str, days: str, vibe: str) -> str:
    return f"{days} trip in {city} focused on {vibe}"


def apply_generated(data, query: str, save_recent: bool = True):
    st.session_state.current_itinerary = data
    st.session_state.structured_itinerary = data.get("structured", {})
    st.session_state.original_query = query
    st.session_state.itinerary_generated = True
    st.session_state.last_modification = None
    st.session_state.page = "itinerary"
    st.session_state.conversation_history = [
        {"role": "user", "content": query},
        {
            "role": "assistant",
            "content": "Here is your itinerary. Tell me what to change — a day, a time slot, or the vibe.",
        },
    ]
    if save_recent:
        st.session_state.recent_itineraries.insert(
            0,
            {
                "query": query,
                "structured": data.get("structured", {}),
                "formatted": data.get("itinerary", ""),
                "raw": data,
            },
        )
        st.session_state.recent_itineraries = st.session_state.recent_itineraries[:8]


def start_seed_chat(city: str):
    st.session_state.selected_city = city
    st.session_state.seed_step = 0
    st.session_state.seed_days = None
    st.session_state.seed_vibe = None
    st.session_state.seed_messages = [
        {
            "role": "assistant",
            "content": f"{city} is a great pick. 3 days, 5 days, or a full week?",
        }
    ]
    st.session_state.page = "chat_seed"


def go_home():
    st.session_state.page = "home"
    st.session_state.itinerary_generated = False
    st.session_state.selected_city = None
    st.session_state.seed_messages = []


def display_itinerary(itinerary_text):
    if not itinerary_text:
        return
    if "🗓️ Day " not in itinerary_text:
        st.markdown(itinerary_text)
        return
    days = itinerary_text.split("🗓️ Day ")
    days = [d.strip() for d in days if d.strip()]
    for day_text in days:
        lines = day_text.split("\n")
        day_num = lines[0].strip() if lines else "?"
        parts = [f'<div class="itinerary-card"><div class="day-header">Day {html.escape(str(day_num))}</div>']
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            if line.startswith("☀️") or line.startswith("🌤️") or line.startswith("🌙"):
                parts.append(f'<div class="slot-label">{html.escape(line)}</div>')
            elif line.startswith("-"):
                parts.append(
                    f'<div class="activity-item">{html.escape(line[1:].strip())}</div>'
                )
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)


SLOT_ORDER = {"morning": 0, "afternoon": 1, "evening": 2}


def day_numbers(structured):
    days = []
    for day in (structured or {}).get("itinerary", []):
        try:
            days.append(int(day.get("day")))
        except (TypeError, ValueError):
            continue
    return sorted(set(days))


def day_activities(structured, day_num):
    for day in (structured or {}).get("itinerary", []):
        try:
            if int(day.get("day")) == int(day_num):
                activities = day.get("activities", [])
                return sorted(
                    activities,
                    key=lambda a: SLOT_ORDER.get(str(a.get("time", "")).lower(), 9),
                )
        except (TypeError, ValueError):
            continue
    return []


def day_pins(activities):
    """Map rows for the day's activity (if matched) and every food option."""
    pins = []
    for activity in activities:
        spots = list(activity.get("food_options") or [])
        if activity.get("place"):
            spots = [activity["place"]] + spots
        for option in spots:
            lat, lon = option.get("lat"), option.get("lon")
            if lat is None or lon is None:
                continue
            pins.append(
                {
                    "lat": float(lat),
                    "lon": float(lon),
                    "name": option.get("name") or "",
                    "slot": activity.get("time") or "",
                }
            )
    return pins


def _food_chip_html(option: dict) -> str:
    name = html.escape(str(option.get("name") or "Restaurant"))
    rating = option.get("rating")
    stars = f"{html.escape(str(rating))}⭐" if rating else ""
    district = html.escape(str(option.get("district") or ""))
    url = option.get("maps_url")
    meta = " · ".join(part for part in (stars, district) if part)
    link = (
        f' <a href="{html.escape(url, quote=True)}" target="_blank">Maps</a>'
        if url
        else ""
    )
    return f'<div class="food-chip"><strong>{name}</strong>{(" · " + meta) if meta else ""}{link}</div>'


def render_slot_row(activity: dict, row_key: str):
    slot = activity.get("time") or "Slot"
    left, right = st.columns([1, 1], gap="medium")
    with left:
        st.markdown(
            f'<div class="slot-panel"><div class="slot-kicker">{html.escape(str(slot))}</div>'
            f"{html.escape(str(activity.get('activity') or ''))}</div>",
            unsafe_allow_html=True,
        )
    with right:
        options = activity.get("food_options") or []
        food = activity.get("food") or ""
        chips = "".join(_food_chip_html(o) for o in options[:3])
        if not chips and food:
            chips = f'<div class="food-chip">{html.escape(str(food))}</div>'
        if not chips:
            chips = '<div class="food-chip">No food picks for this slot.</div>'
        st.markdown(
            f'<div class="food-panel"><div class="slot-kicker">Eat nearby</div>{chips}</div>',
            unsafe_allow_html=True,
        )


def render_day_board(structured):
    days = day_numbers(structured)
    if not days:
        return None

    selected = st.selectbox(
        "Day",
        days,
        format_func=lambda d: f"Day {d}",
        key="map_day",
    )
    activities = day_activities(structured, selected)
    plan, mmap = st.columns([1.2, 0.9], gap="large")
    with plan:
        for i, activity in enumerate(activities):
            render_slot_row(activity, f"d{selected}_{i}")
    with mmap:
        st.markdown("**Map**")
        pins = day_pins(activities)
        if pins:
            st.map(pd.DataFrame(pins), latitude="lat", longitude="lon", size=60)
        else:
            st.caption(
                "No mapped spots for this day. Places covers Taipei, Tainan, "
                "Taichung, Bangkok, and the Peninsula."
            )
    return selected


def render_refine_sidebar():
    with st.sidebar:
        st.markdown("### Refine this trip")
        st.caption("Chat lives here so the plan and map stay on the page.")
        st.caption("Try: Change Day 2 morning to something more cultural")
        for msg in st.session_state.conversation_history:
            if msg.get("content") == "itinerary_generated":
                continue
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        feedback = st.chat_input("Tell me what to change...")
        if not feedback:
            return
        with st.spinner("Updating your itinerary..."):
            data, error = refine_itinerary_request(feedback)
        if error:
            st.session_state.conversation_history.append(
                {"role": "user", "content": feedback}
            )
            st.session_state.conversation_history.append(
                {"role": "assistant", "content": error}
            )
            st.rerun()
        st.session_state.current_itinerary = data
        st.session_state.structured_itinerary = data.get("structured", {})
        summary = format_modification(data.get("modification"))
        st.session_state.last_modification = summary
        for item in st.session_state.recent_itineraries:
            if item.get("query") == st.session_state.original_query:
                item["raw"] = data
                item["structured"] = data.get("structured", {})
                item["formatted"] = data.get("itinerary", "")
                break
        st.session_state.conversation_history.append(
            {"role": "user", "content": feedback}
        )
        st.session_state.conversation_history.append(
            {
                "role": "assistant",
                "content": summary or "Updated itinerary based on your feedback.",
            }
        )
        st.rerun()


def render_nav():
    left, right = st.columns([2, 3])
    with left:
        st.markdown('<div class="brand">🌍 Pack & Go</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="nav-row">', unsafe_allow_html=True)
        n1, n2, n3 = st.columns(3)
        if n1.button("Home", key="nav_home", type="secondary"):
            go_home()
            st.rerun()
        if n2.button("Itineraries", key="nav_itin", type="secondary"):
            st.session_state.page = "itineraries"
            st.rerun()
        if n3.button("Profile", key="nav_profile", type="secondary"):
            st.session_state.page = "profile"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_home():
    st.markdown('<p class="hero-title">Hi there! Where to next? ✈️</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-sub">Let AI create the perfect trip for you.</p>',
        unsafe_allow_html=True,
    )

    search_col, btn_col = st.columns([5, 1.3])
    with search_col:
        query = st.text_input(
            "Trip prompt",
            placeholder="e.g., 3-day trip to Paris, France",
            label_visibility="collapsed",
            key="home_query",
        )
    with btn_col:
        generate = st.button("Generate", key="generate_btn", width="stretch")

    if generate:
        if not query.strip():
            st.warning("Enter a destination, or pick a city below.")
        else:
            with st.spinner("Crafting your itinerary..."):
                data, error = generate_itinerary_request(query.strip())
            if error:
                st.error(error)
            elif data:
                apply_generated(data, query.strip())
                st.rerun()

    st.markdown(
        '<div class="section-head"><h3>Popular Destinations</h3></div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    for dest, col in zip(DESTINATIONS, cols):
        with col:
            st.image(dest["image"], width="stretch")
            st.markdown(
                f'<div class="dest-caption"><div><strong>{dest["city"]}</strong>'
                f'<span>{dest["label"]}</span></div></div>',
                unsafe_allow_html=True,
            )
            if st.button("→", key=f"dest_{dest['city']}", width="stretch", type="secondary"):
                start_seed_chat(dest["city"])
                st.rerun()

    rec_l, rec_r = st.columns([4, 1])
    with rec_l:
        st.markdown(
            '<div class="section-head"><h3>Your Recent Itineraries</h3></div>',
            unsafe_allow_html=True,
        )
    with rec_r:
        if st.button("View all", key="view_all_recent", type="secondary"):
            st.session_state.page = "itineraries"
            st.rerun()
    recents = st.session_state.recent_itineraries[:3]
    if not recents:
        st.markdown(
            '<p class="muted">No trips yet. Generate one or tap a destination.</p>',
            unsafe_allow_html=True,
        )
    else:
        for i, item in enumerate(recents):
            st.markdown(
                f'<div class="recent-card"><strong>{item["query"]}</strong></div>',
                unsafe_allow_html=True,
            )
            if st.button("Open", key=f"recent_{i}", type="secondary"):
                apply_generated(item["raw"], item["query"], save_recent=False)
                st.rerun()


def render_chat_seed():
    city = st.session_state.selected_city or "this city"
    st.markdown(f'<p class="hero-title">Let\'s tailor {city}</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-sub">A couple of quick questions, then we will build the trip.</p>',
        unsafe_allow_html=True,
    )

    for msg in st.session_state.seed_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_text = st.chat_input("Your answer...")
    if not user_text:
        return

    st.session_state.seed_messages.append({"role": "user", "content": user_text})

    if looks_complete(user_text):
        query = user_text.strip()
        if st.session_state.selected_city and st.session_state.selected_city.lower() not in query.lower():
            query = f"{query} in {st.session_state.selected_city}"
        with st.spinner("Crafting your itinerary..."):
            data, error = generate_itinerary_request(query)
        if error:
            st.session_state.seed_messages.append({"role": "assistant", "content": error})
            st.rerun()
        elif data:
            apply_generated(data, query)
            st.rerun()
        return

    if st.session_state.seed_step == 0:
        st.session_state.seed_days = parse_days(user_text)
        st.session_state.seed_step = 1
        st.session_state.seed_messages.append(
            {
                "role": "assistant",
                "content": "Any focus — food, culture, outdoors, nightlife, or a mix?",
            }
        )
        st.rerun()
        return

    st.session_state.seed_vibe = parse_vibe(user_text)
    query = compose_query(
        st.session_state.selected_city,
        st.session_state.seed_days or "3-day",
        st.session_state.seed_vibe,
    )
    with st.spinner("Crafting your itinerary..."):
        data, error = generate_itinerary_request(query)
    if error:
        st.session_state.seed_messages.append({"role": "assistant", "content": error})
        st.rerun()
    elif data:
        apply_generated(data, query)
        st.rerun()


def render_itinerary():
    st.markdown(
        "<style>.block-container { max-width: 1360px; }</style>",
        unsafe_allow_html=True,
    )
    render_refine_sidebar()

    top_l, top_r = st.columns([4, 1])
    with top_l:
        st.markdown('<p class="hero-title">Your itinerary</p>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="hero-sub">{st.session_state.original_query}</p>',
            unsafe_allow_html=True,
        )
        st.caption("Refine the trip from the left sidebar.")
    with top_r:
        if st.button("New trip", key="new_trip", width="stretch"):
            go_home()
            st.rerun()

    itinerary_text = ""
    if st.session_state.current_itinerary:
        itinerary_text = st.session_state.current_itinerary.get("itinerary", "")
    if st.session_state.last_modification:
        st.success(st.session_state.last_modification)

    structured = st.session_state.structured_itinerary
    if structured and day_numbers(structured):
        render_day_board(structured)
    else:
        display_itinerary(itinerary_text)

    if itinerary_text:
        st.download_button(
            label="Download itinerary",
            data=itinerary_text,
            file_name="my_travel_itinerary.txt",
            mime="text/plain",
        )


def render_itineraries():
    st.markdown('<p class="hero-title">Your itineraries</p>', unsafe_allow_html=True)
    recents = st.session_state.recent_itineraries
    if not recents:
        st.markdown(
            '<p class="muted">Nothing saved this session yet.</p>',
            unsafe_allow_html=True,
        )
        return
    for i, item in enumerate(recents):
        st.markdown(
            f'<div class="recent-card"><strong>{item["query"]}</strong></div>',
            unsafe_allow_html=True,
        )
        if st.button("Open", key=f"itin_open_{i}", type="secondary"):
            apply_generated(item["raw"], item["query"], save_recent=False)
            st.rerun()


def render_profile():
    st.markdown('<p class="hero-title">Profile</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="muted">Local demo only — no accounts yet. Trips live in this browser session.</p>',
        unsafe_allow_html=True,
    )


render_nav()
page = st.session_state.page
if page == "chat_seed":
    render_chat_seed()
elif page == "itinerary":
    render_itinerary()
elif page == "itineraries":
    render_itineraries()
elif page == "profile":
    render_profile()
else:
    render_home()
