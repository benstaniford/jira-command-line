from pycopilot import AuthCache
from jira_utils import write_issue_for_chat

class CopilotChat:
    def __init__(self):
        self.auth = AuthCache()

    def ask_with_reauth(self, prompt, stream=False, client=None, max_reauth=1):
        from pycopilot import AuthenticationError
        reauths = 0
        if client is None:
            client = self.auth.authenticate()
        while True:
            try:
                if stream:
                    for chunk in client.ask(prompt, stream=True):
                        yield chunk
                    break
                else:
                    return client.ask(prompt, stream=False)
            except AuthenticationError:
                if reauths < max_reauth:
                    client = self.auth.authenticate()
                    reauths += 1
                    continue
                else:
                    raise

    def chat_with_issues(self, issues, jira, initial_user_message=None):
        import tempfile
        import os
        client = self.auth.authenticate()
        temp_files = []
        try:
            for issue in issues:
                issue_content = write_issue_for_chat(issue, jira)
                try:
                    client.add_context(issue_content)
                except Exception:
                    with tempfile.NamedTemporaryFile(mode='w', suffix=f'_{issue.key}.txt', delete=False) as f:
                        f.write(issue_content)
                        temp_file = f.name
                        temp_files.append(temp_file)
                    client.add_context(temp_file)
            return client, temp_files
        finally:
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except Exception:
                        pass
