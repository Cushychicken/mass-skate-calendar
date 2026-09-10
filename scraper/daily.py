from __future__ import annotations

from scraper import run
from scraper.sources import FinnlySource


run.SOURCES.append(
    FinnlySource(
        name="Warrior Ice Arena",
        city="Boston",
        address="90 Guest St, Boston, MA",
        url="https://warrior.finnlyconnect.com/schedule/20",
    )
)


if __name__ == "__main__":
    raise SystemExit(run.main())
