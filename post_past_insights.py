#!/usr/bin/env python3
"""
Daily Facebook post generator for the "Past Insights" page.

Facts come from Wikipedia/Wikimedia On This Day. Gemini is used only to rewrite
the selected facts into an engaging English Facebook post.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import random
import re
import sys
from dataclasses import dataclass
from typing import Any

import requests


WIKIMEDIA_ENDPOINTS = (
    "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month:02d}/{day:02d}",
    "https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{month:02d}/{day:02d}",
)
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v25.0")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


@dataclass(frozen=True)
class HistoricalEvent:
    year: int
    text: str
    page_title: str | None
    page_url: str | None


def env(name: str, required: bool = True, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def today_in_rome() -> dt.date:
    try:
        from zoneinfo import ZoneInfo

        return dt.datetime.now(ZoneInfo("Europe/Rome")).date()
    except Exception:
        return dt.datetime.utcnow().date()


def fetch_wikipedia_events(target_date: dt.date) -> list[HistoricalEvent]:
    headers = {
        "User-Agent": env(
            "WIKIMEDIA_USER_AGENT",
            required=False,
            default="PastInsightsBot/1.0 (global history Facebook page; contact: set WIKIMEDIA_USER_AGENT)",
        ),
        "Accept": "application/json",
    }

    last_error: Exception | None = None
    for endpoint in WIKIMEDIA_ENDPOINTS:
        url = endpoint.format(month=target_date.month, day=target_date.day)
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            payload = response.json()
            return parse_wikipedia_events(payload)
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Could not fetch Wikipedia events: {last_error}")


def parse_wikipedia_events(payload: dict[str, Any]) -> list[HistoricalEvent]:
    events: list[HistoricalEvent] = []

    for item in payload.get("events", []):
        year = item.get("year")
        text = normalize_space(item.get("text", ""))
        pages = item.get("pages") or []
        first_page = pages[0] if pages else {}
        page_title = first_page.get("title")
        page_url = first_page.get("content_urls", {}).get("desktop", {}).get("page")

        if isinstance(year, int) and text:
            events.append(
                HistoricalEvent(
                    year=year,
                    text=strip_html(text),
                    page_title=page_title,
                    page_url=page_url,
                )
            )

    return events


def strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    return normalize_space(value)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def select_events(events: list[HistoricalEvent], count: int = 3) -> list[HistoricalEvent]:
    useful = [
        event
        for event in events
        if event.year > 0
        and len(event.text) >= 45
        and not looks_too_narrow(event.text)
    ]

    with_pages = [event for event in useful if event.page_url]
    pool = with_pages if len(with_pages) >= count else useful

    if len(pool) < count:
        raise RuntimeError(f"Wikipedia returned only {len(pool)} usable events.")

    seed = today_in_rome().strftime("%Y-%m-%d")
    rng = random.Random(seed)
    selected = rng.sample(pool, count)
    return sorted(selected, key=lambda event: event.year)


def looks_too_narrow(text: str) -> bool:
    lower = text.lower()
    avoid = (
        "episode of ",
        "television series",
        "album",
        "single",
        "video game",
    )
    return any(marker in lower for marker in avoid)


def rewrite_with_gemini(events: list[HistoricalEvent], target_date: dt.date) -> str:
    api_key = env("GEMINI_API_KEY")
    model = env("GEMINI_MODEL", required=False, default=DEFAULT_MODEL)
    payload_events = [
        {
            "year": event.year,
            "text": event.text,
            "source_title": event.page_title,
            "source_url": event.page_url,
        }
        for event in events
    ]

    system_prompt = (
        "You are the copywriter for the English-language Facebook page 'Past Insights'. "
        "You rewrite verified historical events into engaging English. Facts come only "
        "from the provided data. Do not add names, dates, places, causes, consequences, "
        "or details that are not present in the input. Never change the years."
    )
    user_prompt = f"""
Post date: {target_date.strftime("%B %d")}.

Verified events from English Wikipedia, in JSON:
{json.dumps(payload_events, ensure_ascii=False, indent=2)}

Write a Facebook post in English with:
- a short opening
- 3 bullet points, one per event, each including the exact year
- a curious, accessible tone
- maximum 170 words
- no invented facts beyond the provided data
- a simple closing question

Do not include source links in the main body: they will be appended later.
"""

    response = requests.post(
        GEMINI_GENERATE_URL.format(model=model),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500,
            },
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    rewritten = extract_gemini_text(data)
    validate_rewrite(rewritten, events)
    return rewritten


def extract_gemini_text(data: dict[str, Any]) -> str:
    chunks: list[str] = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)

    result = "\n".join(chunks).strip()
    if not result:
        raise RuntimeError(f"Gemini response did not contain text: {data}")
    return result


def validate_rewrite(text: str, events: list[HistoricalEvent]) -> None:
    expected_years = {str(event.year) for event in events}
    found_years = set(re.findall(r"\b\d{3,4}\b", text))
    missing = expected_years - found_years

    if missing:
        raise RuntimeError(f"Gemini rewrite omitted these required years: {sorted(missing)}")

    unexpected = {
        year
        for year in found_years
        if year not in expected_years and 100 <= int(year) <= 2999
    }
    if unexpected:
        raise RuntimeError(f"Gemini rewrite introduced unexpected years: {sorted(unexpected)}")


def append_sources(text: str, events: list[HistoricalEvent]) -> str:
    lines = [text.strip(), "", "Sources: Wikipedia"]
    for event in events:
        label = event.page_title or f"{event.year} event"
        if event.page_url:
            lines.append(f"- {event.year}: {label} - {event.page_url}")
        else:
            lines.append(f"- {event.year}: {label}")
    return "\n".join(lines).strip()


def publish_to_facebook(message: str) -> dict[str, Any]:
    page_id = env("FACEBOOK_PAGE_ID")
    page_access_token = env("FACEBOOK_PAGE_ACCESS_TOKEN")
    dry_run = os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}

    if dry_run:
        print("DRY_RUN enabled. Post not published.")
        print(message)
        return {"dry_run": True, "message": message}

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/feed"
    response = requests.post(
        url,
        data={"message": message, "access_token": page_access_token},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    target_date = today_in_rome()
    if override := os.getenv("POST_DATE"):
        target_date = dt.datetime.strptime(override, "%Y-%m-%d").date()

    events = fetch_wikipedia_events(target_date)
    selected = select_events(events)
    rewritten = rewrite_with_gemini(selected, target_date)
    message = append_sources(rewritten, selected)
    result = publish_to_facebook(message)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
