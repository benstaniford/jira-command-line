#!/usr/bin/env python
"""Parse flakey.md into JSON for downstream processing."""
import json
import re
from pathlib import Path

p = Path.home() / "jira-command-line" / "flakey.md"
text = p.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()

tests = {}  # name -> {dates, suites, count, rate, latest_date, runs (list of urls)}
mode = None
current_name = None

for line in lines:
    if line.startswith("| # | Failures"):
        mode = "summary"
        continue
    if line.startswith("## Top"):
        mode = "detail"
        continue
    if mode == "summary" and line.startswith("|") and not line.startswith("|---"):
        parts = [c.strip() for c in line.split("|")]
        # parts: ['', '#', 'Failures', 'Rate', 'Test', 'Suite(s)', 'Dates', '']
        if len(parts) < 7 or not parts[1].isdigit():
            continue
        rank = int(parts[1])
        failures = parts[2]
        rate = parts[3]
        name = parts[4]
        suites = parts[5]
        dates_str = parts[6]
        dates = [d.strip() for d in dates_str.split(",") if d.strip()]
        latest = max(dates) if dates else ""
        tests[name] = {
            "rank": rank,
            "failures": failures,  # like "27 (129%)"
            "rate": rate,           # like "27/21"
            "suites": suites,
            "dates": dates,
            "latest_date": latest,
            "run_links": [],  # populated from detail
        }
    elif mode == "detail":
        m = re.match(r"^### (\d+)\. (.+?) \((\d+) failures, (\d+)%\)", line)
        if m:
            current_name = m.group(2).strip()
            continue
        m2 = re.match(r"^- (\d{4}-\d{2}-\d{2}) . \[(.+?)\]\((.+?)\)", line)
        if m2 and current_name and current_name in tests:
            date = m2.group(1)
            suite = m2.group(2)
            url = m2.group(3)
            tests[current_name]["run_links"].append({"date": date, "suite": suite, "url": url})

# Find earliest failure date
all_dates = []
for t in tests.values():
    all_dates.extend(t["dates"])
earliest = min(all_dates) if all_dates else ""
latest = max(all_dates) if all_dates else ""

result = {
    "earliest_failure_date": earliest,
    "latest_failure_date": latest,
    "total_tests": len(tests),
    "tests": tests,
}

out = Path.home() / "jira-command-line" / "flakey_parsed.json"
out.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(f"Parsed {len(tests)} tests")
print(f"Earliest failure: {earliest}")
print(f"Latest failure: {latest}")
print(f"Top 20 tests have run_links: {sum(1 for t in tests.values() if t['run_links'])}")
