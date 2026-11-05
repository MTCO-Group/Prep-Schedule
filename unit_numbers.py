r"""
Prep Schedule unit numbers
Version 1.1

1.1: past days too. Nathan, 05/11/2026: "On the prep schedule i'd like the
numbers to show on previous days too please", the last 4 weeks. The
Discrepancy Check 4.9 adds "delivered" to each contract: every unit line
carrying a fleet number, whatever its status, with its delivery date. A past
On Hire job's units take the numbers delivered on that contract on that day,
of their type, a matching configuration first. A past unit never shows
"[Not Picked]": with no number in MCS it shows nothing. This part is the
Prep Schedule's own (the planner only plans units still to go), so it has
no copy in the planner to keep in step with.

1.0: the MCS fleet number of each On Hire unit, or "[Not Picked]", on the Prep
Schedule's job panel and week chips. Nathan, 04/11/2026: the numbers showed
on the Production Planner "but not on the prep schedule".

The facts come from data/unit_numbers.json beside jobs.json, written by the
Prep Schedule MCS Discrepancy Check (4.8): each contract's Unposted MCS unit
lines. The rules that turn those lines into a label per unit are the
Production Planner's, in the Kensite Yard App's shared/src/production.ts
(mcsContract, parseUnitFeed, matchFleet, feedIsFresh, expandPrepJobs). This
file is a line-for-line port so the two apps always give a unit the same
label: KEEP THE TWO IN STEP, and port the planner's tests with any change
(Unit Numbers Offline Test.py beside this file).
"""
import html
import re
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _UK = ZoneInfo("Europe/London")
except Exception:                                    # noqa: BLE001  (no tz database)
    _UK = None

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FEED_FRESH = timedelta(hours=2)
PAST_DAYS = 28        # 1.1: past days shown; the Discrepancy Check's PAST_DAYS covers the same


def _text(v):
    return str(v).strip() if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""


def _norm(s):
    return " ".join(str(s).strip().lower().split())


def _count(v):
    try:
        n = int(float(v))
    except (TypeError, ValueError, OverflowError):
        return 0
    return n if n > 0 else 0


def mcs_contract(ref):
    """The MCS contract a Prep Schedule reference means: digits zero-padded to
    10, without a #1 split suffix, or "" (planner: mcsContract)."""
    base = re.sub(r"\s*#\s*\d{1,2}\s*$", "", str(ref or "").strip())
    digits = re.sub(r"\D", "", base)
    return digits.zfill(10) if digits and len(digits) <= 10 else ""


def _feed_line(v):
    if not isinstance(v, dict) or not isinstance(v.get("type"), str) or not v["type"] \
            or not isinstance(v.get("config"), str) or not (v.get("fleet") is None or isinstance(v.get("fleet"), str)) \
            or not isinstance(v.get("delivery"), str) or _count(v.get("qty")) == 0:
        return None
    return {"type": v["type"], "config": v["config"], "fleet": v["fleet"], "qty": _count(v["qty"]),
            "delivery": v["delivery"]}


def _delivered_line(v):
    if not isinstance(v, dict) or not isinstance(v.get("type"), str) or not v["type"] \
            or not isinstance(v.get("config"), str) or not isinstance(v.get("fleet"), str) or not v["fleet"] \
            or not isinstance(v.get("delivery"), str):
        return None
    return {"type": v["type"], "config": v["config"], "fleet": v["fleet"], "delivery": v["delivery"]}


def parse_unit_feed(raw):
    """The feed file checked, or None (planner: parseUnitFeed)."""
    if not isinstance(raw, dict) or not isinstance(raw.get("written_at"), str) or not isinstance(raw.get("contracts"), dict):
        return None
    contracts = {}
    for key, v in raw["contracts"].items():
        if not isinstance(v, dict) or not isinstance(v.get("lines"), list):
            continue
        lines = [ln for ln in (_feed_line(x) for x in v["lines"]) if ln is not None]
        entry = {"read_at": v["read_at"] if isinstance(v.get("read_at"), str) else "", "lines": lines}
        if isinstance(v.get("delivered"), list):         # 1.1, written by the Discrepancy Check 4.9
            entry["delivered"] = [d for d in (_delivered_line(x) for x in v["delivered"]) if d is not None]
        contracts[str(key).strip()] = entry
    out = {"written_at": raw["written_at"]}
    if isinstance(raw.get("source"), str):
        out["source"] = raw["source"]
    out["contracts"] = contracts
    return out


