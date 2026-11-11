#!/usr/bin/env python3
"""Job Radar: collects jobs, finds new ones, emails you, rebuilds the dashboard.

Sources: Bundesagentur für Arbeit job board (official public API) and, optionally, Adzuna.
Run by GitHub Actions every 12 hours. State lives in data/jobs.json.
"""
import base64
import html
import json
import os
import re
import smtplib
import ssl
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import requests

import config

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "data" / "jobs.json"
DASH_FILE = ROOT / "docs" / "index.html"
NOW = datetime.now(timezone.utc)
NOW_ISO = NOW.isoformat(timespec="seconds")

BA_BASES = [
    "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4",
    "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6",
]
DETAIL_BASE = BA_BASES[0]
DETAIL_CAP = 150          # max job-detail requests per run (used to read the description / language)
PAUSE = 0.35              # seconds between requests, to be polite

S = requests.Session()
S.headers.update({"X-API-Key": "jobboerse-jobsuche", "User-Agent": "Mozilla/5.0 (personal job alert)"})
_ba_base = None
_requests_ok = 0


def log(*a):
    print(*a, flush=True)


def http_json(url, params=None, tries=3):
    global _requests_ok
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=30)
            if r.status_code == 200:
                _requests_ok += 1
                time.sleep(PAUSE)
                return r.json()
            if r.status_code in (400, 404):
                return None
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 * (i + 1))
    return None


# ---------------------------------------------------------------- Bundesagentur
def ba_search(was, wo=None, umkreis=None, pages=2):
    """Return raw 'stellenangebote' items for one query."""
    global _ba_base
    out = []
    for page in range(1, pages + 1):
        params = {"was": was, "page": page, "size": 100, "veroeffentlichtseit": config.DAYS_BACK}
        if wo:
            params["wo"] = wo
        if umkreis is not None:
            params["umkreis"] = umkreis
        data = None
        for base in ([_ba_base] if _ba_base else BA_BASES):
            data = http_json(base + "/jobs", params)
            if data is not None:
                _ba_base = base
                break
        if not data:
            break
        items = data.get("stellenangebote") or []
        out += items
        if len(items) < 100:
            break
    return out


def parse_ba(it):
    ort = it.get("arbeitsort") or {}
    ref = it.get("refnr")
    if not ref:
        return None
    return {
        "id": "ba:" + ref,
        "ref": ref,
        "title": (it.get("titel") or it.get("beruf") or "").strip(),
        "company": (it.get("arbeitgeber") or "").strip(),
        "location": ", ".join(x for x in [ort.get("ort"), ort.get("region")] if x),
        "region": ort.get("region") or "",
        "url": "https://www.arbeitsagentur.de/jobsuche/jobdetail/" + ref,
        "posted": it.get("aktuelleVeroeffentlichungsdatum") or "",
        "source": "Bundesagentur für Arbeit",
    }


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def ba_detail_text(ref):
    enc = urllib.parse.quote(base64.b64encode(ref.encode()).decode(), safe="")
    d = http_json(f"{DETAIL_BASE}/jobdetails/{enc}")
    return " ".join(strings(d)) if d else None


# ---------------------------------------------------------------- Adzuna (optional)
def adzuna_search(what, where=None, pages=2):
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        return []
    out = []
    for page in range(1, pages + 1):
        params = {"app_id": app_id, "app_key": app_key, "what": what, "results_per_page": 50,
                  "sort_by": "date", "max_days_old": config.DAYS_BACK}
        if where:
            params["where"] = where
        data = http_json(f"https://api.adzuna.com/v1/api/jobs/de/search/{page}", params)
        if not data:
            break
        res = data.get("results") or []
        out += res
        if len(res) < 50:
            break
    return out


def parse_adzuna(it):
    loc = it.get("location") or {}
    area = loc.get("area") or []
    region = next((a for a in area if "baden" in a.lower()), area[1] if len(area) > 1 else "")
    return {
        "id": "az:" + str(it.get("id")),
        "title": (it.get("title") or "").strip(),
        "company": ((it.get("company") or {}).get("display_name") or "").strip(),
        "location": loc.get("display_name") or "",
        "region": region,
        "url": it.get("redirect_url") or "",
        "posted": (it.get("created") or "")[:10],
        "snippet": it.get("description") or "",
        "source": "Adzuna",
    }


# ---------------------------------------------------------------- helpers
GER = set("und der die das für mit wir sie ist nicht ein eine bei auf von zu im den deine ihre du dein ihr oder als auch werden".split())
ENG = set("and the for with we you are is of to in your our will a an on as or be have".split())


def detect_lang(text, title=""):
    words = re.findall(r"[a-zäöüß]+", text.lower())
    g = sum(w in GER for w in words)
    e = sum(w in ENG for w in words)
    if g + e >= 8:
        return "de" if g > e else "en"
    t = title.lower()
    if "working student" in t and "werkstudent" not in t:
        return "en"
    return "de" if re.search(r"werkstud|\(m/w/d\)|\(w/m/d\)", t) else "en"


