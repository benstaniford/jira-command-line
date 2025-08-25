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