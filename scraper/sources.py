from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from icalendar import Calendar

TZ = ZoneInfo("America/New_York")
TIME_RANGE = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(\d{1,2}:\d{2}\s*[AP]M)", re.I)


@dataclass(frozen=True)
class Event:
    rink: str
    city: str
    address: str
    kind: str
    title: str
    start: datetime
    end: datetime
    source_url: str
    notes: str = ""

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["start"] = self.start.isoformat()
        payload["end"] = self.end.isoformat()
        payload["id"] = hashlib.sha1(
            f"{self.rink}|{self.kind}|{payload['start']}|{self.title}".encode()
        ).hexdigest()[:16]
        return payload


def classify(title: str) -> str | None:
    value = " ".join(title.lower().replace("&", "and").split())
    if any(term in value for term in ("stick and puck", "stick practice", "stick time", "open hockey", "public hockey")):
        return "stick_puck"
    if "public skating" in value or "public skate" in value:
        return "public_skate"
    return None


def localize(value: datetime) -> datetime:
    return value.replace(tzinfo=TZ) if value.tzinfo is None else value.astimezone(TZ)


def parse_local_range(day: date, text: str) -> tuple[datetime, datetime]:
    match = TIME_RANGE.search(" ".join(text.split()))
    if not match:
        raise ValueError(f"No time range in {text!r}")
    start_t = datetime.strptime(match.group(1).upper().replace(" ", ""), "%I:%M%p").time()
    end_t = datetime.strptime(match.group(2).upper().replace(" ", ""), "%I:%M%p").time()
    start = datetime.combine(day, start_t, TZ)
    end = datetime.combine(day, end_t, TZ)
    if end <= start:
        end += timedelta(days=1)
    return start, end


