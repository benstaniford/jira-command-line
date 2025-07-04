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
            submenu_prompt = "Chat submenu:\nC:chat S:summary s:short_summary q:query\nEnter choice or esc to cancel"
            while True:
                submenu_choice = ui.prompt_get_string(submenu_prompt, keypresses=["C", "S", "c", "s", "q"], filter_key=None, sort_keys=None, search_key=None).strip()
                if submenu_choice == "C":
                    self._chat_flow(ui, view, jira)
                    break
                elif submenu_choice == "S":
                    self._summary_flow(ui, view, jira, brief=False)
                    break
                elif submenu_choice == "s":
                    self._summary_flow(ui, view, jira, brief=True)
                    break
                elif submenu_choice == "q":
                    self._query_flow(ui, view, jira, kwargs.get('config'))
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

    def _summary_flow(self, ui, view, jira, brief=False):
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
            # Compose a pre-canned summary prompt for the selected issues
            summary_prompts = []
            for issue in issues:
                summary = self._short_summary(issue, jira)
                summary_prompts.append(summary)
            combined_summary = "\n\n".join(summary_prompts)
            canned_prompt = f"Please provide a concise summary or analysis of the following Jira issues.\n\n{combined_summary}\n\nPlease also suggest some follow-up questions that would be suitable for an amigos/refinement."
            if brief:
                canned_prompt = f"Please provide a brief summary of the following Jira issues, do so in a single paragraph per item:\n\n{combined_summary}"
            # Start chat with the canned prompt as the first user message
            if USE_PYCOPILOT:
                self._chat_with_pycopilot(ui, issues, jira, initial_user_message=canned_prompt)
            else:
                self._chat_with_ragchat(ui, issues, jira, initial_user_message=canned_prompt)
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
    
    def _chat_with_ragchat(self, ui, issues, jira, initial_user_message=None):
        """Chat using RagChat library"""
        from RagChat import RagChat
        chat = RagChat()
        for issue in issues:
            chat.add_document(write_issue_for_chat(issue, jira))

        ui.yield_screen()
        if initial_user_message:
            chat.chat(initial_user_message=initial_user_message)
        else:
            chat.chat()
        ui.restore_screen()
    
    def _chat_with_pycopilot(self, ui, issues, jira, initial_user_message=None):
        """Chat using pycopilot library with cached authentication"""
        try:
            from pycopilot import AuthenticationError, AuthCache
            self.auth = AuthCache()
            import tempfile
            import os
            client = self.auth.authenticate()
            temp_files = []
            try:
                # Add issues as context
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
                ui.yield_screen()
                if initial_user_message:
                    self._interactive_pycopilot_chat(client, initial_user_message=initial_user_message)
                else:
                    self._interactive_pycopilot_chat(client)
                ui.restore_screen()
            finally:
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

    def _interactive_pycopilot_chat(self, client, initial_user_message=None):
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
        
        first_message = True
        while True:
            try:
                if first_message and initial_user_message:
                    user_input = initial_user_message.strip()
                    first_message = False
                else:
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
                            client = self.auth.authenticate()
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

    def _query_flow(self, ui, view, jira, config):
        try:
            # Get natural language query from user
            query = ui.prompt_get_string("Enter your natural language query about Jira tickets:")
            if not query.strip():
                return False
            
            ui.prompt("Generating JQL query...")
            
            # Get team context from config
            team_name = jira.team_name
            team_id = jira.team_id
            project_name = jira.project_name
            product_name = jira.product_name
            short_names_to_ids = jira.short_names_to_ids
            
            # Build context for JQL generation
            jql_prompt = self._build_jql_generation_prompt(query, team_name, team_id, project_name, product_name, short_names_to_ids)
            
            # Get JQL from Copilot
            copilot_response = self._get_jql_copilot_response(ui, jql_prompt)
            print("\n===== Raw Copilot JQL response =====\n")
            print(copilot_response)
            print("\n===== End Copilot JQL response =====\n")
            jql_query = self._extract_jql_from_response(copilot_response)
            if not jql_query:
                ui.error("Query generation", Exception("Failed to generate JQL query"))
                return False
            
            print(f"\nGenerated JQL: {jql_query}\n")
            
            # Execute the JQL query
            ui.prompt("Executing JQL query...")
            try:
                issues = jira.search_issues(jql_query)
                if len(issues) == 0:
                    ui.prompt("No issues found for this query. Press any key to continue.", " ")
                    return False
                elif len(issues) > 20:
                    ui.prompt(f"Query returned {len(issues)} issues (max 20 for analysis). Showing first 20. Press any key to continue.", " ")
                    issues = issues[:20]
                else:
                    ui.prompt(f"Found {len(issues)} issues. Analyzing with Copilot...")
                
                # Provide full context to Copilot for analysis
                analysis_prompt = self._build_analysis_prompt(query, issues, jira)
                
                # Start chat with the analysis, then allow user to continue chatting
                if USE_PYCOPILOT:
                    self._chat_with_pycopilot(ui, issues, jira, initial_user_message=analysis_prompt)
                else:
                    self._chat_with_ragchat(ui, issues, jira, initial_user_message=analysis_prompt)
                # After initial analysis, user can continue chatting as in regular chat mode
            except Exception as e:
                ui.error("JQL execution", e)
                return False
                
        except Exception as e:
            ui.error("Query flow error", e)
        return False

    def _build_jql_generation_prompt(self, user_query, team_name, team_id, project_name, product_name, short_names_to_ids):
        # Build the prompt for generating JQL
        team_members = ", ".join([f"{name} ({email})" for name, email in short_names_to_ids.items() if email])

        # --- Get valid custom fields (friendly name and field id) ---
        try:
            from libs.MyJiraIssue import MyJiraIssue
            jira_instance = None
            import sys
            if 'jira' in sys.modules:
                jira_instance = sys.modules['jira']
            import inspect
            frame = inspect.currentframe()
            while frame:
                if 'jira' in frame.f_locals:
                    jira_instance = frame.f_locals['jira']
                    break
                frame = frame.f_back
            field_mapping = {}
            if jira_instance:
                try:
                    issues = jira_instance.search_issues(f'project = {project_name}', changelog=False)
                    if issues and len(issues) > 0:
                        issue = issues[0]
                        field_mapping = MyJiraIssue(issue, jira_instance).get_field_mapping(issue)
                    else:
                        fields = jira_instance.fields()
                        for field in fields:
                            field_mapping[field['name']] = field['id']
                except Exception:
                    fields = jira_instance.fields()
                    for field in fields:
                        field_mapping[field['name']] = field['id']
            else:
                field_mapping = {}
        except Exception:
            field_mapping = {}

        # Format the custom fields for the prompt
        if field_mapping:
            custom_fields_str = "\n".join([f"- {friendly} (id: {fid})" for friendly, fid in field_mapping.items()])
            custom_fields_section = f"\nValid custom fields for this project/team (use only these):\n{custom_fields_str}\n"
        else:
            custom_fields_section = ""

        prompt = f"""You are a Jira JQL expert. Convert the following natural language query into a JQL query.

Context:
- Current team: {team_name} (ID: {team_id})
- Project: {project_name}
- Product: {product_name}
- Team members: {team_members}
{custom_fields_section}
User query: "{user_query}"

Requirements:
1. Always include the project filter: project = {project_name}
2. Always include the team filter: "Team[Team]" = {team_id}
3. If the user mentions themselves or team members by name, map to the appropriate email addresses
4. Use appropriate JQL syntax and field names
5. Only use custom fields listed above (by friendly name or id)
6. Always quote string values (e.g., assignee = \"cflynn@beyondtrust.com\")
7. Return ONLY the JQL query, no explanations

JQL Query:"""
        return prompt

    def _get_jql_copilot_response(self, ui, prompt):
        # Generate JQL using Copilot and return the raw response, with robust reauth on auth error
        if not USE_PYCOPILOT:
            return None
        from pycopilot import CopilotClient
        try:
            from pycopilot.exceptions import APIError
        except ImportError:
            class APIError(Exception): pass
        client = self.auth.authenticate()
        response = ""
        tried_reauth = False
        try:
            while True:
                try:
                    for chunk in client.ask(prompt, stream=True):
                        response += chunk
                    break
                except Exception as e:
                    msg = str(e)
                    is_auth = False
                    if isinstance(e, APIError):
                        if hasattr(e, 'status_code') and e.status_code == 401:
                            is_auth = True
                        elif '401' in msg or 'Unauthorized' in msg:
                            is_auth = True
                    elif '401' in msg or 'Unauthorized' in msg:
                        is_auth = True
                    if is_auth and not tried_reauth:
                        client = self.auth.authenticate()
                        response = ""
                        tried_reauth = True
                        continue
                    raise
            return response
        except Exception as e:
            msg = str(e)
            if '401' in msg or 'Unauthorized' in msg:
                ui.error("Copilot authentication failed after retry. Please re-authenticate.", e)
                return None
            raise

    def _get_jql_from_copilot(self, ui, prompt):
        # Generate JQL using Copilot, robust reauth on auth error
        if not USE_PYCOPILOT:
            return None
        try:
            client = self.auth.authenticate()
            response = ""
            tried_reauth = False
            try:
                while True:
                    try:
                        for chunk in client.ask(prompt, stream=True):
                            response += chunk
                        break
                    except Exception as e:
                        msg = str(e)
                        is_auth = False
                        if isinstance(e, APIError):
                            if hasattr(e, 'status_code') and e.status_code == 401:
                                is_auth = True
                            elif '401' in msg or 'Unauthorized' in msg:
                                is_auth = True
                        elif '401' in msg or 'Unauthorized' in msg:
                            is_auth = True
                        if is_auth and not tried_reauth:
                            client = self.auth.authenticate()
                            response = ""
                            tried_reauth = True
                            continue
                        return None
                # Extract JQL from response (remove any extra text)
                lines = response.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('//'):
                        if 'project =' in line.lower():
                            return line
                return None
            except Exception as e:
                msg = str(e)
                if '401' in msg or 'Unauthorized' in msg:
                    ui.error("Copilot authentication failed after retry. Please re-authenticate.", e)
                    return None
                raise
        except Exception as e:
            return None
