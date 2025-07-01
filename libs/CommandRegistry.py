import os
import importlib
from typing import Dict, Tuple, Optional, Any
from libs.commands.base_command import BaseCommand

class CommandRegistry:
    def __init__(self) -> None:
        self.commands: Dict[str, BaseCommand] = {}
        self.load_commands()
    
    def load_commands(self) -> None:
        """Dynamically load all command classes from the commands directory"""
        commands_dir = os.path.join(os.path.dirname(__file__), 'commands')
        
        for filename in os.listdir(commands_dir):
            if filename.endswith('_command.py') and filename != 'base_command.py':
                module_name = filename[:-3]  # Remove .py extension
                try:
                    module = importlib.import_module(f'libs.commands.{module_name}')
                    
                    # Find the command class in the module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BaseCommand) and 
                            attr != BaseCommand):
                            command_instance: BaseCommand = attr()
                            self.commands[command_instance.shortcut] = command_instance
                            break
                except Exception as e:
                    print(f"Failed to load command from {filename}: {e}")
    
    def get_command(self, shortcut: str) -> Optional[BaseCommand]:
        """Get a command by its shortcut"""
        return self.commands.get(shortcut)
    
    def get_all_shortcuts(self) -> Tuple[str, ...]:
        """Get all available shortcuts"""
        return tuple(self.commands.keys())
    
    def get_single_char_shortcuts(self) -> Tuple[str, ...]:
        """Get only single-character shortcuts for UI key handling"""
        return tuple(shortcut for shortcut in self.commands.keys() if len(shortcut) == 1)
    
    def get_help_text(self, ignored) -> str:
        """Get formatted help text for all commands, balancing line lengths"""
        # Collect all command texts
        command_texts = []
        for shortcut in sorted(self.commands.keys(), key=lambda x: (x.lower(), x)):
            if shortcut in ignored:
                continue
            command = self.commands[shortcut]
            command_texts.append(f"{shortcut}:{command.description}")
        
        if not command_texts:
            return ""
        
        max_line_length = 160
        
        # Calculate total length needed including separators
        total_length = sum(len(cmd) for cmd in command_texts) + (len(command_texts) - 1) * 2  # 2 for ", "
        
        # Estimate minimum number of lines needed
        min_lines = max(1, (total_length + max_line_length - 1) // max_line_length)
        
        # Try to distribute commands across lines as evenly as possible
        lines = [[] for _ in range(min_lines)]
        line_lengths = [0] * min_lines
        
        for command_text in command_texts:
            # Find the line with minimum current length
            min_line_idx = line_lengths.index(min(line_lengths))
            
            # Calculate length if we add this command
            separator_length = 2 if lines[min_line_idx] else 0  # ", " or nothing
            new_length = line_lengths[min_line_idx] + separator_length + len(command_text)
            
            # If adding to shortest line would exceed max length, try next shortest
            if new_length > max_line_length and lines[min_line_idx]:
                # Find next best line that can fit this command
                best_line_idx = min_line_idx
                for i, length in enumerate(line_lengths):
                    sep_len = 2 if lines[i] else 0
                    if length + sep_len + len(command_text) <= max_line_length:
                        if length < line_lengths[best_line_idx] or line_lengths[best_line_idx] + (2 if lines[best_line_idx] else 0) + len(command_text) > max_line_length:
                            best_line_idx = i
                
                # If no line can fit it, create a new line
                if line_lengths[best_line_idx] + (2 if lines[best_line_idx] else 0) + len(command_text) > max_line_length:
                    lines.append([])
                    line_lengths.append(0)
                    best_line_idx = len(lines) - 1
                
                min_line_idx = best_line_idx
            
            # Add command to chosen line
            separator_length = 2 if lines[min_line_idx] else 0
            lines[min_line_idx].append(command_text)
            line_lengths[min_line_idx] += separator_length + len(command_text)
        
        # Convert to strings
        help_lines = [", ".join(line) for line in lines if line]
        
        return '\n'.join(help_lines)