def match_fleet(cards, feed):
    """{card id: fleet number, or None (not picked)}; a card Ken does not know
    about is left out (planner: matchFleet). cards are dicts with id, contract,
    unit, config and delivery, in job_cards order."""
    contracts = {}
    for ref, v in (feed or {}).get("contracts", {}).items():
        c = mcs_contract(ref)
        if c and c not in contracts:
            contracts[c] = v
    groups = {}
    for u in cards:
        contract = mcs_contract(u["contract"])
        entry = contracts.get(contract) if contract else None
        if not entry:
            continue
        gid = (contract, u["unit"])
        if gid not in groups:
            slots = []
            for ln in entry["lines"]:
                if ln["type"] != u["unit"]:
                    continue
                for _ in range(1 if ln["fleet"] else ln["qty"]):
                    slots.append({"fleet": ln["fleet"], "config": _norm(ln["config"]),
                                  "delivery": ln["delivery"], "used": False})
            groups[gid] = (slots, [])
        groups[gid][1].append(u)
    out = {}
    for slots, group in groups.values():
        if not slots:
            continue                      # no line of this type on the contract: Ken does not know
        got = {}

        def take(u, fits):
            s = next((x for x in slots if not x["used"] and fits(x) and x["delivery"] == u["delivery"]), None) \
                or next((x for x in slots if not x["used"] and fits(x)), None)
            if s:
                s["used"] = True
                got[u["id"]] = s

        for u in group:
            if u["config"]:
                take(u, lambda s, c=_norm(u["config"]): s["config"] == c)
        for u in group:
            if u["id"] not in got:
                take(u, lambda s: True)
        for u in group:
            out[u["id"]] = got[u["id"]]["fleet"] if u["id"] in got else None
    return out


def _uk(dt):
    d = dt.astimezone(_UK) if _UK else dt.astimezone(timezone.utc)
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M"), d.weekday() < 5


def uk_date(now):
    """Today's date in the UK, "YYYY-MM-DD" (planner: ukToday). The Streamlit
    server runs on UTC, which is a day behind between midnight and 01:00 BST."""
    return _uk(now)[0]


