# A wrapper for issues that allow us to translate atttributes to sensible names
class MyJiraIssue:
    def __init__(self, issue, field_mapping=None):
        self.issue = issue
        self.translations = field_mapping or {}
        self._jira_fields = None  # Cache for available field names

        for key in self.translations:
            try:
                # Dynamically set the attribute on this object to the value of the attribute on the issue
                setattr(self, key, getattr(issue.fields, self.translations[key]))
                setattr(self, key + "_fieldname", self.translations[key])
            except:
                setattr(self, key, "")
                setattr(self, key + "_fieldname", self.translations[key])

    def has_field(self, field_name):
        """
        Check if the issue has a field with the given name.
        Returns True if the field exists, False otherwise.
        """
        return hasattr(self.issue.fields, field_name) or (self._jira_fields != None and field_name in self._jira_fields)

    def __getattr__(self, name):
        """
        Handle missing attributes by suggesting similar field names.
        """
        if name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
            
        # Get all available field names from the issue
        if self._jira_fields is None:
            self._jira_fields = []
            try:
                # Get field names from the raw issue data
                if hasattr(self.issue, 'raw') and 'fields' in self.issue.raw:
                    for field_id, field_value in self.issue.raw['fields'].items():
                        if hasattr(self.issue.fields, field_id):
                            self._jira_fields.append(field_id)
                # Also get standard field names
                for attr_name in dir(self.issue.fields):
                    if not attr_name.startswith('_'):
                        self._jira_fields.append(attr_name)
            except:
                pass

        # Find fields that start with the same 3 letters
        suggestions = []
        if len(name) >= 3:
            prefix = name[:3].lower()
            for field_name in self._jira_fields:
                if field_name.lower().startswith(prefix) or prefix in field_name.lower():
                    suggestions.append(field_name)

        # Create error message with suggestions
        error_msg = f"'{self.__class__.__name__}' object has no attribute '{name}'"
        if suggestions:
            error_msg += f". Did you mean one of these fields: {', '.join(suggestions[:5])}"  # Limit to 5 suggestions
        
        raise AttributeError(error_msg)

    def is_spike(self):
        return self.issue.fields.issuetype.name == "Spike"
