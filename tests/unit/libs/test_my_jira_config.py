import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock
from libs.MyJiraConfig import MyJiraConfig


class TestMyJiraConfig:
    def test_init_sets_correct_paths(self):
        """Test that MyJiraConfig initializes with correct file paths"""
        config = MyJiraConfig()
        assert config.config_dir.endswith('.jira-config')
        assert config.config_file_path.endswith('.jira-config/config.json')
    
    def test_config_file_path_construction(self):
        """Test that config file path is constructed correctly"""
        config = MyJiraConfig()
        home_dir = os.path.expanduser("~")
        expected_dir = os.path.join(home_dir, ".jira-config")
        expected_path = os.path.join(expected_dir, "config.json")
        
        assert config.config_dir == expected_dir
        assert config.config_file_path == expected_path
    
    @patch('os.path.exists')
    def test_exists_returns_true_when_file_exists(self, mock_exists):
        """Test exists() returns True when config file exists"""
        mock_exists.return_value = True
        config = MyJiraConfig()
        assert config.exists() is True
        mock_exists.assert_called_once_with(config.config_file_path)
    
    @patch('os.path.exists')
    def test_exists_returns_false_when_file_missing(self, mock_exists):
        """Test exists() returns False when config file doesn't exist"""
        mock_exists.return_value = False
        config = MyJiraConfig()
        assert config.exists() is False
        mock_exists.assert_called_once_with(config.config_file_path)
    
    @patch('builtins.open', mock_open())
    @patch('os.makedirs')
    @patch('json.dump')
    def test_generate_template_creates_directory(self, mock_json_dump, mock_makedirs):
        """Test that generate_template creates the config directory"""
        config = MyJiraConfig()
        config.generate_template()
        mock_makedirs.assert_called_once_with(config.config_dir, exist_ok=True)
    
    @patch('builtins.open', mock_open())
    @patch('os.makedirs')
    @patch('json.dump')
    def test_generate_template_writes_json(self, mock_json_dump, mock_makedirs):
        """Test that generate_template writes JSON configuration"""
        config = MyJiraConfig()
        config.generate_template()
        
        # Verify json.dump was called
        mock_json_dump.assert_called_once()
        
        # Check that the data passed to json.dump has expected structure
        call_args = mock_json_dump.call_args
        config_data = call_args[0][0]  # First argument to json.dump
        
        assert 'version' in config_data
        assert 'jira' in config_data
        assert 'url' in config_data['jira']
        assert 'teams' in config_data['jira']
    
    @patch('builtins.open', mock_open(read_data='{"version": 1.0, "jira": {"default_team": "TestTeam"}}'))
    @patch('json.load')
    def test_load_reads_config_file(self, mock_json_load):
        """Test that load() reads and parses the config file"""
        valid_config = {
            "version": 1.0, 
            "jira": {
                "default_team": "TestTeam",
                "url": "https://test.atlassian.net",
                "username": "test@example.com",
                "password": "token",
                "fullname": "Test User",
                "teams": {"TestTeam": {}}
            },
            "xray": {
                "client_id": "test_id",
                "client_secret": "test_secret"
            }
        }
        mock_json_load.return_value = valid_config
        
        config = MyJiraConfig()
        result = config.load()
        
        assert result == valid_config
        mock_json_load.assert_called_once()
    
    def test_get_location_returns_config_path(self):
        """Test that get_location() returns the config file path"""
        config = MyJiraConfig()
        assert config.get_location() == config.config_file_path
    
    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_load_raises_exception_when_file_missing(self, mock_open):
        """Test that load() raises exception when config file is missing"""
        config = MyJiraConfig()
        with pytest.raises(FileNotFoundError):
            config.load()
    
    @patch('builtins.open', mock_open(read_data='invalid json'))
    @patch('json.load', side_effect=json.JSONDecodeError("msg", "doc", 0))
    def test_load_raises_exception_on_invalid_json(self, mock_json_load):
        """Test that load() raises exception on invalid JSON"""
        config = MyJiraConfig()
        with pytest.raises(json.JSONDecodeError):
            config.load()

    @patch('builtins.open', mock_open())
    @patch('os.makedirs')
    @patch('json.dump')
    def test_generate_template_contains_boardless_team_example(self, mock_json_dump, mock_makedirs):
        """Test that the template documents the minimal team shape (no team/boards/product)"""
        config = MyJiraConfig()
        config.generate_template()

        config_data = mock_json_dump.call_args[0][0]
        teams = config_data['jira']['teams']

        assert teams['Sparklemuffin']['github_repos'] == ["epm-windows"]
        pathfinder = teams['Pathfinder']
        assert pathfinder['project_name'] == "AIDR"
        assert pathfinder['github_repos'] == ["pathfinder-agent"]
        for optional_key in ('team_id', 'product_name', 'kanban_board_id', 'backlog_board_id', 'escalation_board_id'):
            assert optional_key not in pathfinder


