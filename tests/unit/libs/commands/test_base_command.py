import pytest
from abc import ABC
from libs.commands.base_command import BaseCommand


class ConcreteCommand(BaseCommand):
    """Concrete implementation of BaseCommand for testing"""
    
    @property
    def shortcut(self):
        return "t"
    
    @property
    def description(self):
        return "test command"
    
    def execute(self, ui=None, view=None, jira=None, **kwargs):
        return "executed"


class TestBaseCommand:
    def test_base_command_is_abstract(self):
        """Test that BaseCommand is an abstract class"""
        assert issubclass(BaseCommand, ABC)
        
        # Should not be able to instantiate BaseCommand directly
        with pytest.raises(TypeError):
            BaseCommand()
    
    def test_concrete_implementation_can_be_instantiated(self):
        """Test that concrete implementations can be instantiated"""
        command = ConcreteCommand()
        assert isinstance(command, BaseCommand)
    
    def test_shortcut_property_is_abstract(self):
        """Test that shortcut property must be implemented"""
        class IncompleteCommand(BaseCommand):
            @property
            def description(self):
                return "incomplete"
            
            def execute(self, **kwargs):
                pass
        
        with pytest.raises(TypeError):
            IncompleteCommand()
    
    def test_description_property_is_abstract(self):
        """Test that description property must be implemented"""
        class IncompleteCommand(BaseCommand):
            @property
            def shortcut(self):
                return "i"
            
            def execute(self, **kwargs):
                pass
        
        with pytest.raises(TypeError):
            IncompleteCommand()
    
    def test_execute_method_is_abstract(self):
        """Test that execute method must be implemented"""
        class IncompleteCommand(BaseCommand):
            @property
            def shortcut(self):
                return "i"
            
            @property
            def description(self):
                return "incomplete"
        
        with pytest.raises(TypeError):
            IncompleteCommand()
    
    def test_concrete_command_properties(self):
        """Test that concrete command properties work correctly"""
        command = ConcreteCommand()
        
        assert command.shortcut == "t"
        assert command.description == "test command"
    
    def test_concrete_command_execute(self):
        """Test that concrete command execute method works"""
        command = ConcreteCommand()
        
        result = command.execute()
        assert result == "executed"
        
        # Test with arguments
        result = command.execute(ui="mock_ui", view="mock_view")
        assert result == "executed"
    
    def test_get_help_text_default_implementation(self):
        """Test the default get_help_text implementation"""
        command = ConcreteCommand()
        
        help_text = command.get_help_text()
        assert help_text == "t: test command"
    
    def test_execute_signature_flexibility(self):
        """Test that execute method accepts flexible arguments"""
        class FlexibleCommand(BaseCommand):
            @property
            def shortcut(self):
                return "f"
            
            @property
            def description(self):
                return "flexible"
            
            def execute(self, ui=None, view=None, jira=None, mygit=None, 
                       mygithub=None, config=None, **kwargs):
                return {
                    'ui': ui,
                    'view': view, 
                    'jira': jira,
                    'mygit': mygit,
                    'mygithub': mygithub,
                    'config': config,
                    'extra': kwargs
                }
        
        command = FlexibleCommand()
        
        # Test with all expected parameters
        result = command.execute(
            ui="mock_ui",
            view="mock_view", 
            jira="mock_jira",
            mygit="mock_git",
            mygithub="mock_github",
            config="mock_config",
            extra_param="extra_value"
        )
        
        assert result['ui'] == "mock_ui"
        assert result['view'] == "mock_view"
        assert result['jira'] == "mock_jira"
        assert result['mygit'] == "mock_git"
        assert result['mygithub'] == "mock_github"
        assert result['config'] == "mock_config"
        assert result['extra']['extra_param'] == "extra_value"
    
    def test_multiple_concrete_implementations(self):
        """Test that multiple concrete implementations can coexist"""
        class Command1(BaseCommand):
            @property
            def shortcut(self):
                return "1"
            
            @property  
            def description(self):
                return "first command"
            
            def execute(self, **kwargs):
                return "first"
        
        class Command2(BaseCommand):
            @property
            def shortcut(self):
                return "2"
            
            @property
            def description(self):
                return "second command"
            
            def execute(self, **kwargs):
                return "second"
        
        cmd1 = Command1()
        cmd2 = Command2()
        
        assert cmd1.shortcut == "1"
        assert cmd2.shortcut == "2"
        assert cmd1.execute() == "first"
        assert cmd2.execute() == "second"