from .base_command import BaseCommand
from ..JiraXrayIssue import JiraXrayIssue

class XrayCommand(BaseCommand):
    @property
    def shortcut(self):
        return "x"
    
    @property
    def description(self):
        return "xray"
    
    def execute(self, ui, view, jira, config=None, **kwargs):
        try:
            # If no xray client_id or client_secret is set in the config, show an error
            if (config and (config.get('xray')['client_id'] == "" or config.get('xray')['client_secret'] == "")):
                ui.error("Xray client_id or client_secret not set in config, cannot create x-ray tests")
                return False

            selection = ui.prompt_get_string("Enter issue number")
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                ui.prompt("Parsing test definitions...", "")
                xray_issue = JiraXrayIssue(issue, jira)
                if (not xray_issue.sprint_item_has_valid_tests()):
                    yesno = ui.prompt_get_character(f"Warning: {issue.key} does not have valid tests. Create test template? (y/n)")
                    if yesno == "y":
                        xray_issue.create_test_template()
                else:
                    definitions = xray_issue.parse_test_definitions()
                    yesno = ui.prompt_get_character(f"Create {len(definitions)} tests for [{issue.key}] for repository folder \"{definitions.get_folder()}\" (y/n)")
                    if yesno == "y":
                        ui.prompt("Creating tests...", "")
                        tests = xray_issue.create_test_cases(definitions)
                        for test in tests:
                            ui.prompt(f"Created test:{test.key}", "")
                        test_plan = definitions.get_test_plan()
                        if (test_plan != None):
                            yesno = ui.prompt_get_character(f"\nCreated {len(tests)} tests for {issue.key}, add to test plan {test_plan}? (y/n)")
                            if yesno == "y":
                                test_ids = [test.id for test in tests]
                                if (xray_issue.create_update_test_plan(definitions, test_ids)):
                                    ui.prompt(f"Created test plan {test_plan} with tests:{test_ids}")
                                else:
                                    ui.prompt(f"Added to test plan {test_plan}, tests:{test_ids}")
                        ui.prompt_get_character(f"\nCreated {len(tests)} tests for {issue.key}, press any key to continue...")
        except Exception as e:
            ui.error("Create x-ray tests", e)
        return False
