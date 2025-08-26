from .base_command import BaseCommand
from jira_utils import write_issue_for_chat
from .ai.copilot_chat import CopilotChat


class ChatCommand(BaseCommand):
    def __init__(self):
        self.copilot = CopilotChat()

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
                submenu_choice = ui.prompt_get_string_colored(submenu_prompt, keypresses=["C", "S", "c", "s", "q"], filter_key=None, sort_keys=None, search_key=None).strip()
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
            selection = ui.prompt_get_string_colored("Enter comma separated issue numbers (e.g. 1,2,3) or hit enter to discuss all issues in the view")
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
            self._chat_with_pycopilot(ui, issues, jira)
        except Exception as e:
            ui.error("Chat about issue", e)
        return False

    def _summary_flow(self, ui, view, jira, brief=False):
        try:
            selection = ui.prompt_get_string_colored("Enter comma separated issue numbers (e.g. 1,2,3) or hit enter to summarize all issues in the view")
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
                summary = self.copilot.short_summary(issue, jira)
                summary_prompts.append(summary)
            combined_summary = "\n\n".join(summary_prompts)
            canned_prompt = f"Please provide a concise summary or analysis of the following Jira issues.\n\n{combined_summary}\n\nPlease also suggest some follow-up questions that would be suitable for an amigos/refinement."
            if brief:
                canned_prompt = f"Please provide a brief summary of the following Jira issues, do so in a single paragraph per item:\n\n{combined_summary}"
            # Start chat with the canned prompt as the first user message
            self._chat_with_pycopilot(ui, issues, jira, initial_user_message=canned_prompt)
        except Exception as e:
            ui.error("Summary error", e)
        return False

    def _chat_with_pycopilot(self, ui, issues, jira, initial_user_message=None):
        client, _ = self.copilot.chat_with_issues(issues, jira)
        ui.yield_screen()
        if initial_user_message:
            self._interactive_pycopilot_chat(client, initial_user_message=initial_user_message)
        else:
            self._interactive_pycopilot_chat(client)
        ui.restore_screen()

    def _interactive_pycopilot_chat(self, client, initial_user_message=None):
        self.copilot.interactive_chat(client, initial_user_message=initial_user_message)

    def _query_flow(self, ui, view, jira, config):
        try:
            # Get natural language query from user
            query = ui.prompt_get_string_colored("Enter your natural language query about Jira tickets:")
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
            jql_prompt = self.copilot.build_jql_generation_prompt(query, team_name, team_id, project_name, product_name, short_names_to_ids)
            
            # Get JQL from Copilot
            try:
                copilot_response = self.copilot.get_jql_response(jql_prompt)
            except Exception as e:
                ui.error("Copilot authentication failed after retry. Please re-authenticate.", e)
                return False
            print("\n===== Raw Copilot JQL response =====\n")
            print(copilot_response)
            print("\n===== End Copilot JQL response =====\n")
            jql_query = self.copilot.extract_jql_from_response(copilot_response)
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
                analysis_prompt = self.copilot.build_analysis_prompt(query, issues, jira)
                
                # Start chat with the analysis, then allow user to continue chatting
                self._chat_with_pycopilot(ui, issues, jira, initial_user_message=analysis_prompt)
                # After initial analysis, user can continue chatting as in regular chat mode
            except Exception as e:
                ui.error("JQL execution", e)
                return False
                
        except Exception as e:
            ui.error("Query flow error", e)
        return False