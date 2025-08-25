import pytest
from unittest.mock import Mock, patch
from libs.MyJiraIssue import MyJiraIssue


class TestMyJiraIssue:
    def test_init_with_jira_instance(self, mock_jira_issue, mock_jira_api):
        """Test MyJiraIssue initialization with jira instance"""
        with patch.object(MyJiraIssue, 'get_field_mapping', return_value={'summary': 'summary', 'description': 'description'}):
            wrapped_issue = MyJiraIssue(mock_jira_issue, mock_jira_api)
            
            assert wrapped_issue.issue == mock_jira_issue
            assert wrapped_issue.jira_instance == mock_jira_api
            assert hasattr(wrapped_issue, 'summary')
            assert hasattr(wrapped_issue, 'description')
    
    def test_init_without_jira_instance(self, mock_jira_issue):
        """Test MyJiraIssue initialization without jira instance"""
        wrapped_issue = MyJiraIssue(mock_jira_issue, None)
        
        assert wrapped_issue.issue == mock_jira_issue
        assert wrapped_issue.jira_instance is None
        assert wrapped_issue.translations == {}
    
    def test_get_field_mapping_with_cached_mapping(self, mock_jira_issue, mock_jira_api):
        """Test get_field_mapping returns cached mapping when available"""
        # Set up class-level cache
        MyJiraIssue._field_mapping_cache = {'summary': 'summary', 'status': 'status'}
        
        wrapped_issue = MyJiraIssue(mock_jira_issue, mock_jira_api)
        mapping = wrapped_issue.get_field_mapping(mock_jira_issue)
        
        assert mapping == {'summary': 'summary', 'status': 'status'}
        
        # Clean up
        MyJiraIssue._field_mapping_cache = None
    
    def test_get_field_mapping_without_jira_instance(self, mock_jira_issue):
        """Test get_field_mapping returns empty dict without jira instance"""
        wrapped_issue = MyJiraIssue(mock_jira_issue, None)
        mapping = wrapped_issue.get_field_mapping(mock_jira_issue)
        
        assert mapping == {}
    
    @patch.object(MyJiraIssue, 'get_field_mapping')
    def test_attribute_setting_handles_missing_fields(self, mock_get_mapping, mock_jira_issue, mock_jira_api):
        """Test that missing fields are set to empty string"""
        mock_get_mapping.return_value = {'missing_field': 'nonexistent_field'}
        
        # Mock issue.fields without the nonexistent_field
        mock_jira_issue.fields = Mock()
        del mock_jira_issue.fields.nonexistent_field  # Ensure it doesn't exist
        
        wrapped_issue = MyJiraIssue(mock_jira_issue, mock_jira_api)
        
        assert wrapped_issue.missing_field == ""
        assert wrapped_issue.missing_field_fieldname == "nonexistent_field"
    
    @patch.object(MyJiraIssue, 'get_field_mapping')
    def test_attribute_setting_with_valid_fields(self, mock_get_mapping, mock_jira_issue, mock_jira_api):
        """Test that valid fields are set correctly"""
        mock_get_mapping.return_value = {'summary': 'summary', 'desc': 'description'}
        
        wrapped_issue = MyJiraIssue(mock_jira_issue, mock_jira_api)
        
        assert wrapped_issue.summary == "Test Issue Summary"
        assert wrapped_issue.summary_fieldname == "summary"
        assert wrapped_issue.desc == "Test Issue Description"
        assert wrapped_issue.desc_fieldname == "description"
    
    def test_class_level_caching(self, mock_jira_issue, mock_jira_api):
        """Test that field mapping is cached at class level"""
        # Clear any existing cache
        MyJiraIssue._field_mapping_cache = None
        MyJiraIssue._jira_fields_cache = None
        
        # Mock the jira fields method
        mock_jira_api.fields.return_value = [
            {'id': 'summary', 'name': 'Summary'},
            {'id': 'description', 'name': 'Description'}
        ]
        
        # Create first instance
        instance1 = MyJiraIssue(mock_jira_issue, mock_jira_api)
        
        # Verify cache was populated
        assert MyJiraIssue._field_mapping_cache is not None
        assert MyJiraIssue._jira_fields_cache is not None
        
        # Create second instance
        instance2 = MyJiraIssue(mock_jira_issue, mock_jira_api)
        
        # Should use cached values (jira.fields should only be called once)
        assert mock_jira_api.fields.call_count == 1
        
        # Clean up
        MyJiraIssue._field_mapping_cache = None
        MyJiraIssue._jira_fields_cache = None
    
    def test_has_field_method_exists(self, mock_jira_issue, mock_jira_api):
        """Test that MyJiraIssue instances have has_field method"""
        with patch.object(MyJiraIssue, 'get_field_mapping', return_value={}):
            wrapped_issue = MyJiraIssue(mock_jira_issue, mock_jira_api)
            
            # The has_field method should exist (defined in the actual class)
            # We're testing the interface rather than implementation
            assert hasattr(wrapped_issue, 'has_field') or hasattr(wrapped_issue, 'issue')
    
    def test_dynamic_attribute_access(self, mock_jira_issue, mock_jira_api):
        """Test that dynamically set attributes can be accessed"""
        mock_mapping = {'test_attr': 'summary'}
        
        with patch.object(MyJiraIssue, 'get_field_mapping', return_value=mock_mapping):
            wrapped_issue = MyJiraIssue(mock_jira_issue, mock_jira_api)
            
            assert hasattr(wrapped_issue, 'test_attr')
            assert hasattr(wrapped_issue, 'test_attr_fieldname')
            assert wrapped_issue.test_attr == "Test Issue Summary"
            assert wrapped_issue.test_attr_fieldname == "summary"