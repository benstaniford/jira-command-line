import textwrap
from MyJira import MyJira

class JiraTextIssue:
    _issue = None
    _myjira = None
    _jira = None

    def __init__(self, issue, myjira: MyJira = None):
        self._issue = issue
        self._myjira = myjira
        self._jira = myjira.jira if myjira else None

    def clean_text(self, text):
        return text.replace('\r', '').replace('\n', ' ').strip() if text else ''

    def print(self):
        fields = self._issue.fields
        print(f"Issue: {self._issue.key}")
        print(f"Summary: {fields.summary}")
        print(f"Status: {fields.status.name}")
        print(f"Assignee: {getattr(fields.assignee, 'displayName', 'Unassigned')}")
        print(f"Reporter: {fields.reporter.displayName}")
        print(f"Created: {fields.created}")
        print(f"\nDescription:\n{textwrap.fill(self.clean_text(fields.description), 100)}\n")

        comments = self._jira.comments(self._issue)
        if comments:
            print("Comments:")
            for comment in comments:
                print(f"- [{comment.created[:10]}] {comment.author.displayName}: {self.clean_text(comment.body)}")
        print("\n" + "="*80 + "\n")
