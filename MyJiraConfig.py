import os
import json

class MyJiraConfig:
    def __init__(self):
        home_dir = os.path.expanduser("~")
        self.config_dir = os.path.join(home_dir, ".jira-config")
        self.config_file_path = os.path.join(self.config_dir, "config.json")
    
    def generate_template(self):
        config_data = {
            "jira": {
                "url": "https://beyondtrust.atlassian.net",
                "password": "",
                "username": "myemail@beyondtrust.com",
                "fullname": "My Name",
                "team_name": "Sparklemuffin",
                "team_id": 34,
                "project_name": "EPM",
                "short_names_to_ids": {
                    "Ben": "bstaniford@beyondtrust.com",
                    "Caleb": "ckershaw@beyondtrust.com",
                    "Dimi": "dbostock@beyondtrust.com",
                    "Connor": "cflynn@beyondtrust.com",
                    "Neil": "nwicker@beyondtrust.com",
                    "Nick": "ncrowley@beyondtrust.com",
                    "Tamas": "tvarady@beyondtrust.com"
                },
                "kanban_board_id": 385,
                "backlog_board_id": 341,
                "windows_escalation_board_id": 406
            },
            "github": {
                "username": "bstaniford",
                "login": "benstaniford",
                "token": "",
                "repo_owner": "BeyondTrust",
                "repo_name": "epm-windows"
            },
            "git": {
                "initials": "bs"
            }
        }

        print("Configuration file not found, generating template...")
        print("Please edit the configuration file and generate required PAT tokens for jira and github")

        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_file_path, "w") as config_file:
            json.dump(config_data, config_file, indent=4)
        print(f"Configuration file saved to: {self.config_file_path}")

    def exists(self):
        return os.path.exists(self.config_file_path)

    def load(self):
        config = {}
        with open(self.config_file_path, 'r') as json_file:
            return json.load(json_file)