class TestUpgradeV11:
    def _v10_config(self):
        return {
            "version": 1.0,
            "jira": {
                "url": "https://test.atlassian.net",
                "password": "token",
                "username": "test@example.com",
                "fullname": "Test User",
                "default_team": "TestTeam",
                "teams": {
                    "TestTeam": {"team_id": 42, "project_name": "TEST"},
                    "OtherTeam": {"team_id": 43, "project_name": "TEST"}
                }
            },
            "github": {"token": "t", "repo_owner": "test-org", "repo_name": "test-repo"},
            "xray": {"client_id": "", "client_secret": ""}
        }

    def _upgrade(self, mock_jira_config, config_data):
        os.makedirs(mock_jira_config.config_dir, exist_ok=True)
        with open(mock_jira_config.config_file_path, "w") as config_file:
            json.dump(config_data, config_file)
        return mock_jira_config.upgrade(config_data)

    def test_upgrade_adds_github_repos_and_maps_flat_repo_to_default_team(self, mock_jira_config):
        upgraded = self._upgrade(mock_jira_config, self._v10_config())

        assert upgraded['version'] == 1.2
        assert upgraded['jira']['teams']['TestTeam']['github_repos'] == ["test-repo"]
        assert upgraded['jira']['teams']['OtherTeam']['github_repos'] == []

    def test_upgrade_leaves_claimed_repo_alone(self, mock_jira_config):
        config_data = self._v10_config()
        config_data['jira']['teams']['OtherTeam']['github_repos'] = ["test-repo"]

        upgraded = self._upgrade(mock_jira_config, config_data)

        assert upgraded['jira']['teams']['TestTeam']['github_repos'] == []
        assert upgraded['jira']['teams']['OtherTeam']['github_repos'] == ["test-repo"]

    def test_upgrade_is_idempotent(self, mock_jira_config):
        upgraded = self._upgrade(mock_jira_config, self._v10_config())
        upgraded_again = mock_jira_config.upgrade(json.loads(json.dumps(upgraded)))

        assert upgraded_again == upgraded

    def test_upgrade_preserves_other_config(self, mock_jira_config):
        original = self._v10_config()
        upgraded = self._upgrade(mock_jira_config, json.loads(json.dumps(original)))

        assert upgraded['github'] == original['github']
        assert upgraded['jira']['url'] == original['jira']['url']
        assert upgraded['jira']['teams']['TestTeam']['team_id'] == 42

    def test_upgrade_adds_branch_naming_defaults(self, mock_jira_config):
        upgraded = self._upgrade(mock_jira_config, self._v10_config())

        assert upgraded['git']['branch_name_model'] == 'haiku'
        assert upgraded['git']['max_branch_summary_length'] == 40

    def test_upgrade_keeps_existing_branch_naming_settings(self, mock_jira_config):
        config_data = self._v10_config()
        config_data['version'] = 1.1
        config_data['git'] = {"initials": "js", "branch_name_model": ""}

        upgraded = self._upgrade(mock_jira_config, config_data)

        assert upgraded['git']['branch_name_model'] == ""
        assert upgraded['git']['initials'] == "js"