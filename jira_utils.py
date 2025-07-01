import tempfile
import json
import os

def show_viewer(string):
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        f.write(string.encode('utf-8'))
        f.flush()
        os.system("vim -N --clean +\"set filetype=human\" " + f.name)

def get_string_from_editor():
    filename = None
    with tempfile.NamedTemporaryFile(mode='w+t', suffix=".txt") as f:
        filename = f.name
        f.write("")
    os.system(f"vim -N --clean {filename}")
    with open(filename, 'r+t') as f:
        return f.read()

def inspect_issue(issue):
    show_viewer(json.dumps(issue.raw, indent=4, sort_keys=True))

def view_description(issue, jira):
    show_viewer(jira.get_body(issue, include_comments=True))

def write_issue_for_chat(issue, jira):
    chat_folder = "~/.jiratmp"
    if not os.path.exists(chat_folder):
        os.makedirs(chat_folder)
    filename = os.path.join(chat_folder, f"{issue.key}.json")
    with open(filename, 'w', encoding='utf-8', errors='replace') as f:
        string = jira.get_body(issue, include_comments=True)
        f.write(string)
    return filename
