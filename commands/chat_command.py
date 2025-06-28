from commands.base_command import BaseCommand
from jira_utils import write_issue_for_chat

class ChatCommand(BaseCommand):
    @property
    def shortcut(self):
        return "C"
    
    @property
    def description(self):
        return "chat"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            selection = ui.prompt_get_string("Enter comma separated issue numbers (e.g. 1,2,3) or hit enter to discuss all issues in the view")

            # Get the numbers of the rows
            if selection == "":
                rows = ui.get_rows()
                selection = []
                for i in range(len(rows)):
                    selection.append(str(i + 1))
            else:
                selection = selection.split(",")
                selection = [issue.strip() for issue in selection]

            selection = [int(issue) for issue in selection if issue.isdigit()]
            if len(selection) == 0:
                return False

            issues = []
            for issue in selection:
                [row, issue] = ui.get_row(issue-1)
                issues.append(issue)

            ui.prompt(f"Fetching {len(issues)} issues...")

            issue_ids = []
            from RagChat import RagChat
            chat = RagChat()
            for issue in issues:
                chat.add_document(write_issue_for_chat(issue, jira))

            ui.yield_screen()
            chat.chat()
            ui.restore_screen()

        except Exception as e:
            ui.error("Chat about issue", e)
        return False
