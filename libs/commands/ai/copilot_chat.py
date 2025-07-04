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

    def interactive_chat(self, client, initial_user_message=None):
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
                        for chunk in self.ask_with_reauth(user_input, stream=True, client=client):
                            buffer += chunk
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                print(colorize_markdown(line), flush=True)
                        if buffer:
                            print(colorize_markdown(buffer), flush=True)
                    except Exception as e:
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

    def build_jql_generation_prompt(self, user_query, team_name, team_id, project_name, product_name, short_names_to_ids):
        """Build the prompt for generating JQL from natural language query."""
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

    def get_jql_response(self, prompt):
        """Generate JQL using Copilot and return the raw response, with robust reauth on auth error."""
        try:
            response = ""
            for chunk in self.ask_with_reauth(prompt, stream=True):
                response += chunk
            return response
        except Exception as e:
            raise Exception(f"Copilot authentication failed after retry: {e}")

    def extract_jql_from_response(self, response):
        """
        Extracts the JQL query from a Copilot response.
        Looks for the first line that contains 'project =' and is not a comment or markdown/code block.
        Strips markdown/code block formatting and returns the JQL string.
        Returns None if no JQL is found.
        """
        import re
        if not response:
            print("[DEBUG] Copilot response is empty.")
            return None
        # Remove all code block markers (start and end)
        response = response.strip()
        response = re.sub(r'^```[a-zA-Z]*', '', response)
        response = re.sub(r'```$', '', response)
        # Split into lines and look for JQL
        lines = response.split('\n') if '\n' in response else response.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            # Remove trailing code block markers
            if line.endswith('```'):
                line = line[:-3].strip()
            # Heuristic: must contain 'project ='
            if 'project =' in line.lower():
                # Remove any trailing comment
                line = line.split('//')[0].strip()
                return line
        print(f"[DEBUG] No JQL found in Copilot response:\n{response}")
        return None

    def build_analysis_prompt(self, user_query, issues, jira):
        """Build a prompt for Copilot to analyze the results of a JQL query."""
        summaries = []
        for issue in issues:
            key = getattr(issue, 'key', str(issue))
            summary = getattr(issue.fields, 'summary', "")
            status = getattr(issue.fields, 'status', None)
            status_name = getattr(status, 'name', str(status)) if status else ""
            assignee = getattr(issue.fields, 'assignee', None)
            assignee_name = str(assignee) if assignee else "Unassigned"
            summaries.append(f"[{key}] {summary} (Status: {status_name}, Assignee: {assignee_name})")
        issues_str = "\n".join(summaries)
        prompt = (
            f"Analyze the following Jira issues for the query: '{user_query}'.\n"
            f"Issues:\n{issues_str}\n"
            "Provide insights, trends, or recommendations based on these results."
        )
        return prompt

    def short_summary(self, issue, jira):
        """Compose a short summary string for the issue."""
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