def dkey(j):
    n = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    city = j["location"].split(",")[0]
    return n(j["company"])[:25] + "|" + n(j["title"])[:50] + "|" + n(city)


def is_watch(company):
    return any(re.search(r"\b" + re.escape(w) + r"\b", company, re.I) for w in config.WATCH_COMPANIES)


def match_topics(title):
    return [name for name, rx in config.TOPICS if re.search(rx, title, re.I)]


def in_bw(j):
    return (not j["region"]) or "baden" in j["region"].lower()


# ---------------------------------------------------------------- candidate collection
def collect_ws():
    cands = {}

    def add(items, parser):
        for it in items:
            j = parser(it)
            if j:
                cands[j["id"]] = j

    queries = [("Werkstudent", 4), ("Working Student", 4)]
    queries += [(f"{p} {t}", 2) for t in config.QUERY_TOPICS for p in ("Werkstudent", "Working Student")]
    queries += [(f"Werkstudent {c}", 1) for c in config.WATCH_COMPANIES]

    # does searching by the state name work? If not, fall back to a list of cities.
    probe = ba_search("Werkstudent", wo="Baden-Württemberg", pages=1)
    use_cities = len(probe) == 0
    if use_cities:
        log("State-wide search returned nothing; using the city fallback.")
        queries = queries[:2]
    else:
        add(probe, parse_ba)

    for was, pages in queries:
        if use_cities:
            for city in config.BW_CITIES:
                add(ba_search(was, wo=city, umkreis=25, pages=pages), parse_ba)
        else:
            add(ba_search(was, wo="Baden-Württemberg", pages=pages), parse_ba)
    log(f"Bundesagentur: {len(cands)} working-student candidates")

    az = 0
    for was, pages in queries[:len(config.QUERY_TOPICS) * 2 + 2]:
        for it in adzuna_search(was, where="Baden-Württemberg", pages=1):
            j = parse_adzuna(it)
            if j["url"]:
                cands.setdefault(j["id"], j)
                az += 1
    if az:
        log(f"Adzuna: {az} extra candidates")
    return cands


def collect_trax():
    cands = {}
    for q in config.TRAX_QUERIES:
        for it in ba_search(q, pages=2):
            j = parse_ba(it)
            if j:
                cands[j["id"]] = j
        for it in adzuna_search(q, pages=1):
            j = parse_adzuna(it)
            if j["url"]:
                cands.setdefault(j["id"], j)
    log(f"TRAX search: {len(cands)} candidates")
    return cands


def classify_trax(j, text):
    t = f"{j['title']} {text}"
    if re.search(r"\btrax\b", t, re.I) and re.search(config.TRAX_CONTEXT, t, re.I):
        return "strong"
    fis = re.search(config.FIS_EMPLOYER_RE, j["company"], re.I)
    if fis and re.search(config.TRAX_RELATED, t, re.I):
        return "related"
    if re.search(r"\bechos\b", t, re.I) and re.search(r"swift|fis\b|payment", t, re.I):
        return "related"
    return None


# ---------------------------------------------------------------- state
def load_state():
    try:
        s = json.loads(STATE_FILE.read_text("utf-8"))
    except (OSError, ValueError):
        s = {}
    s.setdefault("jobs", {})
    s.setdefault("rejected", [])
    s.setdefault("meta", {})
    return s


def save_state(s):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1), "utf-8")


# ---------------------------------------------------------------- main logic
def update(state):
    jobs, rejected = state["jobs"], set(state["rejected"])
    new, details_used = [], 0
    dkeys = {dkey(j) for j in jobs.values()}

    trax = collect_trax()
    ws = collect_ws()
    if _requests_ok == 0:
        log("ERROR: no request succeeded. The job board may be down or has changed.")
        sys.exit(1)

    for jid, j in trax.items():
        if jid in jobs:
            jobs[jid]["last_seen"] = NOW_ISO
            continue
        if jid in rejected:
            continue
        text = j.get("snippet", "")
        if j["id"].startswith("ba:"):
            if details_used >= DETAIL_CAP:
                continue          # check it on the next run
            text = ba_detail_text(j["ref"]) or ""
            details_used += 1
        tier = classify_trax(j, text)
        if not tier or dkey(j) in dkeys:
            rejected.add(jid)
            continue
        j.update(section="trax", tier=tier, topics=[], lang=detect_lang(text, j["title"]),
                 watch=is_watch(j["company"]), first_seen=NOW_ISO, last_seen=NOW_ISO)
        j.pop("snippet", None)
        jobs[jid] = j
        dkeys.add(dkey(j))
        new.append(j)

    student, exclude = re.compile(config.STUDENT_RE, re.I), re.compile(config.EXCLUDE_RE, re.I)
    for jid, j in ws.items():
        if jid in jobs:
            jobs[jid]["last_seen"] = NOW_ISO
            continue
        t = j["title"]
        if not student.search(t) or exclude.search(t) or not in_bw(j):
            continue
        topics = match_topics(t)
        if not topics or dkey(j) in dkeys:
            continue
        text = j.get("snippet", "")
        if j["id"].startswith("ba:") and details_used < DETAIL_CAP:
            text = ba_detail_text(j["ref"]) or ""
            details_used += 1
        j.update(section="ws", tier="", topics=topics, lang=detect_lang(text, t),
                 watch=is_watch(j["company"]), first_seen=NOW_ISO, last_seen=NOW_ISO)
        j.pop("snippet", None)
        jobs[jid] = j
        dkeys.add(dkey(j))
        new.append(j)

    cutoff = (NOW - timedelta(days=14)).isoformat()
    for jid in [k for k, v in jobs.items() if v["last_seen"] < cutoff]:
        del jobs[jid]
    state["rejected"] = sorted(rejected)[-6000:]
    log(f"{len(new)} new jobs this run, {len(jobs)} tracked")
    return new


