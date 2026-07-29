from .base_command import BaseCommand
import time

# Default checklist for EPM teams; other projects get no checklist unless the
# team config sets "pr_checklist" (an empty string suppresses it entirely)
DEFAULT_EPM_CHECKLIST = """> [!IMPORTANT]
> __All PRs should follow our [Core Guidelines](https://beyondtrust.atlassian.net/wiki/spaces/PMFW/pages/780271678/EPM+Windows+Development+Strategy#Core-Guidelines). Please review and tick off each of the following before merging__

- [ ] The description explains both the "why" and "what" of the change.
- [ ] This PR is limited to a single logical change. All refactoring, formatting, or unrelated changes are excluded and handled in separate PRs.
- Select one of:
  - [ ] A remote review (e.g. Teams call) has been completed for this PR. <!-- TaskRadio one -->
  - [ ] A remote review (e.g. Teams call) was determined to be unnecessary due to its simplicity. <!-- TaskRadio one -->
- [ ] Impact areas have been identified, and relevant automation ran and linked."""

class PrCommand(BaseCommand):
    @property
    def shortcut(self):
        return "p"
    
    @property
    def description(self):
        return "pr"
    
    def execute(self, ui, view, jira, mygithub=None, mygit=None, **kwargs):
        try:
            if (mygithub == None):
                ui.error("Github token not set in config, cannot create PRs")
                return False
            [selection, row, issue] = ui.prompt_get_issue()
            if issue:
                [i, type_pr] = ui.prompt_with_choice_list("PR Type", ["fix", "feat", "chore", "refactor", "test"])
                if type_pr != "":
                    summary = ui.prompt_get_string("Enter a PR summary (default is issue summary)")
                    summary = summary if summary != "" else issue.fields.summary
                    title = f"{type_pr}: {summary} [{issue.key}]"
                    
                    # Get Problem description
                    problem = ui.prompt_get_string("Enter Problem description")
                    problem = problem if problem != "" else issue.fields.summary
                    
                    # Get Solution description
                    solution = ui.prompt_get_string("Enter Solution description")
                    solution = solution if solution != "" else (issue.fields.description or "")
                    
                    # Build the new PR body format
                    checklist = getattr(jira, 'pr_checklist', None)
                    if checklist is None and jira.project_name == "EPM":
                        checklist = DEFAULT_EPM_CHECKLIST
                    body = f"""<!-- markdownlint-disable-next-line MD041 -->
## Problem

{problem}

## Solution

{solution}"""
                    if checklist:
                        body += f"\n\n## Checklist\n\n{checklist}"
                    body += f"""

## Related Links (e.g. builds, automation runs)

[Add build links and automation runs here]

Jira Ticket: {issue.key}"""
                    head = mygit.current_branch()
                    base = "main"  # all BeyondTrust repos use 'main' as the default branch
                    yesno = ui.prompt_get_character(f"Create the PR {title} from:\n{head} -> {base}? (y/n)")
                    if yesno == "y":
                        ui.prompt(f"Creating PR for {issue.key}...")
                        mygithub.create_pull(title=title, body=body, base=base, head=head)
                        ui.prompt(f"Created PR for {issue.key}...")
                        time.sleep(2)
                        view.refresh()
        except Exception as e:
            ui.error("Create PR", e)
        return False
