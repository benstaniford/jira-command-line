import os
import json

class MyJiraConfig:
    def __init__(self):
        home_dir = os.path.expanduser("~")
        self.config_dir = os.path.join(home_dir, ".jira-config")
        self.config_file_path = os.path.join(self.config_dir, "config.json")
    
    def generate_template(self):
        config_data = {
            "version": 1.0,
            "jira": {
                "url": "https://mycorp.atlassian.net",
                "password": "",
                "username": "myemail@mycorp.com",
                "fullname": "My Name",
                "default_team": "Sparklemuffin",
                "teams": {
                    "Sparklemuffin": {
                        "team_id": 34,
                        "project_name": "EPM",
                        "product_name": "PM Windows",
                        "short_names_to_ids": {
                            "Ben": "bstaniford@mycorp.com",
                            "Caleb": "ckershaw@mycorp.com",
                            "Dimi": "dbostock@mycorp.com",
                            "Connor": "cflynn@mycorp.com",
                            "Neil": "nwicker@mycorp.com",
                            "Nick": "ncrowley@mycorp.com",
                            "Tamas": "tvarady@mycorp.com",
                            "Unassigned": ""
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
                            "Jack": "jlawless@mycorp.com"
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
                            "Richard": "rpittello@mycorp.com"
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
                            "Omar": "oikram@mycorp.com"
                        },
                        "kanban_board_id": 509,
                        "backlog_board_id": 77,
                        "escalation_board_id": 406
                    }
                }
            },
            "github": {
                "username": "flast",
                "login": "firstlast",
                "token": "",
                "repo_owner": "mycorp",
                "repo_name": "epm-windows"
            },
            "git": {
                "initials": "mi"
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
        return config_data

    def exists(self):
        return os.path.exists(self.config_file_path)

    def get_location(self):
        return self.config_file_path

    def validate(self, json_config):
        if 'jira' not in json_config:
            raise ValueError("Jira config not found")
        if 'xray' not in json_config:
            raise ValueError("Xray config not found")
        jira = json_config.get('jira')
        if jira.get('url') is None or jira.get('url') == "":
            raise ValueError("Jira URL not found in config")
        if jira.get('username') is None or jira.get('username') == "" or jira.get('username') == "myemail@mycorp.com":
            raise ValueError("Jira username not specified in config")
        if jira.get('fullname') is None or jira.get('fullname') == "" or jira.get('fullname') == "My Name":
            raise ValueError("Jira fullname not specified in config")
        if jira.get('password') is None or jira.get('password') == "":
            raise ValueError("Jira password not found in config")

    def upgrade(self, config):
        try:
            # Pre 1.0 config files did not have a default_team
            if 'default_team' not in config['jira']:
                # Backup the file
                with open(self.config_file_path, "r") as config_file:
                    with open(self.config_file_path + ".upgraded.bak", "w") as backup_file:
                        backup_file.write(config_file.read())

                old_config = config
                generated_config = self.generate_template()
                generated_config['jira']['url'] = old_config['jira']['url']
                print (f"Upgrading username {old_config['jira']['username']}")
                generated_config['jira']['username'] = old_config['jira']['username']
                generated_config['jira']['password'] = old_config['jira']['password']
                generated_config['jira']['fullname'] = old_config['jira']['fullname']
                generated_config['github']['username'] = old_config['github']['username']
                generated_config['github']['login'] = old_config['github']['login']
                generated_config['github']['token'] = old_config['github']['token']
                generated_config['github']['repo_owner'] = old_config['github']['repo_owner']
                generated_config['github']['repo_name'] = old_config['github']['repo_name']
                generated_config['git']['initials'] = old_config['git']['initials']
                if 'xray' in old_config:
                    generated_config['xray']['client_id'] = old_config['xray']['client_id']
                    generated_config['xray']['client_secret'] = old_config['xray']['client_secret']
                username = old_config['jira']['username']
                company = username.split('@')[1].split('.')[0]
                for team in generated_config['jira']['teams']:
                    for short_name in generated_config['jira']['teams'][team]['short_names_to_ids']:
                        generated_config['jira']['teams'][team]['short_names_to_ids'][short_name] = generated_config['jira']['teams'][team]['short_names_to_ids'][short_name].replace('mycorp', company)

                config = generated_config
            if 'version' not in config:
                config['version'] = 1.0
            with open(self.config_file_path, "w") as config_file:
                json.dump(config, config_file, indent=4)
            return config  
        except:
            raise ValueError("Failed to upgrade config file")

    def load(self):
        with open(self.config_file_path, 'r') as json_file:
            config = json.load(json_file)
            config = self.upgrade(config)
            self.validate(config)
            return config
