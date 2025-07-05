from abc import ABC, abstractmethod
from typing import Any, Optional

class BaseCommand(ABC):
    """Base class for all jira commands"""
    
    @property
    @abstractmethod
    def shortcut(self) -> str:
        """The keyboard shortcut for this command"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this command does"""
        pass
    
    @abstractmethod
    def execute(
        self,
        ui: Any,
        view: Any,
        jira: Any,
        mygit: Optional[Any] = None,
        mygithub: Optional[Any] = None,
        config: Optional[Any] = None,
        **kwargs: Any
    ) -> Any:
        """Execute the command"""
        pass
    
    def get_help_text(self) -> str:
        """Get help text for this command"""
        return f"{self.shortcut}: {self.description}"
