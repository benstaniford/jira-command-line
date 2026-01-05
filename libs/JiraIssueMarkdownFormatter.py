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
            # Convert ADF content to text if needed
            if field_value and not isinstance(field_value, str):
                field_value = self._adf_to_text(field_value)
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
        Remove invisible or special unicode characters (e.g., zero-width space, left-to-right mark, etc.) and carriage returns from the text.
        """
        # Remove common invisible/special unicode characters
        invisible_pattern = (
            r'[\u200B\u200C\u200D\u200E\u200F\u202A-\u202E\u2060-\u206F\uFEFF]'
        )
        text = re.sub(invisible_pattern, '', text)
        # Remove carriage return characters
        text = text.replace('\r', '')
        return text

    def _unwrap_property_holder(self, obj: Any) -> Any:
        """
        Unwrap a Jira PropertyHolder object to get its actual data by recursively converting it to dict.
        """
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj

        if isinstance(obj, dict):
            # Recursively unwrap dict values
            return {k: self._unwrap_property_holder(v) for k, v in obj.items()}

        if isinstance(obj, list):
            # Recursively unwrap list items
            return [self._unwrap_property_holder(item) for item in obj]

        if not hasattr(obj, '__dict__'):
            return str(obj) if obj else ""

        # Try common attributes first
        for attr in ['raw', '_raw']:
            if hasattr(obj, attr):
                raw_val = getattr(obj, attr)
                # Recursively unwrap the raw value
                return self._unwrap_property_holder(raw_val)

        # Build dict from all public attributes recursively
        obj_dict = {}
        try:
            for key in dir(obj):
                if key.startswith('_') or key in ['raw', 'self']:
                    continue
                try:
                    value = getattr(obj, key)
                    if not callable(value):
                        # Recursively unwrap nested objects
                        obj_dict[key] = self._unwrap_property_holder(value)
                except:
                    continue

            # Return the constructed dictionary if it has content
            if obj_dict:
                return obj_dict
        except:
            pass

        return ""

    def _adf_to_text(self, adf_content: Any) -> str:
        """
        Convert Atlassian Document Format (ADF) to plain text.
        Args:
            adf_content: ADF content (can be dict, object, or string)
        Returns:
            Plain text string
        """
        # Unwrap PropertyHolder first
        adf_content = self._unwrap_property_holder(adf_content)

        # Handle if it's already a string
        if isinstance(adf_content, str):
            return adf_content

        # Handle if it's still not a dict
        if not isinstance(adf_content, dict):
            return str(adf_content) if adf_content else ""

        # Process ADF structure
        text_parts = []

        def extract_text(node):
            if isinstance(node, dict):
                node_type = node.get('type', '')

                # Text node
                if node_type == 'text':
                    text_parts.append(node.get('text', ''))

                # Hard break
                elif node_type == 'hardBreak':
                    text_parts.append('\n')

                # Paragraph - add newline after
                elif node_type == 'paragraph':
                    if 'content' in node:
                        for child in node['content']:
                            extract_text(child)
                    text_parts.append('\n\n')

                # Heading
                elif node_type == 'heading':
                    level = node.get('attrs', {}).get('level', 1)
                    text_parts.append('#' * level + ' ')
                    if 'content' in node:
                        for child in node['content']:
                            extract_text(child)
                    text_parts.append('\n\n')

                # List items
                elif node_type in ['bulletList', 'orderedList']:
                    if 'content' in node:
                        for item in node['content']:
                            extract_text(item)

                elif node_type == 'listItem':
                    text_parts.append('- ')
                    if 'content' in node:
                        for child in node['content']:
                            extract_text(child)

                # Code block
                elif node_type == 'codeBlock':
                    text_parts.append('```\n')
                    if 'content' in node:
                        for child in node['content']:
                            extract_text(child)
                    text_parts.append('```\n\n')

                # Generic content processing
                elif 'content' in node:
                    for child in node['content']:
                        extract_text(child)

            elif isinstance(node, list):
                for item in node:
                    extract_text(item)

        extract_text(adf_content)
        result = ''.join(text_parts).strip()

        # Clean up excessive newlines
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result

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
                # Convert ADF comment body to plain text
                comment_text = self._adf_to_text(comment.body)
                if comment_text:  # Only add non-empty comments
                    whole_description = self.add_titled_section(whole_description, f"Comment by {comment.author.displayName}", comment_text)
        whole_description = self._strip_invisible_unicode(whole_description)
        if format_as_html:
            return markdown.markdown(whole_description, extensions=['fenced_code', 'tables'])
        return whole_description
