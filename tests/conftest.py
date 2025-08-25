import pytest
import json
import os
from unittest.mock import Mock, MagicMock
from libs.MyJiraConfig import MyJiraConfig
from libs.MyJira import MyJira
from libs.MyGit import MyGit
from libs.MyGithub import MyGithub

@pytest.fixture
def mock_config():
    """Mock configuration dictionary for testing"""
    return {
        "version": 1.0,
        "jira": {
            "url": "https://test.atlassian.net",
            "password": "test-token",
            "username": "test@example.com",
            "fullname": "Test User",
            "default_team": "TestTeam",
            "teams": {
                "TestTeam": {
                    "team_id": 42,
                    "project_name": "TEST",
                    "product_name": "Test Product",
                    "short_names_to_ids": {
                        "Alice": "alice@example.com",
                        "Bob": "bob@example.com",
                        "Unassigned": ""
                    },
                    "kanban_board_id": 100,
                    "backlog_board_id": 101,
                    "escalation_board_id": 102
                }
            }
        },
        "github": {
            "token": "test-github-token",
            "org": "test-org"
        },
        "git": {
            "initials": "tu"
        }
    }

@pytest.fixture
def mock_jira_config(tmp_path):
    """Mock JiraConfig with temporary directory"""
    config = MyJiraConfig()
    config.config_dir = str(tmp_path / ".jira-config")
    config.config_file_path = str(tmp_path / ".jira-config" / "config.json")
    return config

@pytest.fixture
def mock_jira_issue():
    """Mock Jira issue object"""
    mock_issue = Mock()
    mock_issue.key = "TEST-123"
    mock_issue.fields = Mock()
    mock_issue.fields.summary = "Test Issue Summary"
    mock_issue.fields.description = "Test Issue Description"
    mock_issue.fields.status = Mock()
    mock_issue.fields.status.name = "To Do"
    mock_issue.fields.assignee = Mock()
    mock_issue.fields.assignee.displayName = "Test User"
    mock_issue.fields.priority = Mock()
    mock_issue.fields.priority.name = "Medium"
    mock_issue.raw = {
        'fields': {
            'summary': 'Test Issue Summary',
            'description': 'Test Issue Description',
            'status': {'name': 'To Do'},
            'assignee': {'displayName': 'Test User'},
            'priority': {'name': 'Medium'}
        }
    }
    return mock_issue

@pytest.fixture
def mock_jira_api():
    """Mock JIRA API client"""
    mock_jira = Mock()
    mock_jira.fields.return_value = [
        {'id': 'summary', 'name': 'Summary'},
        {'id': 'description', 'name': 'Description'},
        {'id': 'status', 'name': 'Status'},
        {'id': 'assignee', 'name': 'Assignee'},
        {'id': 'priority', 'name': 'Priority'}
    ]
    mock_jira.issue_types.return_value = [
        Mock(name='Story', id='1'),
        Mock(name='Bug', id='2'),
        Mock(name='Task', id='3')
    ]
    return mock_jira

@pytest.fixture
def mock_ui():
    """Mock UI object for command testing"""
    mock_ui = Mock()
    mock_ui.prompt_get_string.return_value = "test input"
    mock_ui.prompt_get_character.return_value = "y"
    mock_ui.prompt_with_choice_list.return_value = [0, "Story"]
    mock_ui.prompt.return_value = None
    mock_ui.error.return_value = None
    mock_ui.get_row.return_value = [Mock(), Mock()]
    return mock_ui

@pytest.fixture
def mock_view():
    """Mock view object for command testing"""
    mock_view = Mock()
    mock_view.mode = "BACKLOG"
    mock_view.parent_issue = Mock()
    mock_view.parent_issue.key = "TEST-456"
    mock_view.extra_columns = {}
    mock_view.refresh.return_value = None
    mock_view.rebuild.return_value = None
    mock_view.previous.return_value = None
    return mock_view

@pytest.fixture 
def sample_jira_response():
    """Sample Jira API response data"""
    return {
        "issues": [
            {
                "key": "TEST-123",
                "fields": {
                    "summary": "Sample Issue",
                    "description": "This is a test issue",
                    "status": {"name": "To Do"},
                    "assignee": {"displayName": "Test User"},
                    "priority": {"name": "High"}
                }
            }
        ]
    }

@pytest.fixture
def mock_git_repo(tmp_path):
    """Mock git repository for testing"""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    return str(repo_path)