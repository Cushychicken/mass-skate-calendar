from datetime import date

from scraper.sources import CivicPlusSource, MyRecCalendarSource


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

