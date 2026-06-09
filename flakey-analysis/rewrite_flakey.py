#!/usr/bin/env python
"""Rewrite flakey.md to remove fixed tests and add a Fixed section."""
import json
import re
from datetime import datetime
from pathlib import Path

base = Path.home() / "jira-command-line"
flakey = json.load(open(base / "flakey_parsed.json", "r", encoding="utf-8"))
jira_m = json.load(open(base / "jira_matches.json", "r", encoding="utf-8"))
gh_m = json.load(open(base / "github_matches.json", "r", encoding="utf-8"))

tests = flakey["tests"]

fixed_by_jira = jira_m["fixed_by_jira"]
fixed_by_pr = gh_m["fixed_by_pr"]

# Build "fixed" set: test -> chosen fix entry (prefer earliest fix that proves resolution)
fixed = {}  # test_name -> [{"kind": "Jira"/"PR", "key_or_num":..., "date":..., "url":...}]
for t, ms in fixed_by_jira.items():
    for m in ms:
        fixed.setdefault(t, []).append({
            "kind": "Jira",
            "ref": m["key"],
            "date": m["res_date"],
            "url": f"https://beyondtrust.atlassian.net/browse/{m['key']}",
        })
for t, ms in fixed_by_pr.items():
    for m in ms:
        fixed.setdefault(t, []).append({
            "kind": "PR",
            "ref": f"#{m['number']}",
            "date": m["merge_date"],
            "url": f"https://github.com/BeyondTrust/epm-windows/pull/{m['number']}",
        })

fixed_names = set(fixed.keys())
print(f"Tests to remove (fixed): {len(fixed_names)}")
for n in fixed_names:
    print(f"  - {n}")

src = (base / "flakey.md").read_text(encoding="utf-8", errors="replace")
lines = src.splitlines()

# Parse into sections: header (1-3), summary table (4..top section), top section (## Top)
out_lines = []
top_idx = next(i for i, l in enumerate(lines) if l.startswith("## Top"))
# Keep lines [0..top_idx-1] as header+summary; we'll filter summary
# Detect summary table boundaries
header_end = 0
table_start = None
for i, l in enumerate(lines):
    if l.startswith("| # | Failures"):
        table_start = i
        break

# Lines before table_start go as-is.
for i in range(0, table_start):
    out_lines.append(lines[i])

# Summary table: header + separator + rows. Filter rows belonging to fixed tests.
out_lines.append(lines[table_start])      # header
out_lines.append(lines[table_start + 1])  # |---|---|---|...

new_rank = 0
for i in range(table_start + 2, top_idx):
    l = lines[i]
    if not l.strip().startswith("|"):
        out_lines.append(l)
        continue
    parts = [c.strip() for c in l.split("|")]
    if len(parts) < 7 or not parts[1].isdigit():
        out_lines.append(l)
        continue
    test_name = parts[4]
    if test_name in fixed_names:
        continue
    new_rank += 1
    parts[1] = str(new_rank)
    out_lines.append("| " + " | ".join(parts[1:-1]) + " |")

# Detail section
# Find section start indexes
detail_starts = []
for i in range(top_idx, len(lines)):
    if lines[i].startswith("### "):
        detail_starts.append(i)
detail_starts.append(len(lines))

# Filter out fixed tests' details
kept_blocks = []
for j in range(len(detail_starts) - 1):
    start = detail_starts[j]
    end = detail_starts[j + 1]
    header = lines[start]
    m = re.match(r"^### (\d+)\. (.+?) \(.+?\)", header)
    if not m:
        continue
    name = m.group(2).strip()
    if name in fixed_names:
        continue
    kept_blocks.append((name, lines[start:end]))

# Renumber kept blocks
out_lines.append("")
out_lines.append(f"## Top {len(kept_blocks)} Flakey Tests – Regression Run Links")
out_lines.append("")
for idx, (name, block) in enumerate(kept_blocks, 1):
    # Replace the leading "### N." with new number
    block_lines = list(block)
    block_lines[0] = re.sub(r"^### \d+\.", f"### {idx}.", block_lines[0])
    out_lines.extend(block_lines)

# Add Fixed Tests section
out_lines.append("")
out_lines.append("---")
out_lines.append("")
out_lines.append("## Fixed Tests (Removed from Report)")
out_lines.append("")
out_lines.append("The following tests were removed because a fix was identified after their last failure:")
out_lines.append("")
out_lines.append("| Test | Last Failure | Fix | Fix Date | Reference |")
out_lines.append("|------|-------------|-----|----------|-----------|")
for name in sorted(fixed_names):
    latest = tests[name]["latest_date"]
    for fix in fixed[name]:
        ref_md = f"[{fix['ref']}]({fix['url']})"
        out_lines.append(f"| {name} | {latest} | {fix['kind']} | {fix['date']} | {ref_md} |")

# Generation timestamp
out_lines.append("")
out_lines.append(f"_Report regenerated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} after cross-referencing Jira and GitHub for fixes._")

(base / "flakey.md").write_text("\n".join(out_lines) + "\n", encoding="utf-8")
print(f"Rewrote flakey.md: {new_rank} tests in summary, {len(kept_blocks)} in detail section")
