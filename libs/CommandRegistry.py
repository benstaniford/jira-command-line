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
    
    def _collect_command_texts(self, ignored) -> list[str]:
        """Collect and format command texts, excluding ignored shortcuts."""
        return [
            f"{shortcut}:{self.commands[shortcut].description}"
            for shortcut in sorted(self.commands.keys(), key=lambda x: (x.lower(), x.isupper()))
            if shortcut not in ignored
        ]

    def _estimate_min_lines(self, command_texts: list[str], max_line_length: int) -> int:
        """Estimate the minimum number of lines needed to fit all commands."""
        total_length = sum(len(cmd) for cmd in command_texts) + (len(command_texts) - 1) * 2  # 2 for ', '
        return max(1, (total_length + max_line_length - 1) // max_line_length)

    def _distribute_commands(self, command_texts: list[str], min_lines: int, max_line_length: int) -> list[list[str]]:
        """Distribute commands sequentially across lines, preserving order while balancing lengths."""
        if not command_texts:
            return []
        
        # Simple approach: distribute commands sequentially while trying to balance
        commands_per_line = len(command_texts) // min_lines
        extra_commands = len(command_texts) % min_lines
        
        lines = []
        start_idx = 0
        
        for line_num in range(min_lines):
            # Calculate how many commands this line should get
            line_command_count = commands_per_line + (1 if line_num < extra_commands else 0)
            end_idx = start_idx + line_command_count
            
            # Get commands for this line
            line_commands = command_texts[start_idx:end_idx]
            
            # Check if line would be too long
            line_text = ", ".join(line_commands)
            if len(line_text) > max_line_length and len(line_commands) > 1:
                # Try to move some commands to next lines if possible
                while len(line_commands) > 1 and len(", ".join(line_commands)) > max_line_length:
                    line_commands.pop()
                    end_idx -= 1
            
            lines.append(line_commands)
            start_idx = end_idx
        
        # If there are remaining commands due to length constraints, add them to additional lines
        while start_idx < len(command_texts):
            remaining = command_texts[start_idx:]
            line_commands = []
            current_length = 0
            
            for cmd in remaining:
                test_length = current_length + (2 if line_commands else 0) + len(cmd)
                if test_length <= max_line_length:
                    line_commands.append(cmd)
                    current_length = test_length
                    start_idx += 1
                else:
                    break
            
            if line_commands:
                lines.append(line_commands)
            else:
                # If even a single command is too long, add it anyway
                lines.append([remaining[0]])
                start_idx += 1
        
        return [line for line in lines if line]

    def get_help_text(self, ignored) -> str:
        """Get formatted help text for all commands, balancing line lengths"""
        max_line_length = 160
        command_texts = self._collect_command_texts(ignored)
        if not command_texts:
            return ""
        min_lines = self._estimate_min_lines(command_texts, max_line_length)
        # Prefer 3 lines for better readability while fitting in UI constraints
        # Total prompt needs: 1 (command line) + 3 (help text) + 1 (instruction) = 5 lines
        target_lines = max(3, min_lines)
        lines = self._distribute_commands(command_texts, target_lines, max_line_length)
        help_lines = [", ".join(line) for line in lines]
        return '\n'.join(help_lines)
    
    def get_help_text_with_colors(self, ignored) -> list[list[tuple[str, bool]]]:
        """Get formatted help text with color information for command characters.
        
        Returns:
            list[list[tuple[str, bool]]]: List of lines, each containing list of (text, is_red) tuples
        """
        max_line_length = 160
        command_texts = self._collect_command_texts(ignored)
        if not command_texts:
            return []
        min_lines = self._estimate_min_lines(command_texts, max_line_length)
        target_lines = max(3, min_lines)
        lines = self._distribute_commands(command_texts, target_lines, max_line_length)
        
        colored_lines = []
        for line in lines:
            colored_line = []
            for i, command_text in enumerate(line):
                if i > 0:
                    colored_line.append((", ", False))  # Add comma separator
                
                # Split command_text into parts: "shortcut:description"
                if ":" in command_text:
                    shortcut, description = command_text.split(":", 1)
                    colored_line.append((shortcut, True))   # Red for command shortcut
                    colored_line.append((":", False))       # Normal colon
                    colored_line.append((description, False))  # Normal description
                else:
                    # Fallback for commands without colon
                    colored_line.append((command_text, False))
            
            colored_lines.append(colored_line)
        
        return colored_lines
