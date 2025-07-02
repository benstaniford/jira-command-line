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
                if initial_user_message:
                    self._interactive_pycopilot_chat(client, initial_user_message=initial_user_message)
                else:
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

    def _get_jql_copilot_response(self, ui, prompt):
        # Generate JQL using Copilot and return the raw response
        if not USE_PYCOPILOT:
            return None
        from pycopilot import CopilotClient, AuthCache, CopilotAuth, AuthenticationError
        cache = AuthCache()
        chat_token = cache.get_valid_cached_chat_token()
        if not chat_token:
            bearer_token = cache.get_cached_bearer_token()
            if not bearer_token:
                return None
            auth = CopilotAuth()
            chat_token = auth.get_chat_token_from_bearer(bearer_token)
            if not chat_token:
                return None
            cache.cache_chat_token(chat_token)
        client = CopilotClient()
        client.set_chat_token(chat_token)
        response = ""
        for chunk in client.ask(prompt, stream=True):
            response += chunk
        return response

    def _extract_jql_from_response(self, response):
        if not response:
            return None
        import re
        lines = response.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('//'):
                if 'project =' in line.lower():
                    # Post-process: quote any unquoted email addresses or @-containing values
                    line = self._quote_jql_emails(line)
                    return line
        return None

    def _quote_jql_emails(self, jql):
        import re
        # This regex finds = <value> or in (<value>,...) where <value> contains @ and is not quoted
        def replacer(match):
            value = match.group(2)
            if value.startswith('"') and value.endswith('"'):
                return match.group(0)  # already quoted
            if '@' in value:
                return f"{match.group(1)}\"{value}\""
            return match.group(0)
        # For = value
        jql = re.sub(r'(=\s*)([\w@.]+)', replacer, jql)
        # For in (value1, value2, ...)
        def quote_in_values(match):
            prefix = match.group(1)
            values = match.group(2)
            quoted = ', '.join([f'"{v.strip()}"' if '@' in v and not (v.strip().startswith('"') and v.strip().endswith('"')) else v.strip() for v in values.split(',')])
            return f"{prefix}{quoted})"
        jql = re.sub(r'(in \()(.*?)(\))', lambda m: quote_in_values((m.group(1), m.group(2))) + m.group(3), jql)
        return jql

    def _build_jql_generation_prompt(self, user_query, team_name, team_id, project_name, product_name, short_names_to_ids):
        # Build the prompt for generating JQL
        team_members = ", ".join([f"{name} ({email})" for name, email in short_names_to_ids.items() if email])
        prompt = f"""You are a Jira JQL expert. Convert the following natural language query into a JQL query.

Context:
- Current team: {team_name} (ID: {team_id})
- Project: {project_name}
- Product: {product_name}
- Team members: {team_members}

User query: "{user_query}"

Requirements:
1. Always include the project filter: project = {project_name}
2. Always include the team filter: "Team[Team]" = {team_id}
3. If the user mentions themselves or team members by name, map to the appropriate email addresses
4. Use appropriate JQL syntax and field names
5. Always quote string values (e.g., assignee = \"cflynn@beyondtrust.com\")
6. Return ONLY the JQL query, no explanations

JQL Query:"""
        return prompt

    def _build_analysis_prompt(self, original_query, issues, jira):
        # Build detailed issue summaries for analysis
        issue_summaries = []
        for issue in issues:
            summary = self._detailed_summary(issue, jira)
            issue_summaries.append(summary)
        
        combined_issues = "\n\n".join(issue_summaries)
        
        prompt = f"""Based on the following Jira issues, please analyze and answer this query: "{original_query}"

Issues found:
{combined_issues}

Please provide a comprehensive analysis addressing the original query. Include relevant insights, patterns, and recommendations based on the data."""
        
        return prompt

    def _detailed_summary(self, issue, jira):
        # Create a more detailed summary for analysis
        key = getattr(issue, 'key', str(issue))
        summary = getattr(issue.fields, 'summary', "")
        status = getattr(issue.fields, 'status', None)
        status_name = getattr(status, 'name', str(status)) if status else ""
        assignee = getattr(issue.fields, 'assignee', None)
        assignee_name = str(assignee) if assignee else "Unassigned"
        created = getattr(issue.fields, 'created', "")
        updated = getattr(issue.fields, 'updated', "")
        issue_type = getattr(issue.fields, 'issuetype', None)
        issue_type_name = getattr(issue_type, 'name', str(issue_type)) if issue_type else ""
        priority = getattr(issue.fields, 'priority', None)
        priority_name = getattr(priority, 'name', str(priority)) if priority else ""
        
        # Try to get additional fields
        points = None
        try:
            points = jira.get_story_points(issue)
        except Exception:
            points = None
            
        description = getattr(issue.fields, 'description', "")
        if description and len(description) > 200:
            description = description[:200] + "..."
        
        summary_str = f"[{key}] {summary}"
        summary_str += f"\nType: {issue_type_name} | Status: {status_name} | Priority: {priority_name}"
        summary_str += f"\nAssignee: {assignee_name} | Created: {created} | Updated: {updated}"
        if points:
            summary_str += f"\nStory Points: {points}"
        if description:
            summary_str += f"\nDescription: {description}"
            
        return summary_str

    def _get_jql_from_copilot(self, ui, prompt):
        # Generate JQL using Copilot
        if not USE_PYCOPILOT:
            # Fallback - return a basic query if pycopilot not available
            return None
            
        try:
            from pycopilot import CopilotClient, AuthCache, CopilotAuth, AuthenticationError
            
            # Get authentication
            cache = AuthCache()
            chat_token = cache.get_valid_cached_chat_token()
            
            if not chat_token:
                bearer_token = cache.get_cached_bearer_token()
                if not bearer_token:
                    return None
                auth = CopilotAuth()
                chat_token = auth.get_chat_token_from_bearer(bearer_token)
                if not chat_token:
                    return None
                cache.cache_chat_token(chat_token)
            
            # Initialize client
            client = CopilotClient()
            client.set_chat_token(chat_token)
            
            # Get response
            response = ""
            for chunk in client.ask(prompt, stream=True):
                response += chunk
            
            # Extract JQL from response (remove any extra text)
            lines = response.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('//'):
                    # Basic validation - should contain project =
                    if 'project =' in line.lower():
                        return line
            
            return None
            
        except Exception as e:
            return None
