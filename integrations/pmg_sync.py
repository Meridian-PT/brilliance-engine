#!/usr/bin/env python3
"""PMG Time Tracker -> Brilliance Engine sync.

Pulls time entries from the PMG Time Tracker (tt.puremarketing.ai) and pushes
them into Brilliance Engine via the Phase 4 ingestion API
(POST /api/v1/time-entries, X-API-Token). Idempotent per entry is NOT guaranteed
by this script; schedule it over a bounded recent window to avoid duplicates, or
add a dedupe key on the Brilliance side.

Config (env vars, or local 0600 secret files as fallback):
  PMG_BASE            default https://tt.puremarketing.ai
  PMG_EMAIL/PMG_PASSWORD   or  ~/.secrets/pmg_creds  (email\\npassword)
  BRILLIANCE_BASE     default https://brilliance-engine.onrender.com
  TIMETRACK_API_TOKEN      or  ~/.secrets/timetrack_api_token

User mapping: PMG keys time by the worker's email. EMAIL_MAP translates a PMG
email to the matching Brilliance Engine user email where they differ.

NOTE: Mike's PMG account is role=employee, so it can only pull HIS OWN entries.
A team-wide sync needs a PMG admin/service token.
"""
import os, sys, json, urllib.request, urllib.error, datetime

PMG_BASE = os.environ.get("PMG_BASE", "https://tt.puremarketing.ai")
BRILLIANCE_BASE = os.environ.get("BRILLIANCE_BASE", "https://brilliance-engine.onrender.com")
UA = "Meridian-PMG-Sync/1.0"

EMAIL_MAP = {
    # PMG email -> Brilliance Engine email
    "mdaser@puretechnology.nyc": "mike@puretechnology.nyc",
}


def _read_secret(path):
    try:
        return open(os.path.expanduser(path)).read().strip()
    except OSError:
        return None


def _pmg_creds():
    e = os.environ.get("PMG_EMAIL"); p = os.environ.get("PMG_PASSWORD")
    if e and p:
        return e, p
    blob = _read_secret("~/.secrets/pmg_creds")
    if blob and "\n" in blob:
        a, b = blob.split("\n", 1)
        return a.strip(), b.strip()
    raise SystemExit("No PMG credentials (set PMG_EMAIL/PMG_PASSWORD or ~/.secrets/pmg_creds)")


def _bri_token():
    return os.environ.get("TIMETRACK_API_TOKEN") or _read_secret("~/.secrets/timetrack_api_token")


def _req(method, url, headers, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=45) as resp:
            t = resp.read().decode()
            return resp.getcode(), (json.loads(t) if t else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="ignore")


def pmg_login(email, password):
    code, data = _req("POST", f"{PMG_BASE}/api/auth/login",
                       {"Content-Type": "application/json", "User-Agent": UA},
                       {"email": email, "password": password})
    if code != 200 or not isinstance(data, dict) or not data.get("token"):
        raise SystemExit(f"PMG login failed: {code} {data}")
    return data["token"], data.get("user", {})


def pmg_time_entries(token, limit=500):
    h = {"Authorization": f"Bearer {token}", "User-Agent": UA}
    code, data = _req("GET", f"{PMG_BASE}/api/time-entries?limit={limit}", h)
    if code != 200:
        raise SystemExit(f"PMG time-entries fetch failed: {code} {data}")
    return data.get("entries", data) if isinstance(data, dict) else data


def _g(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def transform(entry, default_email):
    """Map a PMG entry to the Brilliance ingestion shape. Defensive about field names."""
    pmg_email = _g(entry, "user_email", "email", default=default_email)
    bri_email = EMAIL_MAP.get(pmg_email, pmg_email)
    # hours: prefer explicit hours, else derive from minutes/seconds
    hours = _g(entry, "hours", "duration_hours")
    if hours is None:
        mins = _g(entry, "minutes", "duration_minutes")
        secs = _g(entry, "seconds", "duration", "duration_seconds")
        if mins is not None:
            hours = round(float(mins) / 60.0, 2)
        elif secs is not None:
            hours = round(float(secs) / 3600.0, 2)
    work_date = _g(entry, "work_date", "date", "started_at", "day")
    if work_date and "T" in str(work_date):
        work_date = str(work_date).split("T")[0]
    project = _g(entry, "project_name", "project", "task", "project_or_task",
                 default=_g(entry, "client_name", "client", default="PMG"))
    desc = _g(entry, "description", "notes", "note", default="")
    if hours is None or not work_date or not bri_email:
        return None
    return {"employee_email": bri_email, "work_date": work_date,
            "hours": float(hours), "project_or_task": str(project)[:200],
            "description": str(desc)[:500]}


def push_to_brilliance(entries, token):
    h = {"Content-Type": "application/json", "X-API-Token": token, "User-Agent": UA}
    code, data = _req("POST", f"{BRILLIANCE_BASE}/api/v1/time-entries", h, {"entries": entries})
    return code, data


def main():
    token_bri = _bri_token()
    if not token_bri:
        raise SystemExit("No Brilliance ingestion token")
    email, password = _pmg_creds()
    pmg_token, user = pmg_login(email, password)
    print(f"PMG login OK as {user.get('email')} (role={user.get('role')})")
    raw = pmg_time_entries(pmg_token)
    print(f"PMG returned {len(raw)} time entries")
    mapped = [m for m in (transform(e, user.get("email")) for e in raw) if m]
    print(f"transformed {len(mapped)} entries ({len(raw)-len(mapped)} skipped for missing fields)")
    if not mapped:
        print("Nothing to push. (If this is Mike's employee account, PMG only exposes his own "
              "entries — team-wide sync needs a PMG admin/service token.)")
        return
    code, data = push_to_brilliance(mapped, token_bri)
    print(f"Brilliance ingestion -> HTTP {code}: {json.dumps(data)[:300]}")


if __name__ == "__main__":
    main()
