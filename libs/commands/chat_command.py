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
            # Submenu for chat feature
            submenu_prompt = "Chat submenu:\nC: Chat about issues\nS: Short summary of issues\nPress key (C/S) or Esc to cancel"
            while True:
                submenu_choice = ui.prompt_get_string(submenu_prompt, keypresses=["C", "S", "c", "s"], filter_key=None, sort_keys=None, search_key=None).strip().upper()
                if submenu_choice == "C":
                    self._chat_flow(ui, view, jira)
                    break
                elif submenu_choice == "S":
                    self._summary_flow(ui, view, jira)
                    break
                elif submenu_choice == "":
                    # Esc or Enter cancels
                    return False
        except Exception as e:
            ui.error("Chat submenu error", e)
        return False

    def _chat_flow(self, ui, view, jira):
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

    def _summary_flow(self, ui, view, jira):
        try:
            selection = ui.prompt_get_string("Enter comma separated issue numbers (e.g. 1,2,3) or hit enter to summarize all issues in the view")
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
            # Show a short summary for each issue
            for issue in issues:
                summary = self._short_summary(issue, jira)
                ui.prompt(summary, prompt_suffix=" (press any key)")
        except Exception as e:
            ui.error("Summary error", e)
        return False

    def _short_summary(self, issue, jira):
        # Compose a short summary string for the issue
        key = getattr(issue, 'key', str(issue))
        summary = getattr(issue.fields, 'summary', "")
        status = getattr(issue.fields, 'status', None)
        status_name = getattr(status, 'name', str(status)) if status else ""
        assignee = getattr(issue.fields, 'assignee', None)
        assignee_name = str(assignee) if assignee else "Unassigned"
        created = getattr(issue.fields, 'created', "")
        updated = getattr(issue.fields, 'updated', "")
        # Try to get points if available
        points = None
        try:
            points = jira.get_story_points(issue)
        except Exception:
            points = None
        summary_str = f"[{key}] {summary}\nStatus: {status_name}\nAssignee: {assignee_name}\nCreated: {created}\nUpdated: {updated}"
        if points is not None:
            summary_str += f"\nPoints: {points}"
        return summary_str
    
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
        """Simple interactive chat loop for pycopilot, with reauth on 401 error, with colors, emojis, and markdown colorization."""
        try:
            from colorama import Fore, Style, init as colorama_init
            colorama_init(autoreset=True)
            COLORAMA = True
        except ImportError:
            COLORAMA = False
            Fore = Style = type('', (), {'RESET_ALL': '', 'BRIGHT': '', 'CYAN': '', 'GREEN': '', 'YELLOW': '', 'RED': '', 'MAGENTA': '', 'WHITE': ''})()

        import re
        def c(text, color):
            return f"{color}{text}{Style.RESET_ALL}" if COLORAMA else text

        def colorize_markdown(line):
            # Code block (simple, not multi-line)
            if line.strip().startswith('```'):
                return c(line, Fore.GREEN + Style.BRIGHT)
            # Headers (skip bold for headers)
            if re.match(r"^# ", line):
                return c(line, Fore.MAGENTA + Style.BRIGHT)
            if re.match(r"^## ", line):
                return c(line, Fore.CYAN + Style.BRIGHT)
            if re.match(r"^### ", line):
                return c(line, Fore.BLUE + Style.BRIGHT)
            # Inline formatting for non-headers
            # Bold
            line = re.sub(r"\*\*(.*?)\*\*", lambda m: c(m.group(1), Fore.YELLOW + Style.BRIGHT), line)
            # Italic (avoid matching inside bold)
            line = re.sub(r"(?<!\*)\*(?!\*)(.*?)\*(?!\*)", lambda m: c(m.group(1), Fore.GREEN), line)
            # Inline code
            line = re.sub(r"`([^`]+)`", lambda m: c(m.group(1), Fore.CYAN), line)
            # Lists (after inline formatting)
            if re.match(r"^\s*\d+\. ", line):
                return c(line, Fore.WHITE)
            if re.match(r"^\s*[-*] ", line):
                return c(line, Fore.WHITE)
            return line

        assistant_emoji = "🤖"
        user_emoji = "🧑"
        system_emoji = "⚙️"
        error_emoji = "❌"
        reauth_emoji = "🔑"

        print(c(f"=== {assistant_emoji} Copilot Chat ===", Fore.CYAN))
        print(c(f"Type 'quit' or 'exit' to end the chat session", Fore.YELLOW))
        print(c(f"Context: Issues have been added to the conversation", Fore.GREEN))
        print(c("-" * 50, Fore.MAGENTA))
        
        while True:
            try:
                user_input = input(c(f"\n{user_emoji} You: ", Fore.YELLOW)).strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                if not user_input:
                    continue
                
                print(c(f"{assistant_emoji} Assistant: ", Fore.CYAN), end="", flush=True)
                
                # Stream the response, with reauth on 401
                def stream_and_colorize():
                    buffer = ""
                    try:
                        for chunk in client.ask(user_input, stream=True):
                            buffer += chunk
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                print(colorize_markdown(line), flush=True)
                        if buffer:
                            print(colorize_markdown(buffer), flush=True)
                    except Exception as e:
                        if "401" in str(e) or "Unauthorized" in str(e):
                            print(c(f"[{reauth_emoji} Reauthenticating...]", Fore.YELLOW))
                            self._reauthenticate_pycopilot(client)
                            stream_and_colorize()
                        else:
                            print(c(f"{error_emoji} Error getting response: {e}", Fore.RED))
                try:
                    stream_and_colorize()
                except Exception as e:
                    print(c(f"{error_emoji} Error getting response: {e}", Fore.RED))
                    
            except KeyboardInterrupt:
                print(c(f"\n\n{system_emoji} Chat session ended.", Fore.MAGENTA))
                break
            except EOFError:
                print(c(f"\n{system_emoji} Chat session ended.", Fore.MAGENTA))
                break
