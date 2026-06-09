#!/usr/bin/env python
"""Build ADF doc for Epic creation."""
import json
from collections import OrderedDict
from datetime import date
from pathlib import Path

base = Path.home() / "jira-command-line"
flakey = json.load(open(base / "flakey_parsed.json", "r", encoding="utf-8"))
jira_m = json.load(open(base / "jira_matches.json", "r", encoding="utf-8"))
gh_m = json.load(open(base / "github_matches.json", "r", encoding="utf-8"))

fixed = set(jira_m["fixed_by_jira"].keys()) | set(gh_m["fixed_by_pr"].keys())

tests = flakey["tests"]
# Build ordered list of top 20 by rank, EXCLUDING fixed
ranked = sorted(tests.items(), key=lambda x: x[1]["rank"])
top = []
for name, info in ranked:
    if name in fixed:
        continue
    if info["run_links"]:
        top.append((name, info))
    if len(top) >= 20:
        break

def runs_to_cell(run_links):
    """Dedup by URL while preserving date order; one link per unique run."""
    seen = OrderedDict()
    for r in run_links:
        if r["url"] not in seen:
            seen[r["url"]] = r
    content = []
    items = list(seen.values())
    for i, r in enumerate(items):
        if i > 0:
            content.append({"type": "text", "text": ", "})
        content.append({
            "type": "text",
            "text": r["date"],
            "marks": [{"type": "link", "attrs": {"href": r["url"]}}],
        })
    return content

table_rows = []
header = {"type": "tableRow", "content": [
    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "#"}]}]},
    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Test Name"}]}]},
    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Failure Rate"}]}]},
    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Affected Runs"}]}]},
    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Open Jira"}]}]},
]}
table_rows.append(header)

for idx, (name, info) in enumerate(top, 1):
    failures = info["failures"]  # e.g. "27 (129%)"
    rate = info["rate"]          # e.g. "27/21"
    cell_runs = runs_to_cell(info["run_links"])
    pct = failures.split("(")[1].rstrip("%)") if "(" in failures else ""
    count_n = failures.split(" ")[0]
    rate_text = f"{pct}% ({count_n}/{rate.split('/')[1]})" if pct else failures
    row = {"type": "tableRow", "content": [
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": str(idx)}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": name}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": rate_text}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": cell_runs}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": " "}]}]},
    ]}
    table_rows.append(row)

period = f"{flakey['earliest_failure_date']} to {flakey['latest_failure_date']}"
intro_text = (
    f"Top {len(top)} flakey tests from EPM-W nightly regression runs over the period {period}. "
    f"Total flakey tests in source report: {flakey['total_tests']} "
    f"(after removing 8 tests with verified fixes). "
    f"Each row links to the affected nightly runs, and where an open Jira ticket exists or is created, "
    f"the Open Jira column links to it."
)

doc = {
    "type": "doc",
    "version": 1,
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": intro_text}]},
        {"type": "table", "attrs": {"layout": "default"}, "content": table_rows},
    ],
}

out = {"top": [(n, info["rank"]) for n, info in top], "adf": doc}
json.dump(out, open(base / "epic_adf.json", "w", encoding="utf-8"), indent=2)
print(f"Built ADF for {len(top)} tests")
for n, _ in [(n, info["rank"]) for n, info in top]:
    print(f"  - {n}")
