from ...RagChat import RagChat
from jira_utils import write_issue_for_chat

class RagChatWrapper:
    def chat_with_issues(self, issues, jira, initial_user_message=None):
        chat = RagChat()
        for issue in issues:
            chat.add_document(write_issue_for_chat(issue, jira))
        return chat, initial_user_message
