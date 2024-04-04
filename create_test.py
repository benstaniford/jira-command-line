#!/usr/bin/python

import argparse
from MyXray import MyXray

# Here's a reference PBI that shows the structure
# https://beyondtrust.atlassian.net/browse/EPM-16217
# Execution record: https://beyondtrust.atlassian.net/browse/EPM-21113

def prompt(message):
    return input(f"{message} (y/n): ")

# Parse --pbi argument
parser = argparse.ArgumentParser()
parser.add_argument("--pbi", help="Create a test issue for the given PBI")
args = parser.parse_args()

# Create the issue
if args.pbi is None:
    throw("Please provide a PBI --pbi")

# Create an instance of MyXray pointing at this PBI
xray = MyXray(args.pbi)
issue = xray.get_sprint_item()

if (not xray.sprint_item_has_valid_tests()):
    yesno = prompt(f"Warning: {issue.key} does not have valid tests. Create test template?")
    if yesno != "y":
        quit()
    xray.create_test_template()
    print(f"Created template in \"Test Result and Evidence\" for {issue.key}, please fill in the details and run this script again.")
    quit()

# Create a test case linked to this PBI
definitions = xray.parse_test_definitions()
print (f"Found {len(definitions)} test definitions under category \"{definitions.get_category()}\"")
for definition in definitions:
    print(definition)
yesno = prompt(f"Create tests for [{issue.key}] with the above definitions for category \"{definitions.get_category()}\"")
if yesno != "y":
    quit()

tests = xray.create_test_cases(definitions)
for test in tests:
    print(f"Created test:{test.key}")

yesno = prompt(f"\nCreated {len(tests)} tests for {issue.key}, delete?")
if yesno == "y":
    for test in tests:
        test.delete(deleteSubtasks=True)
        print(f"Deleted test:{test.key}")
