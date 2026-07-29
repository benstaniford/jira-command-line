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

### Row Cursor and Implicit Selection
No cursor is shown until the user presses up or down, at which point a
reverse-video bar appears on the first row of the current page and the arrow keys
move it (paging the table when it runs off either end). While a row is selected it
is the implicit argument for every command that would otherwise prompt "Enter
issue number" - those commands call `ui.prompt_get_issue()`
(`libs/CursesTableView.py`) instead of pairing `prompt_get_string` with
`get_row`, and it returns the cursor row without prompting at all. Enter opens the
task view for the selected row and Escape clears the cursor; `prompt_get_string`
grew an `escape_returns` argument so escape can be told apart from an empty enter.

Two deliberate exceptions: `browse_command` still shows its prompt so the
sprintboard/backlog/kanban options stay reachable (enter falls back to the cursor
row), and the second prompt in `move_command` ("below which issue?") still asks,
since the cursor is the issue being moved. The cursor is a screen position rather
than a pinned issue - it is clamped when a filter shrinks the table and cleared by
`ui.clear()`, so any view refresh drops it.

### Drilling Into Issues
Enter on a row opens TASKVIEW, which lists the row's children via
`MyJira.get_child_issues()`. That query is just `parent = <key>`, which covers both
of Jira's parent relationships: a story's children are its sub-tasks, an epic's are
its stories and bugs. Epics are therefore drillable, and `backlog_issue_filter`
(`libs/MyJira.py`) lists them in the backlog and sprints views - the current sprint
view keeps the epic-free `issue_filter`.

Drill-downs nest. `JiraTableView` keeps a stack of `(mode, issues, parent_issue)`
frames, one per level, so epic -> story -> sub-tasks works and each Escape (or Enter
with no cursor) unwinds one level via `view.previous()`; `view.has_previous()` is
what the main loop in `jira` tests. An argument-less `refresh()` re-queries the
current level without pushing, and switching to any other view clears the stack.

Inside an epic, `c` (create) prompts for an issue type and parents the new issue to
the epic instead of creating a sub-task, since epics cannot have sub-tasks.

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

### Branch and Worktree Naming
Branch names are `<initials>/<issue-key>/<summary>`. Jira titles are often far too
long for that, so `libs/BranchNamer.py` shells out to the Claude CLI
(`claude -p --model haiku`) to reduce a title over `git.max_branch_summary_length`
characters (default 40) to a few distinctive words. Anything that goes wrong -
Claude not installed, a non-zero exit, a timeout, or a reply that doesn't look
like a branch fragment - falls back to the full title, i.e. the old behaviour.
Set `git.branch_name_model` to `""` to switch shortening off entirely.

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