"""Filtering incidents by the date they occurred."""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def day_range(y, m, d):
    start = datetime(y, m, d, tzinfo=IST)
    return start.isoformat(), (start + timedelta(days=1) - timedelta(microseconds=1)).isoformat()


def make(make_incident, when, title):
    return make_incident(occurred_at=when.isoformat(), title=title)


def test_one_day_on_both_lists(client, auth, make_incident):
    # 10 Nov early morning IST is still 9 Nov in UTC: the day must follow local time
    make(make_incident, datetime(2026, 11, 10, 0, 30, tzinfo=IST), "Just after midnight 10 Nov")
    make(make_incident, datetime(2026, 11, 10, 23, 50, tzinfo=IST), "Late evening 10 Nov")
    make(make_incident, datetime(2026, 11, 9, 23, 50, tzinfo=IST), "Late evening 9 Nov")
    make(make_incident, datetime(2026, 11, 11, 0, 10, tzinfo=IST), "Just after midnight 11 Nov")
    start, end = day_range(2026, 11, 10)

    officer = client.get("/api/incidents", params={"date_from": start, "date_to": end}, headers=auth("officer")).json()
    assert sorted(i["title"] for i in officer["items"]) == ["Just after midnight 10 Nov", "Late evening 10 Nov"]

    admin = client.get("/api/admin/incidents", params={"date_from": start, "date_to": end}, headers=auth("admin")).json()
    assert admin["total"] == 2
    assert sum(admin["colour_totals"].values()) == 2  # totals follow the date filter too


def test_reporter_date_filter_still_only_own(client, auth, make_incident):
    make(make_incident, datetime(2026, 11, 10, 9, 0, tzinfo=IST), "Mine on 10 Nov")
    start, end = day_range(2026, 11, 10)
    assert client.get("/api/incidents", params={"date_from": start, "date_to": end},
                      headers=auth("reporter2")).json()["total"] == 0
    assert client.get("/api/incidents", params={"date_from": start, "date_to": end},
                      headers=auth("reporter")).json()["total"] == 1


def test_date_filter_combines_with_other_filters(client, auth, make_incident):
    make_incident(occurred_at=datetime(2026, 11, 10, 9, 0, tzinfo=IST).isoformat(), category="turbulence",
                  title="Turbulence on 10 Nov")
    make(make_incident, datetime(2026, 11, 10, 10, 0, tzinfo=IST), "Bird strike on 10 Nov")
    start, end = day_range(2026, 11, 10)
    r = client.get("/api/incidents", params={"date_from": start, "date_to": end, "category": "turbulence"},
                   headers=auth("officer")).json()
    assert [i["title"] for i in r["items"]] == ["Turbulence on 10 Nov"]


def test_empty_day(client, auth, make_incident):
    make(make_incident, datetime(2026, 11, 10, 9, 0, tzinfo=IST), "On 10 Nov")
    start, end = day_range(2026, 11, 12)
    assert client.get("/api/incidents", params={"date_from": start, "date_to": end},
                      headers=auth("officer")).json()["total"] == 0


def test_bad_ranges_rejected(client, auth, users):
    start, end = day_range(2026, 11, 10)
    h = auth("officer")
    assert client.get("/api/incidents", params={"date_from": end, "date_to": start}, headers=h).status_code == 422
    assert client.get("/api/incidents", params={"date_from": "2026-11-10T00:00:00"}, headers=h).status_code == 422
    assert client.get("/api/admin/incidents", params={"date_from": end, "date_to": start},
                      headers=auth("admin")).status_code == 422
