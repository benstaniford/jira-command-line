import requests
import datetime

#scriptdoc: title="My comms library for talking to github", tags="bt,work,github"

# pip install PyGithub
from github import Github

class MyGithub:
    def __init__(self, config):
        self.username = config.get("username")
        self.login = config.get("login")
        self.token = config.get("token")
        self.api_endpoint = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.token}" }

        self.github = Github(self.login, self.token)

        # Endpoints
        self.repo_owner = config.get("repo_owner")
        self.repo_name = config.get("repo_name")
        self.pull_endpoint = f"{self.api_endpoint}/repos/{self.repo_owner}/{self.repo_name}/pulls"
        self.pull_query = f"{self.api_endpoint}/search/issues?q=repo:{self.repo_owner}/{self.repo_name}"

    def create_pull(self, title, body, head, base):
        repo = self.github.get_repo(f"{self.repo_owner}/{self.repo_name}")
        return repo.create_pull(title=title, body=body, head=head, base=base)
    
    # Make a request to get the pull requests assigned to you, and return the json
    def get_prs(self):
        response = requests.get(self.pull_endpoint, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Failed to get pull requests: {response.text}")
        return response.json()

    def get_prs_query(self, query):
        response = requests.get(f"{self.pull_query}+{query}", headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Failed to get pull requests: {response.text}")

        # We only get partial information with the query, so look up the full PRs
        all_prs = self.get_prs()
        query_prs = response.json()["items"]
        prs = []
        for pr in all_prs:
            if pr["number"] in [query_pr["number"] for query_pr in query_prs]:
                prs.append(pr)
        return prs

    # Get the number of days since the PR was created
    def get_pr_agedays(self, pr):
        created_at = pr["created_at"]
        date = created_at.split("T")[0]
        time = created_at.split("T")[1].split("Z")[0]
        # days since created
        return str((datetime.datetime.now() - datetime.datetime.strptime(date, "%Y-%m-%d")).days)

    def get_requested_reviewers(self, pr):
        requested_reviewers = pr["requested_reviewers"] 
        reviewers = []
        for reviewer in requested_reviewers:
            reviewers.append(reviewer["login"])
        return reviewers

    def am_i_reviewer(self, pr):
        reviewers = self.get_requested_reviewers(pr)
        return self.login in reviewers

    def get_pr_description(self, pr_number):
        """Get the description/body of a pull request by PR number."""
        repo = self.github.get_repo(f"{self.repo_owner}/{self.repo_name}")
        pr = repo.get_pull(pr_number)
        return pr.body

    def update_pr_description(self, pr_number, new_description):
        """Update the description/body of a pull request by PR number."""
        repo = self.github.get_repo(f"{self.repo_owner}/{self.repo_name}")
        pr = repo.get_pull(pr_number)
        pr.edit(body=new_description)
        return True

    def get_pr_by_number(self, pr_number):
        """Get full PR details by PR number."""
        repo = self.github.get_repo(f"{self.repo_owner}/{self.repo_name}")
        return repo.get_pull(pr_number)
