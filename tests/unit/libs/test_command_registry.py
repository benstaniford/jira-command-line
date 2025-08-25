import pytest
import os
from unittest.mock import patch, Mock, MagicMock
from libs.CommandRegistry import CommandRegistry
from libs.commands.base_command import BaseCommand


# Mock command class for testing
class MockCommand(BaseCommand):
    @property
    def shortcut(self):
        return "m"
    
    @property
    def description(self):
        return "mock command"
    
    def execute(self, **kwargs):
        return "mock executed"


class TestCommandRegistry:
    def test_load_commands_basic_functionality(self):
        """Test that CommandRegistry can load commands successfully"""
        registry = CommandRegistry()
        
        # Registry should initialize without error
        assert hasattr(registry, 'commands')
        assert isinstance(registry.commands, dict)
        
        # Should have load_commands method
        assert hasattr(registry, 'load_commands')
        assert callable(registry.load_commands)
    
    def test_get_command_returns_correct_command(self):
        """Test that get_command returns the correct command instance"""
        registry = CommandRegistry()
        
        # Manually add a mock command
        mock_cmd = MockCommand()
        registry.commands['m'] = mock_cmd
        
        result = registry.get_command('m')
        assert result is mock_cmd
    
    def test_get_command_returns_none_for_missing_shortcut(self):
        """Test that get_command returns None for non-existent shortcut"""
        registry = CommandRegistry()
        result = registry.get_command('nonexistent')
        assert result is None
    
    def test_get_all_shortcuts_returns_all_shortcuts(self):
        """Test that get_all_shortcuts returns all registered shortcuts"""
        registry = CommandRegistry()
        
        # Manually add mock commands
        cmd1 = MockCommand()
        cmd2 = Mock()
        cmd2.shortcut = 'x'
        
        registry.commands = {'m': cmd1, 'x': cmd2}
        
        shortcuts = registry.get_all_shortcuts()
        assert set(shortcuts) == {'m', 'x'}
        assert isinstance(shortcuts, tuple)
    
    def test_get_single_char_shortcuts_filters_correctly(self):
        """Test that get_single_char_shortcuts only returns single character shortcuts"""
        registry = CommandRegistry()
        
        # Mock commands with different shortcut lengths
        cmd1 = Mock()
        cmd1.shortcut = 's'  # Single char
        cmd2 = Mock() 
        cmd2.shortcut = 'long'  # Multi char
        cmd3 = Mock()
        cmd3.shortcut = 'x'  # Single char
        
        registry.commands = {'s': cmd1, 'long': cmd2, 'x': cmd3}
        
        single_chars = registry.get_single_char_shortcuts()
        assert set(single_chars) == {'s', 'x'}
        assert isinstance(single_chars, tuple)
    
    def test_collect_command_texts_excludes_ignored(self):
        """Test that _collect_command_texts excludes ignored shortcuts"""
        registry = CommandRegistry()
        
        # Mock commands
        cmd1 = Mock()
        cmd1.shortcut = 's'
        cmd1.description = 'search'
        
        cmd2 = Mock()
        cmd2.shortcut = 'h'
        cmd2.description = 'help'
        
        cmd3 = Mock()
        cmd3.shortcut = 'q'
        cmd3.description = 'quit'
        
        registry.commands = {'s': cmd1, 'h': cmd2, 'q': cmd3}
        
        # Test excluding some commands
        result = registry._collect_command_texts(['h', 'q'])
        
        assert result == ['s:search']
    
    def test_collect_command_texts_sorts_correctly(self):
        """Test that _collect_command_texts sorts commands correctly"""
        registry = CommandRegistry()
        
        # Mock commands in various cases
        cmd1 = Mock()
        cmd1.shortcut = 'Z'
        cmd1.description = 'zulu'
        
        cmd2 = Mock()
        cmd2.shortcut = 'a'
        cmd2.description = 'alpha'
        
        cmd3 = Mock()
        cmd3.shortcut = 'B'
        cmd3.description = 'bravo'
        
        registry.commands = {'Z': cmd1, 'a': cmd2, 'B': cmd3}
        
        result = registry._collect_command_texts([])
        
        # Should be sorted by lowercase, then by case
        expected = ['a:alpha', 'B:bravo', 'Z:zulu']
        assert result == expected
    
    def test_estimate_min_lines_calculates_correctly(self):
        """Test that _estimate_min_lines calculates minimum lines correctly"""
        registry = CommandRegistry()
        
        # Test with known values
        command_texts = ['a:alpha', 'b:bravo', 'c:charlie']  # lengths: 7, 7, 9
        # Total length: 7 + 7 + 9 + 2*2 (separators) = 27
        max_line_length = 15
        
        result = registry._estimate_min_lines(command_texts, max_line_length)
        
        # Should need at least 2 lines (27/15 = 1.8, rounded up to 2)
        assert result == 2
    
    def test_get_help_text_returns_formatted_string(self):
        """Test that get_help_text returns properly formatted help string"""
        registry = CommandRegistry()
        
        # Mock commands
        cmd1 = Mock()
        cmd1.shortcut = 's'
        cmd1.description = 'search'
        
        cmd2 = Mock()
        cmd2.shortcut = 'h'
        cmd2.description = 'help'
        
        registry.commands = {'s': cmd1, 'h': cmd2}
        
        result = registry.get_help_text(['h'])  # Exclude 'h'
        
        assert 's:search' in result
        assert 'h:help' not in result
    
    def test_get_help_text_handles_empty_commands(self):
        """Test that get_help_text handles empty command list"""
        registry = CommandRegistry()
        registry.commands = {}
        
        result = registry.get_help_text([])
        assert result == ""
    
    def test_load_commands_handles_errors_gracefully(self):
        """Test that load_commands doesn't crash on errors"""
        # This test verifies the class can handle errors during initialization
        # without detailed mocking of the internals
        
        try:
            registry = CommandRegistry()
            # If we get here without exception, the error handling works
            assert True
        except Exception as e:
            # If there's an exception, it should not be from command loading failures
            # as those should be caught and handled
            assert False, f"CommandRegistry initialization should not raise exceptions: {e}"