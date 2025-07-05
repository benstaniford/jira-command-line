from .base_command import BaseCommand
import time

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
            selection = ui.prompt_get_string("Enter issue number")
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                [i, type_pr] = ui.prompt_with_choice_list("PR Type", ["fix", "feat", "chore", "refactor", "test"])
                if type_pr != "":
                    summary = ui.prompt_get_string("Enter a PR summary (default is issue summary)")
                    summary = summary if summary != "" else issue.fields.summary
                    title = f"{type_pr}: {summary} [{issue.key}]"
                    body = f"Jira Issue: {issue.permalink()}"
                    yesno = ui.prompt_get_character(f"Do you want to include the description in the PR body? (y/n)")
                    if yesno == "y":
                        body += f"\n\nDescription: {issue.fields.description}"
                    head = mygit.current_branch()
                    base = "main"
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
