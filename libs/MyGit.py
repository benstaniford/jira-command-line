#scriptdoc: title="My shortcuts for doing stuff with the local repo", tags="bt,work,git"

# pip install gitpython
from git import Repo
import os
import re

class MyGit:
    # Matches git@github.com:owner/repo.git, ssh://git@github.com/owner/repo
    # and https://github.com/owner/repo(.git)
    GITHUB_REMOTE_RE = re.compile(
        r'^(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)'
        r'(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$')

    def __init__(self, config):
        self.support_dir = os.path.join(os.path.expanduser("~"), "Support")
        self.initials = config.get("initials")

    def get_origin_repo(self):
        """Return (owner, repo) from the current directory's origin remote, or
        None if not inside a git repo, no origin remote, or not a github.com remote."""
        try:
            repo = Repo('.', search_parent_directories=True)
            url = repo.remotes.origin.url
        except Exception:
            return None
        match = self.GITHUB_REMOTE_RE.match(url.strip())
        return (match.group('owner'), match.group('repo')) if match else None

    def current_branch(self):
        repo = Repo('.', search_parent_directories=True)
        return repo.active_branch.name

    def branch_name_for_issue(self, issue_number, summary):
        # Make a valid branch name
        summary = "".join(c for c in summary if c.isalnum() or c == " ")
        summary = summary.strip()
        summary = summary.replace(" ", "-")
        summary = summary.replace("---", "-")
        summary = summary.replace("--", "-")
        summary = summary.lower()
        issue_number = issue_number.lower()
        return f"{self.initials}/{issue_number}/{summary}"

    def create_branch_for_issue(self, issue_number, summary):
        repo = Repo('.', search_parent_directories=True)
        if repo.is_dirty():
            raise Exception("Repo is dirty")

        branch_name = self.branch_name_for_issue(issue_number, summary)

        # Create the branch (all BeyondTrust repos use 'main' as the default branch)
        repo.git.checkout('main')
        repo.git.checkout('-b', branch_name)

        # Push the branch
        repo.git.push("--set-upstream", "origin", branch_name)

        return branch_name

    def create_worktree_for_issue(self, issue_number, summary):
        """Create a new branch off main and check it out into a sibling worktree.
        Returns (branch_name, worktree_path)."""
        repo = Repo('.', search_parent_directories=True)
        branch_name = self.branch_name_for_issue(issue_number, summary)

        # Worktrees live alongside the repo in <repo>-worktrees/<branch-dirname>
        repo_root = repo.working_tree_dir
        worktree_dir = f"{repo_root}-worktrees"
        worktree_path = os.path.join(worktree_dir, branch_name.replace("/", "-"))
        if os.path.exists(worktree_path):
            raise Exception(f"Worktree already exists: {worktree_path}")
        os.makedirs(worktree_dir, exist_ok=True)

        # Branch from main without disturbing the current checkout
        repo.git.worktree('add', worktree_path, '-b', branch_name, 'main')

        return branch_name, worktree_path

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
