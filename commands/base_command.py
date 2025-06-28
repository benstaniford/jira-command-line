from abc import ABC, abstractmethod

class BaseCommand(ABC):
    """Base class for all jira commands"""
    
    @property
    @abstractmethod
    def shortcut(self):
        """The keyboard shortcut for this command"""
        pass
    
    @property
    @abstractmethod
    def description(self):
        """Description of what this command does"""
        pass
    
    @abstractmethod
    def execute(self, ui, view, jira, mygit=None, mygithub=None, config=None, **kwargs):
        """Execute the command"""
        pass
    
    def get_help_text(self):
        """Get help text for this command"""
        return f"{self.shortcut}: {self.description}"
