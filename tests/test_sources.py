from datetime import date

from scraper.sources import CivicPlusSource, FinnlySource, MyRecCalendarSource


def test_myrec_calendar_parser():
    html = """<table class='styled'><tr class='trTitle left'><td colspan='3'>Thursday October 1, 2026</td></tr><tr><td>9:00 AM - 10:50 AM</td><td>Public Skate</td><td></td></tr></table>"""
    source = MyRecCalendarSource(name="Rink", city="Town", address="1 Main", url="https://example.com", location_value="1,2")
    events = source.parse(html)
    assert len(events) == 1
    assert events[0].kind == "public_skate"
    assert events[0].start.date() == date(2026, 10, 1)


def test_civicplus_parser():
    html = """<li><h3><a id='eventTitle_1' href='/Calendar.aspx?EID=1'><span>ADULT STICK PRACTICE</span></a></h3><div class='subHeader'><div class='date'>September 10, 2026, 12:00 PM - 1:45 PM</div></div><div itemscope itemtype='http://schema.org/Event'><span itemprop='name'>ADULT STICK PRACTICE</span><span itemprop='startDate'>2026-09-10T12:00:00</span></div></li>"""
    source = CivicPlusSource(name="Rink", city="Town", address="1 Main", base_url="https://example.com/calendar.aspx", calendar_id=1)
    events = source.parse(html)
    assert len(events) == 1
    assert events[0].kind == "stick_puck"
    assert events[0].end.hour == 13


def test_finnly_parser():
    html = '''<script>_onlineScheduleList = [{"EventStartTime":"2026-09-12T12:30:00","EventEndTime":"2026-09-12T13:50:00","EventTypeName":"Public Skating","Description":"Weekend session","Closed":false},{"EventStartTime":"2026-09-13T08:30:00","EventEndTime":"2026-09-13T09:20:00","EventTypeName":"Public Hockey","Description":"Drop-in","Closed":false}];</script>'''
    source = FinnlySource(name="Warrior", city="Boston", address="90 Guest", url="https://example.com")
    events = source.parse(html, date(2026, 9, 1), date(2026, 9, 30))
    assert [event.kind for event in events] == ["public_skate", "stick_puck"]
