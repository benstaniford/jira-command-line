#!/usr/bin/env python
"""Build ADF doc for Epic creation - with Open Jira links populated."""
import json
from collections import OrderedDict
from pathlib import Path

base = Path.home() / "jira-command-line"
flakey = json.load(open(base / "flakey_parsed.json", "r", encoding="utf-8"))
jira_m = json.load(open(base / "jira_matches.json", "r", encoding="utf-8"))
gh_m = json.load(open(base / "github_matches.json", "r", encoding="utf-8"))

fixed = set(jira_m["fixed_by_jira"].keys()) | set(gh_m["fixed_by_pr"].keys())

# Map test name -> open Jira key (from Step 9 results)
open_tickets = {
    "Conhost_ChildInstanceIsNotElevatedIfInAnUntrustedLocation_CWindowsSystem32SpoolDriversColor": "EPM-54810",
    "Conhost_ChildInstanceIsNotElevatedIfInAnUntrustedLocation_CWindowsTasks": "EPM-54810",
    "Conhost_ChildInstanceIsNotElevatedIfInAnUntrustedLocation_Syswow64Path": "EPM-54810",
    "Identity_CancelIdentityVerificationViaTaskTray": "EPM-54036",
    "ApplySingleUserPolicyToMultipleUsers": "EPM-52900",
}

tests = flakey["tests"]
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

def open_jira_cell(name):
    key = open_tickets.get(name)
    if key:
        return [{
            "type": "text",
            "text": key,
            "marks": [{"type": "link", "attrs": {"href": f"https://beyondtrust.atlassian.net/browse/{key}"}}],
        }]
    return [{"type": "text", "text": " "}]

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
    failures = info["failures"]
    rate = info["rate"]
    cell_runs = runs_to_cell(info["run_links"])
    pct = failures.split("(")[1].rstrip("%)") if "(" in failures else ""
    count_n = failures.split(" ")[0]
    rate_text = f"{pct}% ({count_n}/{rate.split('/')[1]})" if pct else failures
    row = {"type": "tableRow", "content": [
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": str(idx)}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": name}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": rate_text}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": cell_runs}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": open_jira_cell(name)}]},
    ]}
    table_rows.append(row)

period = f"{flakey['earliest_failure_date']} to {flakey['latest_failure_date']}"
intro_text = (
    f"Top {len(top)} flakey tests in PMfW Regression on main, period {period} "
    f"(21 nightly runs after omitting one outlier). "
    f"Total flakey tests in source report: {flakey['total_tests']}; "
    f"{len(fixed)} removed as fixed (resolved after their last failure); "
    f"{flakey['total_tests'] - len(fixed)} remain. "
    f"The top {len(top)} are listed below with linked Jira tickets; the full report is in flakey.md."
)

doc = {
    "type": "doc",
    "version": 1,
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": intro_text}]},
        {"type": "table", "attrs": {"layout": "default"}, "content": table_rows},
    ],
}

out_path = base / "epic_adf_final.json"
json.dump(doc, open(out_path, "w", encoding="utf-8"))
print(f"Built ADF for {len(top)} tests")
print(f"Size: {out_path.stat().st_size} bytes")
