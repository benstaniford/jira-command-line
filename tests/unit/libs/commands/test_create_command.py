import pytest
from unittest.mock import Mock, patch, MagicMock
from libs.commands.create_command import CreateCommand
from libs.ViewMode import ViewMode


class TestCreateCommand:
    def test_shortcut_property(self):
        """Test that CreateCommand has correct shortcut"""
        command = CreateCommand()
        assert command.shortcut == "c"
    
    def test_description_property(self):
        """Test that CreateCommand has correct description"""
        command = CreateCommand()
        assert command.description == "create"
    
    def test_execute_backlog_issue_creation(self, mock_ui, mock_view, mock_jira_api):
        """Test creating a backlog issue"""
        mock_view.mode = ViewMode.BACKLOG
        mock_ui.prompt_get_string.side_effect = ["Test Summary", "Test Description", ""]  # Empty Found In build
        mock_ui.prompt_with_choice_list.side_effect = [[0, "(Skip - No Component)"], [0, "Story"]]  # Component then issue type
        
        # Mock reference issue and project components
        mock_jira_api.reference_issue = Mock()
        mock_jira_api.reference_issue.fields.project.id = "12345"
        mock_jira_api.jira.project_components.return_value = []
        
        mock_issue = Mock()
        mock_issue.key = "TEST-123"
        mock_jira_api.create_backlog_issue.return_value = mock_issue
        mock_jira_api.get_possible_types.return_value = ["Story", "Bug", "Task"]
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_jira_api.create_backlog_issue.assert_called_once_with("Test Summary", "Test Description", "Story", None, None)
        mock_ui.prompt.assert_called_with("Created TEST-123...")
        mock_view.refresh.assert_called_once()
        assert result is False
    
    def test_execute_sprint_issue_creation(self, mock_ui, mock_view, mock_jira_api):
        """Test creating a sprint issue"""
        mock_view.mode = ViewMode.SPRINT
        mock_ui.prompt_get_string.side_effect = ["Sprint Summary", "Sprint Description", "1.2.3"]  # With Found In build
        mock_ui.prompt_with_choice_list.side_effect = [[0, "(Skip - No Component)"], [1, "Bug"]]  # Component then issue type
        
        # Mock reference issue and project components  
        mock_jira_api.reference_issue = Mock()
        mock_jira_api.reference_issue.fields.project.id = "12345"
        mock_jira_api.jira.project_components.return_value = []
        
        mock_issue = Mock()
        mock_issue.key = "TEST-456"
        mock_jira_api.create_sprint_issue.return_value = mock_issue
        mock_jira_api.get_possible_types.return_value = ["Story", "Bug", "Task"]
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_jira_api.create_sprint_issue.assert_called_once_with("Sprint Summary", "Sprint Description", "Bug", "1.2.3", None)
        mock_ui.prompt.assert_called_with("Created TEST-456...")
        mock_view.refresh.assert_called_once()
        assert result is False
    
    def test_execute_sub_task_creation(self, mock_ui, mock_view, mock_jira_api):
        """Test creating a sub-task in task view"""
        mock_view.mode = ViewMode.TASKVIEW
        mock_view.parent_issue = Mock()
        mock_view.parent_issue.key = "PARENT-123"
        
        mock_ui.prompt_get_string.side_effect = ["Sub-task Summary", "Sub-task Description"]
        mock_ui.prompt_get_character.return_value = "y"
        
        mock_subtask = Mock()
        mock_subtask.key = "SUB-789"
        mock_jira_api.create_sub_task.return_value = mock_subtask
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_jira_api.create_sub_task.assert_called_once_with(
            mock_view.parent_issue, "Sub-task Summary", "Sub-task Description"
        )
        mock_jira_api.assign_to_me.assert_called_once_with(mock_subtask)
        mock_ui.prompt.assert_called_with("Created SUB-789...")
        assert result is False
    
    def test_execute_sub_task_no_assignment(self, mock_ui, mock_view, mock_jira_api):
        """Test creating a sub-task without assignment"""
        mock_view.mode = ViewMode.TASKVIEW
        mock_view.parent_issue = Mock()
        mock_view.parent_issue.key = "PARENT-123"
        
        mock_ui.prompt_get_string.side_effect = ["Sub-task Summary", "Sub-task Description"]
        mock_ui.prompt_get_character.return_value = "n"
        
        mock_subtask = Mock()
        mock_subtask.key = "SUB-789"
        mock_jira_api.create_sub_task.return_value = mock_subtask
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_jira_api.create_sub_task.assert_called_once()
        mock_jira_api.assign_to_me.assert_not_called()
        assert result is False
    
    def test_execute_empty_summary_returns_false(self, mock_ui, mock_view, mock_jira_api):
        """Test that empty summary returns False without creating issue"""
        mock_ui.prompt_get_string.return_value = ""
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_jira_api.create_backlog_issue.assert_not_called()
        mock_jira_api.create_sprint_issue.assert_not_called()
        mock_jira_api.create_sub_task.assert_not_called()
        assert result is False
    
    def test_execute_empty_description_returns_false(self, mock_ui, mock_view, mock_jira_api):
        """Test that empty description returns False without creating issue"""
        mock_ui.prompt_get_string.side_effect = ["Valid Summary", ""]
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_jira_api.create_backlog_issue.assert_not_called()
        mock_jira_api.create_sprint_issue.assert_not_called()
        mock_jira_api.create_sub_task.assert_not_called()
        assert result is False
    
    def test_execute_empty_issue_type_returns_false(self, mock_ui, mock_view, mock_jira_api):
        """Test that empty issue type returns False without creating issue"""
        mock_view.mode = ViewMode.BACKLOG
        mock_ui.prompt_get_string.side_effect = ["Summary", "Description"]
        mock_ui.prompt_with_choice_list.return_value = [0, ""]  # Empty type
        mock_jira_api.get_possible_types.return_value = ["Story", "Bug"]
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_jira_api.create_backlog_issue.assert_not_called()
        assert result is False
    
    @patch('libs.commands.create_command.get_string_from_editor')
    def test_execute_with_editor_f1(self, mock_editor, mock_ui, mock_view, mock_jira_api):
        """Test using F1 to open editor for description"""
        mock_view.mode = ViewMode.BACKLOG
        mock_ui.prompt_get_string.side_effect = ["Summary", "KEY_F1"]
        mock_ui.prompt_with_choice_list.return_value = [0, "Story"]
        mock_editor.return_value = "Editor Description"
        mock_jira_api.get_possible_types.return_value = ["Story"]
        
        mock_issue = Mock()
        mock_issue.key = "TEST-999"
        mock_jira_api.create_backlog_issue.return_value = mock_issue
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api, stdscr=Mock())
        
        mock_editor.assert_called_once()
        mock_view.rebuild.assert_called()
        mock_jira_api.create_backlog_issue.assert_called_once_with("Summary", "Editor Description", "Story")
        assert result is False
    
    def test_execute_with_f2_use_summary(self, mock_ui, mock_view, mock_jira_api):
        """Test using F2 to use summary as description"""
        mock_view.mode = ViewMode.BACKLOG
        mock_ui.prompt_get_string.side_effect = ["Test Summary", "KEY_F2"]
        mock_ui.prompt_with_choice_list.return_value = [0, "Story"]
        mock_jira_api.get_possible_types.return_value = ["Story"]
        
        mock_issue = Mock()
        mock_issue.key = "TEST-888"
        mock_jira_api.create_backlog_issue.return_value = mock_issue
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_view.rebuild.assert_called()
        mock_jira_api.create_backlog_issue.assert_called_once_with("Test Summary", "Test Summary", "Story")
        assert result is False
    
    def test_execute_handles_exceptions(self, mock_ui, mock_view, mock_jira_api):
        """Test that exceptions are handled properly"""
        mock_ui.prompt_get_string.side_effect = Exception("Test error")
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_ui.error.assert_called_once_with("Create issue", mock_ui.prompt_get_string.side_effect)
        assert result is False
    
    def test_execute_jira_api_exception(self, mock_ui, mock_view, mock_jira_api):
        """Test handling of Jira API exceptions"""
        mock_view.mode = ViewMode.BACKLOG
        mock_ui.prompt_get_string.side_effect = ["Summary", "Description"]
        mock_ui.prompt_with_choice_list.return_value = [0, "Story"]
        mock_jira_api.get_possible_types.return_value = ["Story"]
        mock_jira_api.create_backlog_issue.side_effect = Exception("Jira API error")
        
        command = CreateCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_ui.error.assert_called_once()
        assert result is False