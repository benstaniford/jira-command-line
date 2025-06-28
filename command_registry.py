import os
import importlib
from commands.base_command import BaseCommand

class CommandRegistry:
    def __init__(self):
        self.commands = {}
        self.load_commands()
    
    def load_commands(self):
        """Dynamically load all command classes from the commands directory"""
        commands_dir = os.path.join(os.path.dirname(__file__), 'commands')
        
        for filename in os.listdir(commands_dir):
            if filename.endswith('_command.py') and filename != 'base_command.py':
                module_name = filename[:-3]  # Remove .py extension
                try:
                    module = importlib.import_module(f'commands.{module_name}')
                    
                    # Find the command class in the module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BaseCommand) and 
                            attr != BaseCommand):
                            command_instance = attr()
                            self.commands[command_instance.shortcut] = command_instance
                            break
                except Exception as e:
                    print(f"Failed to load command from {filename}: {e}")
    
    def get_command(self, shortcut):
        """Get a command by its shortcut"""
        return self.commands.get(shortcut)
    
    def get_all_shortcuts(self):
        """Get all available shortcuts"""
        return tuple(self.commands.keys())
    
    def get_single_char_shortcuts(self):
        """Get only single-character shortcuts for UI key handling"""
        return tuple(shortcut for shortcut in self.commands.keys() if len(shortcut) == 1)
    
    def get_help_text(self):
        """Get formatted help text for all commands"""
        help_lines = []
        current_line = ""
        
        for shortcut in sorted(self.commands.keys()):
            command = self.commands[shortcut]
            command_text = f"{shortcut}:{command.description}"
            
            # Check if adding this command would exceed 160 characters
            potential_line = current_line + (", " if current_line else "") + command_text
            
            if len(potential_line) > 160 and current_line:
                # Start a new line
                help_lines.append(current_line)
                current_line = command_text
            else:
                # Add to current line
                current_line = potential_line
        
        # Add the last line if it has content
        if current_line:
            help_lines.append(current_line)
            
        return '\n'.join(help_lines)
