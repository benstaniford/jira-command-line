# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Installation and Setup

This is a Python-based Jira command line client that requires Python 3.11 (Python 3.12 has compatibility issues with dependencies).

### Dependencies Installation
```bash
# Windows
pip install -r requirements.txt

# Unix/Linux/macOS
pip install -r requirements-unix.txt

# Manual installation
pip install jira gitpython PyGithub windows-curses ttkthemes sv-ttk  # Windows
pip install jira gitpython PyGithub ttkthemes sv-ttk                 # Unix
```

**Note:** The main difference is that Windows requires `windows-curses` package while Unix systems use the built-in curses library.

### Configuration
On first run, the tool generates a template configuration file at `~/.jira-config/config.json` that must be customized with:
- Jira PAT tokens from https://id.atlassian.com/manage-profile/security/api-tokens
- GitHub PAT tokens from https://github.com/settings/tokens (classic token with repo scope)
- Team configurations, board IDs, and user mappings

## Running the Application

The main entry point is the `jira` script in the root directory:
```bash
python jira                    # Default backlog mode
python jira -s                 # Sprint mode
python jira -l                 # Backlog mode
python jira -B <board_index>   # Specific board mode
python jira -z                 # Escalations mode
python jira -w                 # Windows-shared mode
```

## Architecture Overview

### Core Architecture
- **Main Entry**: `jira` script initializes the curses UI and handles command-line arguments
- **UI Layer**: `CursesTableView` provides the terminal-based table interface
- **Data Layer**: `JiraTableView` handles Jira data presentation and view modes
- **Command System**: Plugin-based command registry that dynamically loads commands from `libs/commands/`
- **Integration**: Separate modules for Jira (`MyJira`), Git (`MyGit`), and GitHub (`MyGithub`) APIs

### Key Components
- **CommandRegistry** (`libs/CommandRegistry.py`): Dynamically discovers and loads command classes
- **BaseCommand** (`libs/commands/base_command.py`): Abstract base class for all commands
- **ViewMode** (`libs/ViewMode.py`): Enum defining different view types (SPRINT, BACKLOG, TASKVIEW, etc.)
- **MyJiraConfig** (`libs/MyJiraConfig.py`): Configuration management with team-specific settings

### Command System
Commands are auto-discovered from `libs/commands/` directory. Each command:
- Inherits from `BaseCommand`
- Implements `shortcut`, `description`, and `execute()` methods
- Is registered automatically by filename pattern `*_command.py`
- Receives UI, view, Jira, Git, and GitHub objects for execution

The command help display at the bottom of the UI is optimized for readability by preferring 3 lines of help text instead of cramming all commands into the minimum number of lines possible. The UI reserves 5 lines total at the bottom for the command prompt area. Help text lines are indented with 2 spaces for visual separation from the command line and instruction line.

### View Modes
The application supports multiple view modes:
- **BACKLOG**: Team backlog issues
- **SPRINT**: Current sprint issues  
- **BOARD**: Specific board view
- **TASKVIEW**: Detailed task view
- **ESCALATIONS**: Escalated issues
- **WINDOWS_SHARED**: Windows-specific shared view

## Development Notes

### Adding New Commands
1. Create `new_feature_command.py` in `libs/commands/`
2. Inherit from `BaseCommand`
3. Implement required abstract methods
4. Command will be auto-registered on startup

### Configuration Structure
The config supports multiple teams with individual settings for:
- Team IDs and project names
- Board IDs (kanban, backlog, escalation)
- User name mappings for quick assignment
- Jira and GitHub authentication tokens

### Testing Framework
The project now includes a comprehensive test suite using pytest:

**Running Tests:**
```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=libs --cov-report=term-missing

# Run specific test file
python -m pytest tests/unit/libs/test_my_git.py -v
```

**Test Structure:**
- `tests/unit/libs/` - Unit tests for core components
- `tests/unit/libs/commands/` - Command-specific tests  
- `tests/conftest.py` - Shared fixtures and test utilities
- `requirements-test.txt` - Testing dependencies

**CI/CD Pipeline:**
- GitHub Actions workflow runs tests on every push to main and PR
- Tests run on Python 3.11 and 3.12
- Includes security scanning with Bandit and Safety
- Code quality checks with Black, isort, and mypy
- Coverage reporting to Codecov
- Dependabot for dependency updates