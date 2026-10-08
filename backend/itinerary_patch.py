"""Pure helpers for surgical itinerary edits. No LLM or API imports."""

from __future__ import annotations

import copy
import json
import re
from typing import Any


TIME_SLOTS = ("Morning", "Afternoon", "Evening")


def normalize_time_slot(time_slot: str | None) -> str | None:
    if not time_slot:
        return None
    key = time_slot.strip().lower()
    mapping = {
        "morning": "Morning",
        "afternoon": "Afternoon",
        "evening": "Evening",
        "night": "Evening",
    }
    return mapping.get(key, time_slot.strip().title())


def find_day(itinerary: dict, day_num: int) -> dict | None:
    for day in itinerary.get("itinerary", []):
        if int(day.get("day")) == int(day_num):
            return day
    return None


def _activity_index(day: dict, target_time: str) -> int | None:
    for i, activity in enumerate(day.get("activities", [])):
        if normalize_time_slot(activity.get("time")) == target_time:
            return i
    return None


def patch_activity(
    itinerary: dict,
    day_num: int,
    time_slot: str,
    new_activity: dict,
) -> dict:
    """Replace one time slot. Leaves every other day and slot unchanged."""
    target_time = normalize_time_slot(time_slot)
    if not target_time:
        raise ValueError("Could not tell which time slot to change.")

    updated = copy.deepcopy(itinerary)
    day = find_day(updated, day_num)
    if day is None:
        raise ValueError(f"Day {day_num} not found in the current itinerary.")

    idx = _activity_index(day, target_time)
    if idx is None:
        raise ValueError(f"{target_time} not found on Day {day_num}.")

    existing = day["activities"][idx]
    patched = {
        "time": target_time,
        "activity": new_activity.get("activity") or existing.get("activity", ""),
        "food": new_activity.get("food", existing.get("food", "")),
    }
    # Options belong to the old restaurant; drop them when the food changes so
    # ensure_food can refill with venues that match the new slot.
    options = new_activity.get("food_options") or (
        existing.get("food_options") if patched["food"] == existing.get("food") else None
    )
    if options:
        patched["food_options"] = options
    if new_activity.get("source"):
        patched["source"] = new_activity["source"]
    elif existing.get("source"):
        patched["source"] = existing["source"]

    day["activities"][idx] = patched
    return updated


def patch_day(itinerary: dict, day_num: int, new_day: dict | list) -> dict:
    """Replace one day's activities. Leaves every other day unchanged."""
    if isinstance(new_day, list):
        activities = new_day
    else:
        activities = new_day.get("activities")
    if not activities:
        raise ValueError("Replacement day is missing activities.")

    updated = copy.deepcopy(itinerary)
    days = updated.get("itinerary", [])
    idx = None
    for i, day in enumerate(days):
        if int(day.get("day")) == int(day_num):
            idx = i
            break
    if idx is None:
        raise ValueError(f"Day {day_num} not found in the current itinerary.")

    days[idx] = {"day": int(day_num), "activities": activities}
    return updated


def apply_patches(itinerary: dict, patches: list) -> dict:
    """Apply a list of slot replacements. Unlisted slots stay as they are."""
    updated = itinerary
    for patch in patches:
        day = patch.get("day") or patch.get("target_day")
        time_slot = patch.get("time") or patch.get("target_time")
        if day is None or not time_slot:
            continue
        updated = patch_activity(updated, day, time_slot, patch)
    return updated


def extract_json(text: str) -> Any:
    """Pull a JSON object or array out of an LLM response."""
    if not text:
        return {}

    fenced = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    for pattern in (r"(\{[\s\S]*\})", r"(\[[\s\S]*\])"):
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def modification_summary(intent: dict) -> dict:
    return {
        "type": intent.get("type"),
        "target_day": intent.get("target_day"),
        "target_time": normalize_time_slot(intent.get("target_time"))
        if intent.get("target_time")
        else intent.get("target_time"),
    }
