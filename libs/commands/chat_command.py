from .base_command import BaseCommand
from jira_utils import write_issue_for_chat

# Set to True to use pycopilot, False to use RagChat
USE_PYCOPILOT = True

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

            if USE_PYCOPILOT:
                self._chat_with_pycopilot(ui, issues, jira)
            else:
                self._chat_with_ragchat(ui, issues, jira)

        except Exception as e:
            ui.error("Chat about issue", e)
        return False
    
    def _chat_with_ragchat(self, ui, issues, jira):
        """Chat using RagChat library"""
        from RagChat import RagChat
        chat = RagChat()
        for issue in issues:
            chat.add_document(write_issue_for_chat(issue, jira))

        ui.yield_screen()
        chat.chat()
        ui.restore_screen()
    
    def _chat_with_pycopilot(self, ui, issues, jira):
        """Chat using pycopilot library with cached authentication"""
        try:
            from pycopilot import CopilotClient, AuthCache, CopilotAuth, AuthenticationError
            
            # Try to get cached authentication
            cache = AuthCache()
            chat_token = cache.get_valid_cached_chat_token()
            
            if not chat_token:
                # Try to get a new chat token from cached bearer token
                bearer_token = cache.get_cached_bearer_token()
                if not bearer_token:
                    raise Exception("Auth failed, please authenticate with copilot")
                auth = CopilotAuth()
                try:
                    chat_token = auth.get_chat_token_from_bearer(bearer_token)
                    if not chat_token:
                        raise Exception("Auth failed, please authenticate with copilot")
                    cache.cache_chat_token(chat_token)
                except Exception:
                    raise Exception("Auth failed, please authenticate with copilot")
            
            # Initialize client with cached token
            client = CopilotClient()
            client.set_chat_token(chat_token)
            
            import tempfile
            import os
            temp_files = []
            try:
                # Add issues as context
                for issue in issues:
                    issue_content = write_issue_for_chat(issue, jira)
                    # Add the content directly to the context if supported
                    try:
                        client.add_context(issue_content)
                    except Exception:
                        # Fallback: if add_context only supports file paths, use temp file
                        with tempfile.NamedTemporaryFile(mode='w', suffix=f'_{issue.key}.txt', delete=False) as f:
                            f.write(issue_content)
                            temp_file = f.name
                            temp_files.append(temp_file)
                        client.add_context(temp_file)
                
                # Start interactive chat
                ui.yield_screen()
                self._interactive_pycopilot_chat(client)
                ui.restore_screen()
            
            finally:
                # Clean up temp files
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        try:
                            os.unlink(temp_file)
                        except Exception:
                            pass
        
        except AuthenticationError:
            raise Exception("Auth failed, please authenticate with copilot")
        except ImportError:
            raise Exception("pycopilot library not available, please install it or set USE_PYCOPILOT=False")
    
    def _reauthenticate_pycopilot(self, client):
        """Try to get a new chat token from cached bearer token and set it on the client. Raise if not possible."""
        from pycopilot import AuthCache, CopilotAuth
        cache = AuthCache()
        bearer_token = cache.get_cached_bearer_token()
        if not bearer_token:
            raise Exception("Auth failed, please authenticate with copilot")
        auth = CopilotAuth()
        chat_token = auth.get_chat_token_from_bearer(bearer_token)
        if not chat_token:
            raise Exception("Auth failed, please authenticate with copilot")
        cache.cache_chat_token(chat_token)
        client.set_chat_token(chat_token)

    def _interactive_pycopilot_chat(self, client):
        """Simple interactive chat loop for pycopilot, with reauth on 401 error."""
        print("=== Copilot Chat ===")
        print("Type 'quit' or 'exit' to end the chat session")
        print("Context: Issues have been added to the conversation")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                if not user_input:
                    continue
                
                print("Assistant: ", end="", flush=True)
                
                # Stream the response, with reauth on 401
                try:
                    try:
                        for chunk in client.ask(user_input, stream=True):
                            print(chunk, end="", flush=True)
                        print()  # New line after response
                    except Exception as e:
                        if "401" in str(e) or "Unauthorized" in str(e):
                            print("[Reauthenticating...]")
                            self._reauthenticate_pycopilot(client)
                            for chunk in client.ask(user_input, stream=True):
                                print(chunk, end="", flush=True)
                            print()
                        else:
                            print(f"Error getting response: {e}")
                except Exception as e:
                    print(f"Error getting response: {e}")
                    
            except KeyboardInterrupt:
                print("\n\nChat session ended.")
                break
            except EOFError:
                print("\nChat session ended.")
                break