# ---------------------------------------------------------------- email
def dashboard_url():
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}/"
    return ""


def job_html(j):
    star = " ★" if j.get("watch") else ""
    meta = " · ".join(x for x in [j["company"] + star, j["location"], ", ".join(j["topics"])] if x)
    tier = " (related)" if j.get("tier") == "related" else ""
    return (f'<p style="margin:0 0 14px"><a href="{html.escape(j["url"])}" style="font-weight:600;'
            f'font-size:15px;color:#1d4ed8;text-decoration:none">{html.escape(j["title"])}{tier}</a><br>'
            f'<span style="color:#475467;font-size:13px">{html.escape(meta)}</span></p>')


def build_email(new, first_run, total):
    sec = {
        "TRAX / FIS (Germany)": [j for j in new if j["section"] == "trax"],
        "Working student, English": [j for j in new if j["section"] == "ws" and j["lang"] == "en"],
        "Working student, Deutsch": [j for j in new if j["section"] == "ws" and j["lang"] == "de"],
    }
    url = dashboard_url()
    short = {"TRAX / FIS (Germany)": "TRAX", "Working student, English": "English", "Working student, Deutsch": "Deutsch"}
    counts = ", ".join(f"{len(v)} {short[k]}" for k, v in sec.items() if v)
    if first_run:
        subject = f"{config.SUBJECT_PREFIX} Setup complete: {total} matching jobs found"
        intro = (f"Your job radar is running. {total} jobs match right now. Starting now, you only get an "
                 "email when something new shows up. Everything found so far is on your dashboard.")
        sec = {k: v[:8] for k, v in sec.items() if k.startswith("TRAX")}
    else:
        subject = f"{config.SUBJECT_PREFIX} {len(new)} new: {counts}"
        intro = f"{len(new)} new jobs since the last check."
    body = [f'<div style="font-family:system-ui,Segoe UI,Arial;max-width:640px"><p>{intro}</p>']
    plain = [intro, ""]
    for name, items in sec.items():
        if not items:
            continue
        body.append(f'<h3 style="margin:22px 0 10px;font-size:16px">{name} ({len(items)})</h3>')
        plain.append(f"== {name} ({len(items)}) ==")
        for j in items:
            body.append(job_html(j))
            plain.append(f"{j['title']} | {j['company']} | {j['location']}\n{j['url']}\n")
    if url:
        body.append(f'<p><a href="{url}">Open dashboard</a></p>')
        plain.append(f"Dashboard: {url}")
    body.append("</div>")
    return subject, "\n".join(plain), "".join(body)


def send_email(subject, plain, html_body):
    user, pwd, to = os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD"), os.getenv("EMAIL_TO")
    if not (user and pwd and to):
        log("Email not configured (missing GMAIL_USER / GMAIL_APP_PASSWORD / EMAIL_TO). Preview:\n", subject, "\n", plain)
        return
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, f"Job Radar <{user}>", to
    msg.set_content(plain)
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pwd.replace(" ", ""))
        s.send_message(msg)
    log("Email sent.")


# ---------------------------------------------------------------- dashboard
def build_dashboard(state):
    cutoff = (NOW - timedelta(days=3)).isoformat()
    open_jobs = [j for j in state["jobs"].values() if j["last_seen"] >= cutoff]
    open_jobs.sort(key=lambda j: j["first_seen"], reverse=True)
    payload = {"updated": NOW_ISO, "jobs": open_jobs}
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    DASH_FILE.parent.mkdir(exist_ok=True)
    DASH_FILE.write_text((ROOT / "dashboard_template.html").read_text("utf-8").replace("__DATA__", data), "utf-8")


def main():
    state = load_state()
    first_run = not state["meta"].get("last_run")
    new = update(state)
    state["meta"]["last_run"] = NOW_ISO
    open_total = len(state["jobs"])
    if new:
        subject, plain, body = build_email(new, first_run, open_total)
        send_email(subject, plain, body)      # if this fails the run fails and nothing is saved
    elif first_run:
        log("First run finished with no matches.")
    save_state(state)
    build_dashboard(state)


if __name__ == "__main__":
    main()
