import markdown
import yaml
import re
from typing import Any, List, Optional
from .MyJiraIssue import MyJiraIssue

class JiraIssueMarkdownFormatter:
    def __init__(self, jira_instance: Any):
        self.jira = jira_instance

    def add_titled_section(self, body: str, title: str, content: Optional[str]) -> str:
        if content is not None and content != "":
            body += f"## {title}\n\n{content}\n\n"
        return body

    def _add_field_section(self, wrapped_issue: Any, whole_description: str, field_name: str, section_title: str) -> str:
        if wrapped_issue.has_field(field_name):
            field_value = getattr(wrapped_issue, field_name, "")
            whole_description = self.add_titled_section(whole_description, section_title, field_value)
        return whole_description

    def _add_additional_fields(self, wrapped_issue: Any, whole_description: str, covered_fields: List[tuple]) -> str:
        try:
            all_jira_fields = self.jira.fields()
            field_id_to_name = {field['id']: field['name'] for field in all_jira_fields}
            covered_field_names = {field_name for field_name, _ in covered_fields}
            skip_fields = {
                'summary', 'description', 'issuekey', 'project', 'issuetype', 'status', 
                'resolution', 'created', 'updated', 'reporter', 'assignee', 'priority',
                'labels', 'components', 'versions', 'fixVersions', 'attachment',
                'comment', 'worklog', 'timetracking', 'votes', 'watches', 'subtasks',
                'issuelinks', 'changelog', 'transitions', 'operations', 'editmeta',
                'renderedFields', 'names', 'schema', 'expand'
            }
            issue_fields = wrapped_issue.issue.raw.get('fields', {})
            additional_fields_added = False
            for field_id, field_value in issue_fields.items():
                if field_value is None or field_value == "" or field_value == []:
                    continue
                field_name = field_id_to_name.get(field_id, field_id)
                if field_id in skip_fields or any(covered_field in field_id.lower() or covered_field in field_name.lower() 
                                                 for covered_field in covered_field_names):
                    continue
                if (field_id.startswith('customfield_') == False and 
                    field_id not in ['environment', 'duedate', 'timeestimate', 'timespent']):
                    continue
                try:
                    if hasattr(field_value, 'displayName'):
                        clean_value = field_value.displayName
                    elif hasattr(field_value, 'name'):
                        clean_value = field_value.name
                    elif hasattr(field_value, 'value'):
                        clean_value = field_value.value
                    elif isinstance(field_value, list):
                        if len(field_value) > 0:
                            if hasattr(field_value[0], 'displayName'):
                                clean_value = ', '.join([item.displayName for item in field_value])
                            elif hasattr(field_value[0], 'name'):
                                clean_value = ', '.join([item.name for item in field_value])
                            elif hasattr(field_value[0], 'value'):
                                clean_value = ', '.join([item.value for item in field_value])
                            elif isinstance(field_value[0], (dict, list)):
                                try:
                                    clean_value = f"```yaml\n{yaml.dump(field_value, default_flow_style=False, indent=2)}\n```"
                                except:
                                    clean_value = ', '.join([str(item) for item in field_value])
                            else:
                                clean_value = ', '.join([str(item) for item in field_value])
                        else:
                            continue
                    elif isinstance(field_value, dict):
                        if 'displayName' in field_value:
                            clean_value = field_value['displayName']
                        elif 'name' in field_value:
                            clean_value = field_value['name']
                        elif 'value' in field_value:
                            clean_value = field_value['value']
                        else:
                            try:
                                clean_value = f"```yaml\n{yaml.dump(field_value, default_flow_style=False, indent=2)}\n```"
                            except:
                                clean_value = str(field_value)
                    else:
                        try:
                            import json
                            if isinstance(field_value, str) and (field_value.strip().startswith('{') or field_value.strip().startswith('[')):
                                parsed_json = json.loads(field_value)
                                clean_value = f"```yaml\n{yaml.dump(parsed_json, default_flow_style=False, indent=2)}\n```"
                            else:
                                clean_value = str(field_value)
                        except:
                            clean_value = str(field_value)
                    if not clean_value or len(str(clean_value).strip()) < 1:
                        continue
                    if not additional_fields_added:
                        whole_description += "## Additional Fields\n\n"
                        additional_fields_added = True
                    display_name = field_name.replace('customfield_', '').replace('_', ' ').title()
                    whole_description = self.add_titled_section(whole_description, f"### {display_name}", clean_value)
                except Exception:
                    continue
        except Exception as e:
            print(f"Warning: Could not retrieve additional fields: {e}")
        return whole_description

    def _strip_invisible_unicode(self, text: str) -> str:
        """
        Remove invisible or special unicode characters (e.g., zero-width space, left-to-right mark, etc.) from the text.
        """
        # Remove common invisible/special unicode characters
        invisible_pattern = (
            r'[\u200B\u200C\u200D\u200E\u200F\u202A-\u202E\u2060-\u206F\uFEFF]'
        )
        return re.sub(invisible_pattern, '', text)

    def format(self, issue: Any, include_comments: bool = False, format_as_html: bool = False) -> str:
        wrapped_issue = MyJiraIssue(issue, self.jira)
        whole_description = ""
        whole_description = self.add_titled_section(whole_description, "Issue ID: ", issue.key)
        field_sections = [
            ("summary", "Summary"),
            ("description", "Description"),
            ("acceptance_criteria", "Acceptance Criteria"),
            ("test_result_evidence", "Test Result and Evidence"),
            ("repro_steps", "Reproduction Steps"),
            ("customer_repro_steps", "Steps to Reproduce"),
            ("relevant_environment", "Relevant Environment"),
            ("expected_results", "Expected Results"),
            ("actual_results", "Actual Results")
        ]
        for field_name, section_title in field_sections:
            whole_description = self._add_field_section(wrapped_issue, whole_description, field_name, section_title)
        whole_description = self._add_additional_fields(wrapped_issue, whole_description, field_sections)
        if include_comments:
            comments = self.jira.comments(issue.key)
            comments.reverse()
            for comment in comments:
                whole_description = self.add_titled_section(whole_description, f"Comment by {comment.author.displayName}", comment.body)
        whole_description = self._strip_invisible_unicode(whole_description)
        if format_as_html:
            return markdown.markdown(whole_description, extensions=['fenced_code', 'tables'])
        return whole_description
