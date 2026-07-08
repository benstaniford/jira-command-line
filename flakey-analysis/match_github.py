#!/usr/bin/env python
"""Match merged GitHub PRs against flakey tests."""
import json
from pathlib import Path

base = Path.home() / "jira-command-line"
flakey = json.load(open(base / "flakey_parsed.json", "r", encoding="utf-8"))
prs = json.load(open(base / "github_prs.json", "r", encoding="utf-8"))

tests = flakey["tests"]

for p in prs:
    p["blob"] = (p["title"] + " " + (p.get("body") or "")).lower()
    p["merge_date"] = (p.get("mergedAt") or "")[:10]

matches = {}
for test_name, info in tests.items():
    test_lower = test_name.lower()
    test_matches = []
    for p in prs:
        if test_lower in p["blob"]:
            test_matches.append({
                "number": p["number"],
                "title": p["title"],
                "merge_date": p["merge_date"],
            })
    if test_matches:
        matches[test_name] = test_matches

fixed = {}
fix_didnt_work = {}
for test_name, info in tests.items():
    latest = info["latest_date"]
    for m in matches.get(test_name, []):
        if m["merge_date"] and m["merge_date"] >= latest:
            fixed.setdefault(test_name, []).append(m)
        elif m["merge_date"] and m["merge_date"] < latest:
            fix_didnt_work.setdefault(test_name, []).append(m)

out = {
    "matches": matches,
    "fixed_by_pr": fixed,
    "fix_didnt_work_pr": fix_didnt_work,
}
json.dump(out, open(base / "github_matches.json", "w", encoding="utf-8"), indent=2)

print(f"Total flakey tests: {len(tests)}")
print(f"Tests with PR match: {len(matches)}")
print(f"Tests fixed by PR (merged AFTER latest failure): {len(fixed)}")
print(f"PR predates latest failure: {len(fix_didnt_work)}")
print()
print("PR-fixed tests:")
for k, v in fixed.items():
    for m in v:
        print(f"  {k} -> #{m['number']} ({m['merge_date']}): {m['title'][:80]}")
print()
print("PR predates latest failure:")
for k, v in fix_didnt_work.items():
    for m in v:
        print(f"  {k} (last failed {tests[k]['latest_date']}) -> #{m['number']} merged {m['merge_date']}: {m['title'][:80]}")
