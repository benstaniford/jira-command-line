from .base_command import BaseCommand
import webbrowser
import os

class SupportCommand(BaseCommand):
    @property
    def shortcut(self):
        return "S"
    
    @property
    def description(self):
        return "spprtdir"
    
    def execute(self, ui, view, jira, mygit=None, **kwargs):
        try:
            selection = ui.prompt_get_string("Enter issue number")
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                yesno = "n"
                folder_name = ""
                try:
                    folder_name = mygit.create_support_folder(issue.key, issue.fields.summary, issue.permalink())
                    yesno = ui.prompt_get_character(f"Created support folder for {issue.key}...\nDo you want to download attachments? (y/n)")
                except Exception as e:
                    folder_name = e.args[0]
                    yesno = ui.prompt_get_character(f"Support folder already exists for {issue.key}...\nDo you want to update downloaded attachments? (y/n)")
                webbrowser.open(folder_name)
                if yesno == "y":
                    # Create a lambda function to prompt each time a file begins download
                    callback = lambda filename: ui.prompt(f"Downloading {filename}...")
                    jira.download_attachments(issue, os.path.join(folder_name, "attachments"), callback)
        except Exception as e:
            ui.error("Create support folder", e)
        return False