def _weekday_before(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    while True:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            return d.strftime("%Y-%m-%d")


def feed_is_fresh(written_at, now):
    """Can "[Not Picked]" be trusted? (planner: feedIsFresh). now is an aware datetime."""
    try:
        t = datetime.fromisoformat(str(written_at).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    if t > now + timedelta(minutes=5):
        return False
    if now - t < FEED_FRESH:
        return True
    n_date, n_time, n_weekday = _uk(now)
    if n_weekday and "09:30" <= n_time < "17:00":
        return False
    day = n_date if n_weekday and n_time >= "17:00" else _weekday_before(n_date)
    w_date, w_time, _ = _uk(t)
    return f"{w_date} {w_time}" >= f"{day} 16:00"


def _configs_for(job, unit, qty, av_units):
    out = []
    all_cfgs = job.get("av_configs") if isinstance(job.get("av_configs"), dict) else {}
    cfgs = all_cfgs.get(unit) if unit in av_units and isinstance(all_cfgs.get(unit), dict) else {}
    for config, n in cfgs.items():
        for _ in range(_count(n)):
            if len(out) >= qty:
                break
            out.append(str(config).strip())
    while len(out) < qty:
        out.append("")
    return out


def job_cards(jobs, today, asset_units, av_units, since=None):
    """One card per asset for every On Hire job dated today or later, in the
    planner's order (planner: expandPrepJobs). Each card carries the job's
    (date, index) so the Prep Schedule can find its labels. 1.1: since (a
    date before today) takes past jobs from that date too."""
    since = since or today
    cards = []
    for dk in sorted(jobs or {}):
        day = jobs[dk]
        if not _DATE.match(dk) or dk < since or not isinstance(day, list):
            continue
        for ji, job in enumerate(day):
            if not isinstance(job, dict) or job.get("type") != "On Hire" or not isinstance(job.get("units"), dict):
                continue
            for unit, qty in job["units"].items():
                if unit not in asset_units:
                    continue
                for k, config in enumerate(_configs_for(job, unit, _count(qty), av_units)):
                    cards.append({"id": (dk, ji, unit, k), "dk": dk, "ji": ji, "contract": _text(job.get("contract_number")),
                                  "unit": unit, "config": config, "delivery": dk})
    return cards


def match_delivered(cards, feed):
    """1.1: {card id: fleet number} for past cards, from each contract's
    delivered list: the numbers delivered on that MCS contract, of the card's
    type, on the card's own delivery date, a matching configuration first.
    A card with no such number is left out: a past unit is never "not picked"."""
    delivered = {}
    for ref, v in (feed or {}).get("contracts", {}).items():
        c = mcs_contract(ref)
        if c and c not in delivered and isinstance(v.get("delivered"), list):
            delivered[c] = v["delivered"]
    groups = {}
    for u in cards:
        contract = mcs_contract(u["contract"])
        if not contract or contract not in delivered:
            continue
        gid = (contract, u["unit"], u["delivery"])
        if gid not in groups:
            slots = [{"fleet": d["fleet"], "config": _norm(d["config"]), "used": False}
                     for d in delivered[contract] if d["type"] == u["unit"] and d["delivery"] == u["delivery"]]
            groups[gid] = (slots, [])
        groups[gid][1].append(u)
    out = {}
    for slots, group in groups.values():
        def take(u, fits):
            s = next((x for x in slots if not x["used"] and fits(x)), None)
            if s:
                s["used"] = True
                out[u["id"]] = s["fleet"]
        for u in group:
            if u["config"]:
                take(u, lambda s, c=_norm(u["config"]): s["config"] == c)
        for u in group:
            if u["id"] not in out:
                take(u, lambda s: True)
    return out


def labels_by_job(jobs, feed, now, today, asset_units, av_units, past_days=PAST_DAYS):
    """{(date, job index): [(unit, config, fleet number or None)]} in card
    order. A fleet number always shows; None ("[Not Picked]") only while the
    feed is fresh and only from today on; a unit Ken does not know about is
    left out. 1.1: past jobs from past_days ago show what was delivered."""
    if not feed:
        return {}
    since = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=past_days)).strftime("%Y-%m-%d")
    every = job_cards(jobs, today, asset_units, av_units, since=since)
    cards = [c for c in every if c["dk"] >= today]
    fleet = match_fleet(cards, feed)
    fleet.update(match_delivered([c for c in every if c["dk"] < today], feed))
    fresh = feed_is_fresh(feed.get("written_at", ""), now)
    out = {}
    for c in every:
        if c["id"] not in fleet:
            continue
        f = fleet[c["id"]]
        if f is None and not fresh:
            continue
        out.setdefault((c["dk"], c["ji"]), []).append((c["unit"], c["config"], f))
    return out


def _tag(fleet):
    if fleet:
        return f"<span class='yb-fleet'>[{html.escape(fleet)}]</span>"
    return "<span class='yb-fleet yb-fleet-np'>[Not Picked]</span>"


def chip_html(labels):
    """The week chip's compact line: picked numbers, then one red count."""
    if not labels:
        return ""
    picked = [_tag(f) for _u, _c, f in labels if f]
    missing = sum(1 for _u, _c, f in labels if not f)
    if missing:
        picked.append("<span class='yb-fleet yb-fleet-np'>[Not Picked"
                      + (f" ×{missing}" if missing > 1 else "") + "]</span>")
    return "<div class='yb-fleets'>" + " ".join(picked) + "</div>"


def unit_cell_html(labels):
    """The job panel's cell for one unit type: each configured AV as
    "Office [8224]", other units as their numbers then one red count."""
    if not labels:
        return ""
    if any(c for _u, c, _f in labels):
        return " · ".join(f"{html.escape(c)} {_tag(f)}" if c else _tag(f) for _u, c, f in labels)
    picked = [_tag(f) for _u, _c, f in labels if f]
    missing = sum(1 for _u, _c, f in labels if not f)
    if missing:
        picked.append("<span class='yb-fleet yb-fleet-np'>[Not Picked"
                      + (f" ×{missing}" if missing > 1 else "") + "]</span>")
    return " ".join(picked)
