#!/usr/bin/env python
"""Match resolved Jira tickets against flakey tests."""
import json
import re
from pathlib import Path

base = Path.home() / "jira-command-line"
flakey = json.load(open(base / "flakey_parsed.json", "r", encoding="utf-8"))
jira = json.load(open(base / "jira_resolved.json", "r", encoding="utf-8"))

tests = flakey["tests"]

# Build per-ticket text blob (lowercased)
for t in jira:
    t["blob"] = (t["summary"] + " " + (t["description"] or "")).lower()
    t["res_date"] = t["resolutiondate"][:10] if t["resolutiondate"] else ""

matches = {}  # test_name -> list of {ticket_key, res_date, summary}

for test_name, info in tests.items():
    test_lower = test_name.lower()
    latest = info["latest_date"]
    # Build candidate fragments: full name, and split-by-underscore prefix
    fragments = [test_lower]
    # Also try the substring after first underscore prefix (e.g. "AppControl_BlockExecution_...")
    parts = test_lower.split("_")
    if len(parts) > 2:
        # Use a 3-segment fragment (often distinctive enough)
        fragments.append("_".join(parts[:3]))

    test_matches = []
    for t in jira:
        # Exact full-name match
        if test_lower in t["blob"]:
            test_matches.append({
                "key": t["key"],
                "res_date": t["res_date"],
                "summary": t["summary"],
                "match_type": "exact",
            })
    if test_matches:
        matches[test_name] = test_matches

# Determine fixed
fixed = {}
fix_didnt_work = {}
for test_name, info in tests.items():
    latest = info["latest_date"]
    for m in matches.get(test_name, []):
        if m["res_date"] and m["res_date"] >= latest:
            fixed.setdefault(test_name, []).append(m)
        elif m["res_date"] and m["res_date"] < latest:
            fix_didnt_work.setdefault(test_name, []).append(m)

out = {
    "matches": matches,
    "fixed_by_jira": fixed,
    "fix_didnt_work_jira": fix_didnt_work,
}
json.dump(out, open(base / "jira_matches.json", "w", encoding="utf-8"), indent=2)

print(f"Total flakey tests: {len(tests)}")
print(f"Tests with any Jira match: {len(matches)}")
print(f"Tests fixed (resolved AFTER latest failure): {len(fixed)}")
print(f"Tests where fix predates latest failure: {len(fix_didnt_work)}")
print()
print("Fixed tests:")
for k, v in fixed.items():
    for m in v:
        print(f"  {k} -> {m['key']} ({m['res_date']}): {m['summary'][:80]}")
print()
print("Fix predates latest failure:")
for k, v in fix_didnt_work.items():
    for m in v:
        print(f"  {k} (last failed {tests[k]['latest_date']}) -> {m['key']} resolved {m['res_date']}")
