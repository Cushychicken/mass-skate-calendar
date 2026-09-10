from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scraper.sources import HalixCalendarSource, ICalendarSource, MyRecCalendarSource, MyRecProgramSource

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "data" / "events.json"

SOURCES = [
    MyRecCalendarSource(
        name="LoConte Rink",
        city="Medford",
        address="97 Locust St, Medford, MA",
        url="https://medfordma.myrec.com/info/calendar/mobile.aspx?FacilityID=14780&AreaID=0",
        location_value="14780,0",
        page_url="https://medfordma.myrec.com/info/calendar/default.aspx?FacilityID=14780",
    ),
    MyRecProgramSource(name="Viglirolo Rink", city="Belmont", address="10 Concord Ave, Belmont, MA", urls=["https://belmontma.myrec.com/info/activities/program_details.aspx?ProgramID=30231", "https://belmontma.myrec.com/info/activities/program_details.aspx?ProgramID=29877"]),
    ICalendarSource(
        name="Stoneham Arena",
        city="Stoneham",
        address="101 Montvale Ave, Stoneham, MA",
        feed_url="https://www.stoneham-ma.gov/common/modules/iCalendar/iCalendar.aspx?catID=26&feed=calendar",
        page_url="https://www.stoneham-ma.gov/calendar.aspx?CID=26",
        headers={"User-Agent": "Mozilla/5.0 (compatible; MassSkateCalendar/1.0)"},
    ),
    HalixCalendarSource(
        name="Cronin Rink",
        city="Revere",
        address="870 Revere Beach Pkwy, Revere, MA",
        base_url="https://fmc.myhalix.io",
        page_url="https://fmc.myhalix.io/pages/publicskatingcalendars.revere",
        sandbox_key="sbx~00~300",
        scope_element_id="business",
        scope_key="biz~00~-wcAAAAAAAA~AQA",
        resource_key="sre~fc~fmcns~10ice",
    ),
]


def load_previous() -> dict:
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"events": [], "sources": []}


def main() -> int:
    today = date.today()
    horizon = today + timedelta(days=int(os.getenv("SKATE_CALENDAR_DAYS", "90")))
    previous = load_previous()
    old_by_rink = {}
    for event in previous.get("events", []):
        old_by_rink.setdefault(event.get("rink"), []).append(event)

    events, statuses = [], []
    failures = 0
    for source in SOURCES:
        try:
            fresh = [event.to_dict() for event in source.fetch(today, horizon)]
            events.extend(fresh)
            statuses.append({"rink": source.name, "ok": True, "event_count": len(fresh), "stale": False})
        except Exception as exc:  # isolate unreliable third-party sites
            failures += 1
            now = datetime.now(timezone.utc)
            retained = []
            for event in old_by_rink.get(source.name, []):
                try:
                    if datetime.fromisoformat(event["end"]).astimezone(timezone.utc) >= now:
                        retained.append(event)
                except (KeyError, TypeError, ValueError):
                    continue
            events.extend(retained)
            statuses.append({"rink": source.name, "ok": False, "event_count": len(retained), "stale": bool(retained), "error": f"{type(exc).__name__}: {exc}"})

    unique = {event["id"]: event for event in events}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "range": {"start": today.isoformat(), "end": horizon.isoformat()},
        "sources": statuses,
        "events": sorted(unique.values(), key=lambda event: (event["start"], event["rink"])),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['events'])} events; {failures} source failures")
    return 1 if failures == len(SOURCES) else 0


if __name__ == "__main__":
    raise SystemExit(main())
