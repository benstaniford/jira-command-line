# A wrapper for issues that allow us to translate atttributes to sensible names
class MyJiraIssue:
    # Class-level cache for field mappings to avoid repeated API calls across instances
    _field_mapping_cache = None
    # Class-level cache for all Jira fields to avoid repeated API calls
    _jira_fields_cache = None
    
    def __init__(self, issue, jira_instance):
        self.issue = issue
        self.jira_instance = jira_instance
        self.translations = self.get_field_mapping(issue) if jira_instance else {}
        self._jira_fields = None  # Cache for available field names

        for key in self.translations:
            try:
                # Dynamically set the attribute on this object to the value of the attribute on the issue
                setattr(self, key, getattr(issue.fields, self.translations[key]))
                setattr(self, key + "_fieldname", self.translations[key])
            except:
                setattr(self, key, "")
                setattr(self, key + "_fieldname", self.translations[key])

    def get_field_mapping(self, issue):
        """
        Dynamically retrieve field mappings from Jira API.
        Returns a dictionary mapping friendly names to field IDs.
        """
        if not self.jira_instance:
            return {}
            
        if MyJiraIssue._field_mapping_cache is not None:
            return MyJiraIssue._field_mapping_cache
            
        try:
            # Get all fields from Jira (use cached version if available)
            if MyJiraIssue._jira_fields_cache is None:
                MyJiraIssue._jira_fields_cache = self.jira_instance.fields()
            fields = MyJiraIssue._jira_fields_cache
            
            # Create mapping based on field names
            field_mapping = {}
            
            # Standard fields (these are consistent across Jira instances)
            field_mapping["description"] = "description"
            field_mapping["summary"] = "summary"
            
            # Custom fields - map by name to ID
            for field in fields:
                field_id = field['id']
                
                # Map common field names to friendly names
                name_mappings = {
                    'repro_steps': ['repro steps', 'reproduction steps', 'steps to reproduce'],
                    'acceptance_criteria': ['acceptance criteria', 'ac'],
                    'actual_results': ['actual results', 'actual result'],
                    'expected_results': ['expected results', 'expected result'],
                    'customer_repro_steps': ['customer repro steps', 'customer reproduction steps'],
                    'test_result_evidence': ['test result evidence', 'test evidence'],
                    'relevant_environment': ['relevant environment', 'environment'],
                    'sprint': ['sprint'],
                    'story_points': ['story points', 'points'],
                    'product': ['product'],
                    'team': ['team'],
                    'test_steps': ['test steps'],
                    'impact_areas': ['impact areas'],
                    'priority_score': ['priority score']
                }

                # Unfortunately we still seem to need this for a few things
                hard_name_mappings = {
                    'test_results': 'customfield_10097',
                    'product': 'customfield_10108',
                    'team': 'customfield_10001'
                }
                
                # Check if this field matches any of our desired mappings
                for friendly_name, possible_names in name_mappings.items():
                    if any(possible_name in field['name'].lower() for possible_name in possible_names):
                        field_mapping[friendly_name] = field_id
                        break

                for key, val in hard_name_mappings.items():
                    field_mapping[key] = val;
            
            MyJiraIssue._field_mapping_cache = field_mapping
            return field_mapping
            
        except Exception as e:
            print(f"Warning: Could not retrieve field mappings from Jira API: {e}")
            # Return empty mapping to trigger field suggestions
            return {}

    @classmethod
    def refresh_field_mapping(cls):
        """
        Force refresh of field mapping cache.
        """
        cls._field_mapping_cache = None

    def has_field(self, field_name):
        """
        Check if the issue has a field with the given name.
        Returns True if the field exists, False otherwise.
        """
        return hasattr(self.issue.fields, field_name) or (self._jira_fields != None and field_name in self._jira_fields)

    def __getattr__(self, name):
        """
        Handle missing attributes by suggesting similar field names, or returning None for mapped fields that are not set.
        """
        if name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

        # If the attribute is a mapped field, return None if not set
        if hasattr(self, 'translations') and name in self.translations:
            return None

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

        # Find fields that start with the same 3 letters or custom fields that appear to have values we don't know about
        suggestions = []
        if len(name) >= 3:
            prefix = name[:3].lower()
            # Add friendly names from translations that match
            for friendly_name in self.translations.keys():
                if friendly_name.lower().startswith(prefix) or prefix in friendly_name.lower():
                    suggestions.append(friendly_name)
            # Add custom fields not mapped, not None, that match
            for field_name in self._jira_fields:
                # Only consider custom fields not in translations
                if field_name.startswith('customfield_') and field_name not in self.translations.values():
                    value = getattr(self.issue.fields, field_name, None)
                    if value is not None and isinstance(value, str):
                        suggestions.append(f"{field_name} : {value[:20]}\n")

        # Create error message with suggestions
        error_msg = f"'{self.__class__.__name__}' object has no attribute '{name}'"
        if suggestions:
            error_msg += f". Did you mean one of these fields: {', '.join(suggestions[:25])}"  # Limit to 25 suggestions
        
        raise AttributeError(error_msg)

    def is_spike(self):
        return self.issue.fields.issuetype.name == "Spike"
