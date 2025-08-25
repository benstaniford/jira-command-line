import pytest
from unittest.mock import Mock, patch
from libs.commands.move_command import MoveCommand
from libs.ViewMode import ViewMode


class TestMoveCommand:
    def test_shortcut_property(self):
        """Test that MoveCommand has correct shortcut"""
        command = MoveCommand()
        assert command.shortcut == "m"
    
    def test_description_property(self):
        """Test that MoveCommand has correct description"""
        command = MoveCommand()
        assert command.description == "move"
    
    def test_execute_move_to_top(self, mock_ui, mock_view, mock_jira_api):
        """Test moving an issue to the top"""
        mock_view.mode = ViewMode.SPRINT
        
        # Mock user inputs
        mock_ui.prompt_get_string.return_value = "1"  # Select issue 1
        mock_ui.prompt_with_choice_dictionary.return_value = "To top"
        
        # Mock issues
        mock_issue = Mock()
        mock_issue.key = "TEST-123"
        mock_top_issue = Mock()
        mock_top_issue.key = "TEST-TOP"
        
        mock_ui.get_row.side_effect = [
            [0, mock_issue],    # First call for selected issue
            [0, mock_top_issue] # Second call for top issue
        ]
        
        command = MoveCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        # Verify the ranking operation
        mock_jira_api.set_rank_above.assert_called_once_with(mock_issue, mock_top_issue)
        mock_ui.prompt.assert_called_with("Moved TEST-123 to top...")
        mock_view.refresh.assert_called_once()
        assert result is None
    
    def test_execute_move_to_bottom(self, mock_ui, mock_view, mock_jira_api):
        """Test moving an issue to the bottom"""
        mock_view.mode = ViewMode.BACKLOG
        
        # Mock user inputs
        mock_ui.prompt_get_string.return_value = "2"  # Select issue 2
        mock_ui.prompt_with_choice_dictionary.return_value = "To bottom"
        
        # Mock issues
        mock_issue = Mock()
        mock_issue.key = "TEST-456"
        mock_bottom_issue = Mock()
        mock_bottom_issue.key = "TEST-BOTTOM"
        
        mock_ui.get_row.side_effect = [
            [1, mock_issue],       # First call for selected issue
            [-1, mock_bottom_issue] # Second call for bottom issue
        ]
        
        command = MoveCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        # Verify the ranking operation
        mock_jira_api.set_rank_below.assert_called_once_with(mock_issue, mock_bottom_issue)
        mock_ui.prompt.assert_called_with("Moved TEST-456 to bottom...")
        mock_view.refresh.assert_called_once()
    
    def test_execute_move_below_issue(self, mock_ui, mock_view, mock_jira_api):
        """Test moving an issue below another specific issue"""
        mock_view.mode = ViewMode.SPRINT
        
        # Mock user inputs - first selects issue to move, then selects "Below issue", then target issue
        mock_ui.prompt_get_string.side_effect = ["1", "3"]  # Move issue 1 below issue 3
        mock_ui.prompt_with_choice_dictionary.return_value = "Below issue"
        
        # Mock issues
        mock_issue = Mock()
        mock_issue.key = "TEST-MOVE"
        mock_target_issue = Mock()
        mock_target_issue.key = "TEST-TARGET"
        
        mock_ui.get_row.side_effect = [
            [0, mock_issue],      # First call for issue to move
            [2, mock_target_issue] # Second call for target issue
        ]
        
        command = MoveCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        # Verify the ranking operation
        mock_jira_api.set_rank_below.assert_called_once_with(mock_issue, mock_target_issue)
        mock_ui.prompt.assert_called_with("Moved TEST-MOVE below TEST-TARGET...")
        mock_view.refresh.assert_called_once()
    
    def test_execute_move_to_backlog_from_sprint(self, mock_ui, mock_view, mock_jira_api):
        """Test moving an issue from sprint to backlog"""
        mock_view.mode = ViewMode.SPRINT
        
        # Mock user inputs
        mock_ui.prompt_get_string.return_value = "1"
        mock_ui.prompt_with_choice_dictionary.return_value = "To backlog"
        
        # Mock issue
        mock_issue = Mock()
        mock_issue.key = "TEST-789"
        mock_ui.get_row.return_value = [0, mock_issue]
        
        command = MoveCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        # Verify the move operation
        mock_jira_api.move_to_backlog.assert_called_once_with(mock_issue)
        mock_ui.prompt.assert_called_with("Moved TEST-789 to backlog...")
        mock_view.refresh.assert_called_once()
    
    def test_execute_move_to_sprint_from_backlog(self, mock_ui, mock_view, mock_jira_api):
        """Test moving an issue from backlog to sprint"""
        mock_view.mode = ViewMode.BACKLOG
        
        # Mock user inputs
        mock_ui.prompt_get_string.return_value = "2"
        mock_ui.prompt_with_choice_dictionary.return_value = "To sprint"
        
        # Mock issue
        mock_issue = Mock()
        mock_issue.key = "TEST-999"
        mock_ui.get_row.return_value = [1, mock_issue]
        
        command = MoveCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        # Verify the move operation
        mock_jira_api.move_to_sprint.assert_called_once_with(mock_issue)
        mock_ui.prompt.assert_called_with("Moved TEST-999 to sprint...")
        mock_view.refresh.assert_called_once()
    
    def test_execute_choice_dictionary_options_in_sprint_mode(self, mock_ui, mock_view, mock_jira_api):
        """Test that sprint mode shows backlog option"""
        mock_view.mode = ViewMode.SPRINT
        mock_ui.prompt_get_string.return_value = "1"
        mock_ui.prompt_with_choice_dictionary.return_value = "To backlog"
        
        mock_issue = Mock()
        mock_issue.key = "TEST-SPRINT"
        mock_ui.get_row.return_value = [0, mock_issue]
        
        command = MoveCommand()
        command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        # Verify that the choice dictionary was called with sprint-specific options
        call_args = mock_ui.prompt_with_choice_dictionary.call_args
        assert call_args[0][0] == "Move where?"
        options = call_args[0][1]
        assert 'l' in options  # Should have 'l': 'To backlog'
        assert options['l'] == 'To backlog'
        assert 't' in options  # Should have standard options
        assert 'b' in options
        assert 'i' in options
    
    def test_execute_choice_dictionary_options_in_backlog_mode(self, mock_ui, mock_view, mock_jira_api):
        """Test that backlog mode shows sprint option"""
        mock_view.mode = ViewMode.BACKLOG
        mock_ui.prompt_get_string.return_value = "1"
        mock_ui.prompt_with_choice_dictionary.return_value = "To sprint"
        
        mock_issue = Mock()
        mock_issue.key = "TEST-BACKLOG"
        mock_ui.get_row.return_value = [0, mock_issue]
        
        command = MoveCommand()
        command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        # Verify that the choice dictionary was called with backlog-specific options
        call_args = mock_ui.prompt_with_choice_dictionary.call_args
        options = call_args[0][1]
        assert 's' in options  # Should have 's': 'To sprint'
        assert options['s'] == 'To sprint'
        assert 't' in options  # Should have standard options
        assert 'b' in options
        assert 'i' in options
    
    def test_execute_non_numeric_selection_ignored(self, mock_ui, mock_view, mock_jira_api):
        """Test that non-numeric selections are ignored"""
        mock_ui.prompt_get_string.return_value = "abc"  # Non-numeric input
        
        command = MoveCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        # Should not call any Jira methods
        mock_jira_api.set_rank_above.assert_not_called()
        mock_jira_api.set_rank_below.assert_not_called()
        mock_jira_api.move_to_backlog.assert_not_called()
        mock_jira_api.move_to_sprint.assert_not_called()
        mock_view.refresh.assert_not_called()
    
    def test_execute_handles_exceptions(self, mock_ui, mock_view, mock_jira_api):
        """Test that exceptions are handled properly"""
        mock_ui.prompt_get_string.side_effect = Exception("Test error")
        
        command = MoveCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_ui.error.assert_called_once_with("Move issue", mock_ui.prompt_get_string.side_effect)
        assert result is None
    
    def test_execute_handles_jira_api_exceptions(self, mock_ui, mock_view, mock_jira_api):
        """Test handling of Jira API exceptions"""
        mock_view.mode = ViewMode.SPRINT
        mock_ui.prompt_get_string.return_value = "1"
        mock_ui.prompt_with_choice_dictionary.return_value = "To top"
        
        mock_issue = Mock()
        mock_issue.key = "TEST-ERROR"
        mock_top_issue = Mock()
        mock_top_issue.key = "TEST-TOP"
        
        mock_ui.get_row.side_effect = [
            [0, mock_issue],
            [0, mock_top_issue]
        ]
        
        # Mock Jira API to throw exception
        mock_jira_api.set_rank_above.side_effect = Exception("Jira API error")
        
        command = MoveCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        mock_ui.error.assert_called_once()
        assert result is None
    
    def test_execute_below_issue_non_numeric_target_ignored(self, mock_ui, mock_view, mock_jira_api):
        """Test that non-numeric target for 'below issue' is ignored"""
        mock_view.mode = ViewMode.SPRINT
        
        mock_ui.prompt_get_string.side_effect = ["1", "xyz"]  # Valid issue, invalid target
        mock_ui.prompt_with_choice_dictionary.return_value = "Below issue"
        
        mock_issue = Mock()
        mock_issue.key = "TEST-VALID"
        mock_ui.get_row.return_value = [0, mock_issue]
        
        command = MoveCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)
        
        # Should not call ranking methods
        mock_jira_api.set_rank_below.assert_not_called()
        mock_view.refresh.assert_not_called()