import pytest
from unittest.mock import Mock
from libs.commands.quit_command import QuitCommand


class TestQuitCommand:
    def test_shortcut_property(self):
        """Test that QuitCommand has correct shortcut"""
        command = QuitCommand()
        assert command.shortcut == "q"
    
    def test_description_property(self):
        """Test that QuitCommand has correct description"""
        command = QuitCommand()
        assert command.description == "quit"
    
    def test_execute_returns_true(self):
        """Test that execute returns True to signal quit"""
        command = QuitCommand()
        mock_ui = Mock()
        result = command.execute(ui=mock_ui, view=Mock(), jira=Mock())
        assert result is True
    
    def test_execute_with_arguments_returns_true(self):
        """Test that execute returns True regardless of arguments"""
        command = QuitCommand()
        
        mock_ui = Mock()
        mock_view = Mock()
        mock_jira = Mock()
        
        result = command.execute(
            ui=mock_ui, 
            view=mock_view, 
            jira=mock_jira,
            extra_param="test"
        )
        
        assert result is True
    
    def test_execute_calls_ui_close(self):
        """Test that execute calls ui.close()"""
        command = QuitCommand()
        
        mock_ui = Mock()
        mock_view = Mock()
        
        command.execute(ui=mock_ui, view=mock_view, jira=Mock())
        
        # Verify ui.close() was called
        mock_ui.close.assert_called_once()
        
        # Verify other UI methods were not called
        mock_ui.prompt.assert_not_called()
        mock_ui.error.assert_not_called()
        mock_ui.prompt_get_string.assert_not_called()
        
        # Verify no view methods were called
        mock_view.refresh.assert_not_called()
        mock_view.rebuild.assert_not_called()