class MyRecCalendarSource:
    def __init__(self, *, name: str, city: str, address: str, url: str, location_value: str):
        self.name, self.city, self.address = name, city, address
        self.url, self.location_value = url, location_value

    def fetch(self, start: date, end: date) -> list[Event]:
        session = requests.Session()
        response = session.get(self.url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        form = {
            field["name"]: field.get("value", "")
            for field in soup.select('input[type="hidden"][name]')
        }
        form.update(
            {
                "ctl00$Content$ddlLocation": self.location_value,
                "ctl00$Content$txtStartDate": start.strftime("%m/%d/%Y"),
                "ctl00$Content$txtEndDate": end.strftime("%m/%d/%Y"),
                "ctl00$Content$btnSubmit": "Go",
            }
        )
        response = session.post(self.url, data=form, timeout=30)
        response.raise_for_status()
        return self.parse(response.text)

    def parse(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        for table in soup.select("table.styled"):
            header = table.select_one("tr.trTitle")
            if not header:
                continue
            try:
                day = date_parser.parse(header.get_text(" ", strip=True), fuzzy=True).date()
            except (ValueError, OverflowError):
                continue
            for row in table.select("tr"):
                cells = row.find_all("td", recursive=False)
                if len(cells) < 2:
                    continue
                time_text = cells[0].get_text(" ", strip=True)
                title = cells[1].get_text(" ", strip=True)
                kind = classify(title)
                if not kind or not TIME_RANGE.search(time_text):
                    continue
                event_start, event_end = parse_local_range(day, time_text)
                events.append(Event(self.name, self.city, self.address, kind, title, event_start, event_end, self.url))
        return events


class MyRecProgramSource:
    def __init__(self, *, name: str, city: str, address: str, urls: Iterable[str]):
        self.name, self.city, self.address, self.urls = name, city, address, list(urls)

    def fetch(self, _start: date, _end: date) -> list[Event]:
        events: list[Event] = []
        for url in self.urls:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for row in soup.select("tr"):
                activity = row.select_one('td[data-title="Activity"]')
                when = row.select_one('td[data-title="Date/Time"]')
                if not activity or not when:
                    continue
                title = activity.get_text(" ", strip=True)
                kind = classify(title)
                text = when.get_text(" ", strip=True)
                date_match = re.search(r"\d{2}/\d{2}/\d{4}", text)
                if not kind or not date_match:
                    continue
                day = datetime.strptime(date_match.group(), "%m/%d/%Y").date()
                event_start, event_end = parse_local_range(day, text)
                fees = row.select_one('td[data-title="Fees"]')
                notes = fees.get_text(" ", strip=True) if fees else ""
                events.append(Event(self.name, self.city, self.address, kind, title, event_start, event_end, url, notes))
        return events


class FinnlySource:
    def __init__(self, *, name: str, city: str, address: str, url: str):
        self.name, self.city, self.address, self.url = name, city, address, url

    def fetch(self, start: date, end: date) -> list[Event]:
        response = requests.get(
            self.url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MassSkateCalendar/1.0)"},
            timeout=30,
        )
        response.raise_for_status()
        return self.parse(response.text, start, end)

    def parse(self, html: str, start: date, end: date) -> list[Event]:
        match = re.search(r"_onlineScheduleList\s*=\s*(\[.*?\]);", html, re.S)
        if not match:
            raise ValueError("Finnly schedule data was not found")
        events: list[Event] = []
        for item in json.loads(match.group(1)):
            title = str(item.get("EventTypeName", "")).strip()
            kind = classify(title)
            if not kind or item.get("Closed"):
                continue
            event_start = localize(datetime.fromisoformat(item["EventStartTime"]))
            event_end = localize(datetime.fromisoformat(item["EventEndTime"]))
            if start <= event_start.date() <= end:
                notes = str(item.get("Description", "")).strip()
                events.append(Event(self.name, self.city, self.address, kind, title, event_start, event_end, self.url, notes))
        return events


class CivicPlusSource:
    def __init__(self, *, name: str, city: str, address: str, base_url: str, calendar_id: int):
        self.name, self.city, self.address = name, city, address
        self.base_url, self.calendar_id = base_url, calendar_id
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MassSkateCalendar/1.0; +https://github.com/Cushychicken/mass-skate-calendar)"
        }

    def fetch(self, start: date, end: date) -> list[Event]:
        months = {(start.year, start.month), (end.year, end.month)}
        cursor = date(start.year, start.month, 1)
        while cursor <= end:
            months.add((cursor.year, cursor.month))
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        found: dict[str, Event] = {}
        successful_months = 0
        last_error: Exception | None = None
        for year, month in sorted(months):
            try:
                params = {"CID": self.calendar_id, "month": month, "year": year, "day": 1, "calType": 0}
                response = requests.get(self.base_url, params=params, headers=self.headers, timeout=20)
                response.raise_for_status()
                successful_months += 1
                for event in self.parse(response.text):
                    if start <= event.start.date() <= end:
                        found[event.to_dict()["id"]] = event
            except requests.RequestException as exc:
                last_error = exc
                if (year, month) == (start.year, start.month):
                    try:
                        response = requests.get(
                            self.base_url,
                            params={"CID": self.calendar_id},
                            headers=self.headers,
                            timeout=20,
                        )
                        response.raise_for_status()
                        successful_months += 1
                        for event in self.parse(response.text):
                            if start <= event.start.date() <= end:
                                found[event.to_dict()["id"]] = event
                    except requests.RequestException as fallback_exc:
                        last_error = fallback_exc
        if not successful_months and last_error:
            raise last_error
        return list(found.values())

    def parse(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        for schema in soup.select('[itemscope][itemtype$="/Event"]'):
            title_node = schema.select_one('[itemprop="name"]')
            start_node = schema.select_one('[itemprop="startDate"]')
            if not title_node or not start_node:
                continue
            title = title_node.get_text(" ", strip=True)
            kind = classify(title)
            if not kind:
                continue
            event_start = localize(datetime.fromisoformat(start_node.get_text(strip=True)))
            parent = schema.parent
            date_text = parent.select_one(".subHeader .date") if parent else None
            try:
                _, event_end = parse_local_range(event_start.date(), date_text.get_text(" ", strip=True))
            except (ValueError, AttributeError):
                event_end = event_start + timedelta(hours=2)
            link = parent.select_one('a[id^="eventTitle_"]') if parent else None
            source_url = urljoin(self.base_url, link.get("href", "")) if link else self.base_url
            description = schema.select_one('[itemprop="description"]')
            notes = description.get_text(" ", strip=True) if description else ""
            events.append(Event(self.name, self.city, self.address, kind, title, event_start, event_end, source_url, notes))
        return events


class ICalendarSource:
    def __init__(self, *, name: str, city: str, address: str, feed_url: str, page_url: str, headers: dict[str, str] | None = None):
        self.name, self.city, self.address = name, city, address
        self.feed_url, self.page_url = feed_url, page_url
        self.headers = headers or {}

    def fetch(self, start: date, end: date) -> list[Event]:
        response = requests.get(self.feed_url, headers=self.headers, timeout=30)
        response.raise_for_status()
        calendar = Calendar.from_ical(response.content)
        events: list[Event] = []
        for item in calendar.walk("VEVENT"):
            title = str(item.get("summary", "")).strip()
            kind = classify(title)
            if not kind:
                continue
            raw_start = item.decoded("dtstart")
            raw_end = item.decoded("dtend") if item.get("dtend") else raw_start + timedelta(hours=2)
            event_start = localize(datetime.combine(raw_start, time.min) if isinstance(raw_start, date) and not isinstance(raw_start, datetime) else raw_start)
            event_end = localize(datetime.combine(raw_end, time.min) if isinstance(raw_end, date) and not isinstance(raw_end, datetime) else raw_end)
            if start <= event_start.date() <= end:
                events.append(Event(self.name, self.city, self.address, kind, title, event_start, event_end, self.page_url, str(item.get("description", ""))))
        return events
