#scriptdoc: title="My shortcuts for doing stuff with the local repo", tags="bt,work,git"

# pip install gitpython
from git import Repo
import os
import re

class MyGit:
    def __init__(self, config):
        self.support_dir = os.path.join(os.path.expanduser("~"), "Support")
        self.initials = config.get("initials")

    def current_branch(self):
        repo = Repo('.')
        return repo.active_branch.name

    def create_branch_for_issue(self, issue_number, summary):
        repo = Repo('.')
        if repo.is_dirty():
            raise Exception("Repo is dirty")

        # Make a valid branch name
        summary = "".join(c for c in summary if c.isalnum() or c == " ")
        summary = summary.strip()
        summary = summary.replace(" ", "-")
        summary = summary.replace("---", "-")
        summary = summary.replace("--", "-")
        summary = summary.lower()
        issue_number = issue_number.lower()
        branch_name = f"{self.initials}/{issue_number}/{summary}"

        # Create the branch
        repo.git.checkout('main')
        repo.git.checkout('-b', branch_name)

        # Push the branch
        repo.git.push("--set-upstream", "origin", branch_name)

        return branch_name

    def create_support_folder(self, desired_id, title, url):
        folder_name = title
        folder_name = folder_name.replace(" ", "-")
        folder_name = folder_name.replace("--", "-").replace("--", "-").replace("--", "-")
        folder_name = re.sub(r'[^a-zA-Z0-9\-]', '', folder_name)
        folder_name = folder_name.lower()
        folder_name = os.path.join(self.support_dir, folder_name)

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

            # Create a windows shortcut to the url
            shortcut = os.path.join(folder_name, f"Case {desired_id}.url")
            with open(shortcut, 'w') as f:
                f.write('[InternetShortcut]\n')
                f.write('URL=' + url)
                f.close()

            # Create a markdown file with the url
            markdown = os.path.join(folder_name, f"CaseNotes-{desired_id}.md")
            with open(markdown, 'w') as f:
                f.write('# ' + title + '\n')
                f.write(url)
                f.write('\n\n## Notes\n\n')
                f.close()

            # Create a subfolder called attachments
            attachments = os.path.join(folder_name, "attachments")
            os.makedirs(attachments)

            return folder_name
        else:
            raise Exception(folder_name)
