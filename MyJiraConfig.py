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
                "default_team": "Sparklemuffin",
                "teams": {
                    "Sparklemuffin": {
                        "team_id": 34,
                        "project_name": "EPM",
                        "product_name": "PM Windows",
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
                        "escalation_board_id": 406
                    },
                    "Red Panda": {
                        "team_id": "e4e9e450-7523-478b-bccd-06ce6f7419ec-30",
                        "project_name": "EPM",
                        "product_name": "PM Windows",
                        "short_names_to_ids": {
                            "Jack": "jlawless@beyondtrust.com"
                        },
                        "kanban_board_id": 509,
                        "backlog_board_id": 69,
                        "escalation_board_id": 406
                    },
                    "Viscacha": {
                        "team_id": 33,
                        "project_name": "EPM",
                        "product_name": "PM Windows",
                        "short_names_to_ids": {
                            "Richard": "rpittello@beyondtrust.com"
                        },
                        "kanban_board_id": 509,
                        "backlog_board_id": 316,
                        "escalation_board_id": 406
                    },
                    "Mac": {
                        "team_id": 14,
                        "project_name": "EPM",
                        "product_name": "PM Mac",
                        "short_names_to_ids": {
                            "Omar": "oikram@beyondtrust.com"
                        },
                        "kanban_board_id": 509,
                        "backlog_board_id": 77,
                        "escalation_board_id": 406
                    }
                }
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
            },
            "xray": {
                "client_id": "",
                "client_secret": "",
                "project_id": "10027"
            }
        }

        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_file_path, "w") as config_file:
            json.dump(config_data, config_file, indent=4)

    def exists(self):
        return os.path.exists(self.config_file_path)

    def get_location(self):
        return self.config_file_path

    def load(self):
        config = {}
        with open(self.config_file_path, 'r') as json_file:
            return json.load(json_file)
