import tempfile
import json
import os
from pathlib import Path

def show_viewer(string, file_type="md"):
    """
    Display content in a viewer with proper syntax highlighting
    
    Args:
        string: Content to display
        file_type: File type (extension) for syntax highlighting (default: md)
    """
    with tempfile.NamedTemporaryFile(suffix=f".{file_type}") as f:
        f.write(string.encode('utf-8'))
        f.flush()
        # Set proper filetype based on content
        filetype = "html" if file_type == "html" else "markdown" if file_type == "md" else "human"
        os.system(f"vim -N --clean +\"set filetype={filetype}\" " + f.name)

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

def view_description(issue, jira, as_html=False):
    """View issue description with optional HTML formatting"""
    content = jira.get_body(issue, include_comments=True, format_as_html=as_html)
    file_type = "html" if as_html else "md"
    show_viewer(content, file_type=file_type)

def write_issue_for_chat(issue, jira, as_html=False):
    """Write issue description to a file with optional HTML formatting"""
    chat_folder = Path.home() / ".jiratmp"
    chat_folder.mkdir(parents=True, exist_ok=True)
    
    # Use appropriate extension based on format
    extension = "html" if as_html else "md"
    filename = chat_folder / f"{issue.key}.{extension}"
    
    with open(filename, 'w', encoding='utf-8', errors='replace') as f:
        string = jira.get_body(issue, include_comments=True, format_as_html=as_html)
        f.write(string)
    return str(filename)
