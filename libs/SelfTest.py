#scriptdoc: title="Live, read-only self test of the jira client for the current repo", tags="bt,work,jira"

import json
import os
import re
import shutil
import sys
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

from git import Repo

from .CommandRegistry import CommandRegistry
from .commands.base_command import BaseCommand
from .JiraTableView import JiraTableView
from .MyJiraIssue import MyJiraIssue
from .ViewMode import ViewMode

# Commands that can only be tested by writing to Jira, git or the disk. --test
# never runs them; the read-only groundwork of the others is checked instead
UNTESTED_COMMANDS = {
    "d": "deletes an issue",
    "e": "adds a comment",
    "k": "creates a spike issue",
    "S": "creates a local support folder",
    "q": "only quits",
}

class CheckSkipped(Exception):
    pass

class CheckWarning(Exception):
    pass

class HeadlessTableView:
    """
    Stands in for CursesTableView so the real commands and JiraTableView run
    unchanged without a terminal. Prompts are answered from a script, every
    y/n confirmation is refused, and errors are recorded rather than shown.
    """
    def __init__(self) -> None:
        self.header: List[str] = []
        self.rows: List[tuple] = []  # (cells, data, is_subrow)
        self.errors: List[tuple] = []
        self.answers: List[Any] = []
        self.subrows_enabled = False
        self.cursor: Optional[int] = None

    def _next_answer(self) -> Any:
        return self.answers.pop(0) if self.answers else ""

    def active_rows(self) -> List[tuple]:
        return [r for r in self.rows if self.subrows_enabled or not r[2]]

    # Table
    def clear(self) -> None:
        self.header = []
        self.rows = []
        self.cursor = None

    def add_header(self, header: List[str]) -> None:
        self.header = list(header)

    def add_row(self, row, data=None, subrows=None, row_index=None, parent_row=None) -> None:
        self.rows.append((list(row), data, parent_row is not None))
        for subrow, subrow_data in subrows or []:
            self.add_row(subrow, subrow_data, parent_row=row)

    def get_row(self, row_index: int):
        cells, data, _ = self.active_rows()[row_index]
        return cells, data

    def get_rows(self) -> List[tuple]:
        return self.active_rows()

    def toggle_subrows(self) -> None:
        self.subrows_enabled = not self.subrows_enabled

    # Row cursor
    def has_selection(self) -> bool:
        return self.cursor is not None

    def clear_selection(self) -> None:
        self.cursor = None

    def get_selected_row(self):
        return self.get_row(self.cursor) if self.cursor is not None else None

    # Prompts
    def prompt(self, prompt_text, prompt_suffix=" >", color=None) -> None:
        pass

    def error(self, msg, exception=None) -> None:
        self.errors.append((msg, exception))

    def prompt_get_character(self, prompt_text) -> str:
        return "n"

    def prompt_get_string(self, prompt, keypresses=None, filter_key=None, sort_keys=None, search_key=None, ctrl_keys=None, escape_returns: Any = "") -> Any:
        return self._next_answer()

    def prompt_get_issue(self, prompt_text="Enter issue number", keypresses=None):
        selected = self.get_selected_row()
        if selected is not None:
            return ["", selected[0], selected[1]]
        return ["", None, None]

    def prompt_with_choice_list(self, prompt_text, choices, non_numeric_keypresses=False):
        answer = self._next_answer()
        for index, choice in enumerate(choices):
            if str(choice) == str(answer):
                return (index, choice)
        return (None, "")

    def prompt_with_choice_dictionary(self, prompt_text, dictionary):
        return None

    def prompt_fuzzy_find(self, prompt_text, choices, max_display=4) -> str:
        answer = self._next_answer()
        return answer if answer in choices else ""

    # Drawing
    def draw(self) -> None:
        pass

    def enable_row_numbers(self) -> None:
        pass

    def disable_row_numbers(self) -> None:
        pass

class SelfTest:
    """
    Runs the jira client against the real Jira, git and github for the
    repository in the current directory, without writing anything, and prints
    a PASS/WARN/FAIL/SKIP line per check.
    """
    COLOURS = {"PASS": "\033[32m", "WARN": "\033[33m", "FAIL": "\033[31m", "SKIP": "\033[36m"}

    def __init__(self, jira: Any, mygit: Any, mygithub: Any, config: Dict[str, Any], origin: Optional[tuple], out=sys.stdout) -> None:
        self.jira = jira
        self.mygit = mygit
        self.mygithub = mygithub
        self.config = config
        self.origin = origin
        self.out = out
        self.colour = hasattr(out, "isatty") and out.isatty()

        self.ui = HeadlessTableView()
        self.view = JiraTableView(self.ui, jira)
        self.registry = CommandRegistry()
        self.counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "SKIP": 0}
        self.covered: set = set()
        # Every full issue any view returned, by key, for the column and
        # command checks; filled in as the views run
        self.seen: Dict[str, Any] = {}

    # Returns the process exit code: 1 if any check failed
    def run(self) -> int:
        repo = f"{self.origin[0]}/{self.origin[1]}" if self.origin else "no github remote"
        self.write(f"Jira self test: team {self.jira.team_name}, {repo}, {os.getcwd()}")

        self.section("Environment")
        self.check("git remote", self.check_git_remote)
        self.check("team", self.check_team)
        self.check("jira login", self.check_jira_login)
        self.check("custom field mapping", self.check_field_mapping)
        self.check("command registry", self.check_registry)

        self.section("Views")
        self.check("l: backlog", lambda: self.check_view_command("l", ViewMode.BACKLOG), "l")
        self.check("s: sprint", lambda: self.check_view_command("s", ViewMode.SPRINT, ["Points"]), "s")
        self.check("L: sprints", lambda: self.check_view_command("L", ViewMode.SPRINTS, ["Sprint"]), "L")
        self.check("W: windows shared", lambda: self.check_view_command("W", ViewMode.WINDOWS_SHARED), "W")
        self.check("z: escalations", self.check_escalations, "z")
        boards = self.jira.get_boards()
        if not boards:
            self.check("B: boards", self.skip("no boards configured"), "B")
        for board in boards:
            self.check(f"B: board {board}", lambda board=board: self.check_view_command("B", ViewMode.BOARD, answers=[board]), "B")
        self.check("r: refresh", self.check_refresh, "r")
        self.check("T: sub-tasks", self.check_toggle_subtasks, "T")
        self.check("digit: story sub-tasks", self.check_story_drilldown, "digit")
        self.check("digit: epic children", self.check_epic_drilldown, "digit")
        self.check("?: text search", self.check_text_search, "?")
        self.check("?: key search", self.check_key_search, "?")
        self.check("?: number search", self.check_number_search, "?")
        self.check("?: label search", self.check_label_search, "?")
        self.check("KEY_F1: help", self.check_help, "KEY_F1")

        self.section("Columns and issue types")
        self.check("issue types", self.check_issue_types)
        for index, (name, column) in enumerate(self.jira.get_optional_fields().items()):
            self.check(f"F{index + 2}: {name.lower()}", lambda column=column: self.check_column(column))
        self.check("all columns at once", self.check_all_columns)

        self.section("Commands (read-only parts)")
        self.check("v: view markdown", lambda: self.check_body(as_html=False), "v")
        self.check("v: view html", lambda: self.check_body(as_html=True))
        self.check("i: inspect", self.check_inspect, "i")
        self.check("b: browse", self.check_browse, "b")
        self.check("a: assign", self.check_assign, "a")
        self.check("t: status", self.check_status, "t")
        self.check("P: points", self.check_points, "P")
        self.check("c: create", self.check_create, "c")
        self.check("m: move", self.check_move, "m")
        self.check("E: team", self.check_teams, "E")
        self.check("h: branch", self.check_branch, "h")
        self.check("w: worktree", self.check_worktree, "w")
        self.check("p: pr", self.check_pr, "p")
        self.check("x: xray", self.check_xray, "x")
        self.check("V: visualise", self.check_visualise, "V")

        self.section("Not run (they write)")
        for shortcut, reason in UNTESTED_COMMANDS.items():
            self.check(f"{shortcut}: {self.describe(shortcut)}", self.skip(reason), shortcut)
        self.check("command coverage", self.check_coverage)

        summary = ", ".join(f"{count} {status.lower()}" for status, count in self.counts.items())
        self.write(f"\n{summary}")
        return 1 if self.counts["FAIL"] else 0

    # Output and check plumbing
    def write(self, text: str) -> None:
        print(text, file=self.out, flush=True)

    def section(self, title: str) -> None:
        self.write(f"\n{title}")

    def check(self, name: str, fn: Callable[[], Optional[str]], command: Optional[str] = None) -> None:
        if command:
            self.covered.add(command)
        start = time.monotonic()
        try:
            status, detail = "PASS", fn() or ""
        except CheckSkipped as e:
            status, detail = "SKIP", str(e)
        except CheckWarning as e:
            status, detail = "WARN", str(e)
        except Exception as e:
            status, detail = "FAIL", f"{type(e).__name__}: {e}".split("\n")[0]
            if os.environ.get("JIRA_TEST_TRACEBACK"):
                traceback.print_exc(file=self.out)
        elapsed = time.monotonic() - start
        self.counts[status] += 1
        label = f"{self.COLOURS[status]}{status}\033[0m" if self.colour else status
        self.write(f"  {label}  {name:<36} {detail} ({elapsed:.1f}s)")

    def skip(self, reason: str) -> Callable[[], None]:
        def fn():
            raise CheckSkipped(reason)
        return fn

    def describe(self, shortcut: str) -> str:
        command = self.registry.get_command(shortcut)
        return command.description if command else "?"

    def require(self, condition: Any, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    def sample(self, predicate: Callable[[Any], bool] = lambda issue: True, what: str = "issue") -> Any:
        for issue in self.seen.values():
            if predicate(issue):
                return issue
        raise CheckSkipped(f"no {what} in any view")

    def run_command(self, shortcut: str, answers: Optional[List[Any]] = None, **kwargs) -> Any:
        self.ui.errors = []
        self.ui.answers = list(answers or [])
        result = self.registry.get_command(shortcut).execute(
            ui=self.ui, view=self.view, jira=self.jira, mygit=self.mygit,
            mygithub=self.mygithub, config=self.config, stdscr=None, **kwargs)
        if self.ui.errors:
            msg, exception = self.ui.errors[0]
            raise RuntimeError(f"{msg}: {exception}" if exception is not None else msg)
        return result

    # Checks the table the last command drew is well formed and records its issues
    def check_table(self, mode: int, extra_headers: Optional[List[str]] = None) -> str:
        self.require(self.view.mode == mode, f"view mode is {self.view.mode}, expected {mode}")
        self.require(self.ui.header[:3] == ["Key", "Summary", "Status"], f"unexpected header {self.ui.header}")
        for header in extra_headers or []:
            self.require(header in self.ui.header, f"{header} column missing from {self.ui.header}")
        issues = subtasks = 0
        for cells, data, is_subrow in self.ui.rows:
            width = 3 if is_subrow else len(self.ui.header)
            self.require(len(cells) == width, f"{data.key} has {len(cells)} cells, expected {width}")
            bad = [c for c in cells if not isinstance(c, str)]
            self.require(not bad, f"{data.key} has non-text cells {bad}")
            if is_subrow:
                subtasks += 1
            else:
                issues += 1
                self.seen.setdefault(data.key, data)
        return f"{issues} issues, {subtasks} sub-tasks"

    def find_row(self, predicate: Callable[[Any], bool]) -> Optional[int]:
        for index, (cells, data, is_subrow) in enumerate(self.ui.active_rows()):
            if predicate(data):
                return index
        return None

    # Environment
    def check_git_remote(self) -> str:
        if not self.origin:
            raise CheckWarning("not a github checkout, so the default team and configured github repo are used")
        return f"{self.origin[0]}/{self.origin[1]}"

    def check_team(self) -> str:
        if not self.origin:
            return f"{self.jira.team_name} (default team)"
        claimed = self.jira.find_team_for_github_repo(self.origin[1])
        if claimed is None:
            raise CheckWarning(f"no team lists {self.origin[1]} in github_repos, using {self.jira.team_name}")
        if claimed != self.jira.team_name:
            return f"{self.jira.team_name} (--team, repo belongs to {claimed})"
        projects = ", ".join(self.jira._project_names())
        return f"{self.jira.team_name}, projects {projects}"

    def check_jira_login(self) -> str:
        me = self.jira.jira.myself()
        return f"{me.get('displayName')} on {self.jira.url}"

    def check_field_mapping(self) -> str:
        mapping = MyJiraIssue(None, self.jira.jira).translations
        missing = [name for name in ("story_points", "sprint", "priority_score") if name not in mapping]
        if missing:
            raise CheckWarning(f"no Jira field found for {', '.join(missing)}")
        return f"{len(mapping)} fields mapped"

    def check_registry(self) -> str:
        loaded = {type(command) for command in self.registry.commands.values()}
        shadowed = []
        for name, module in list(sys.modules.items()):
            if not name.startswith("libs.commands.") or not name.endswith("_command"):
                continue
            for attr in vars(module).values():
                if (isinstance(attr, type) and issubclass(attr, BaseCommand) and attr is not BaseCommand
                        and attr.__module__ == name and attr not in loaded):
                    shadowed.append(f"{name.split('.')[-1]} ({attr().shortcut})")
        if shadowed:
            raise CheckWarning(f"hidden by a duplicate shortcut: {', '.join(shadowed)}")
        return f"{len(self.registry.commands)} commands"

    # Views
    def check_view_command(self, shortcut: str, mode: int, extra_headers: Optional[List[str]] = None, answers: Optional[List[Any]] = None) -> str:
        self.run_command(shortcut, answers)
        return self.check_table(mode, extra_headers)

    def check_escalations(self) -> str:
        if not self.jira.product_name:
            raise CheckSkipped(f"team {self.jira.team_name} has no product_name")
        return self.check_view_command("z", ViewMode.ESCALATIONS)

    # Refresh and the sub-task toggle use the backlog, which unlike the sprint
    # is rarely empty
    def check_refresh(self) -> str:
        self.run_command("l")
        before = [data.key for _, data, _ in self.ui.rows]
        self.run_command("r")
        self.check_table(ViewMode.BACKLOG)
        after = [data.key for _, data, _ in self.ui.rows]
        self.require(len(after) == len(before), f"backlog had {len(before)} rows, {len(after)} after refresh")
        return f"backlog re-queried, {len(after)} rows"

    def check_toggle_subtasks(self) -> str:
        self.run_command("l")
        parents = len(self.ui.active_rows())
        self.run_command("T")
        try:
            self.require(len(self.ui.active_rows()) == len(self.ui.rows), "sub-tasks still hidden after toggling on")
        finally:
            self.run_command("T")
        self.require(len(self.ui.active_rows()) == parents, "sub-tasks still shown after toggling off")
        return f"{len(self.ui.rows) - parents} sub-tasks shown and hidden"

    # Drills into a row of the given view via a row number, as typing it would
    def drill_into(self, shortcut: str, predicate: Callable[[Any], bool], what: str) -> Any:
        self.run_command(shortcut)
        index = self.find_row(predicate)
        if index is None:
            raise CheckSkipped(f"no {what} in the {self.describe(shortcut)} view")
        parent = self.ui.get_row(index)[1]
        self.run_command("digit", selection=str(index + 1))
        return parent

    def check_story_drilldown(self) -> str:
        has_subtasks = lambda issue: not self.jira.is_epic(issue) and len(issue.fields.subtasks) > 0
        try:
            parent = self.drill_into("s", has_subtasks, "issue with sub-tasks")
        except CheckSkipped:
            parent = self.drill_into("l", has_subtasks, "issue with sub-tasks in the sprint or")
        detail = self.check_table(ViewMode.TASKVIEW, ["Assignee"])
        self.require(self.view.parent_issue.key == parent.key, f"drilled into {self.view.parent_issue.key}, expected {parent.key}")
        self.require(len(self.ui.rows) > 0, f"{parent.key} lists {len(parent.fields.subtasks)} sub-tasks but none were fetched")
        self.view.previous()
        self.require(not self.view.has_previous(), "escape did not return to the top level")
        return f"{parent.key}: {detail}"

    def check_epic_drilldown(self) -> str:
        epic = self.drill_into("l", self.jira.is_epic, "epic")
        detail = self.check_table(ViewMode.TASKVIEW, ["Assignee", "Points"])
        # One level further, so the nested drill-down stack is exercised too
        index = self.find_row(lambda issue: len(issue.fields.subtasks) > 0)
        if index is not None:
            child = self.ui.get_row(index)[1]
            self.run_command("digit", selection=str(index + 1))
            self.check_table(ViewMode.TASKVIEW, ["Assignee"])
            self.require(self.view.parent_issue.key == child.key, f"drilled into {self.view.parent_issue.key}, expected {child.key}")
            self.view.previous()
            self.require(self.view.parent_issue.key == epic.key, f"escape returned to {self.view.parent_issue.key}, expected {epic.key}")
            detail += f", then {child.key}"
        self.view.previous()
        self.require(self.view.mode == ViewMode.BACKLOG and not self.view.has_previous(), "escape did not return to the backlog")
        return f"{epic.key}: {detail}"

    def search(self, answers: List[Any], mode: int = ViewMode.SEARCH) -> List[str]:
        self.run_command("?", answers)
        self.check_table(mode)
        return [data.key for _, data, is_subrow in self.ui.rows if not is_subrow]

    def check_text_search(self) -> str:
        issue = self.sample(lambda issue: re.search(r"[A-Za-z]{4,}", issue.fields.summary or ""), "issue with a worded summary")
        word = max(re.findall(r"[A-Za-z]+", issue.fields.summary), key=len)
        keys = self.search([word])
        if not keys:
            raise CheckWarning(f"no results for '{word}' (from {issue.key})")
        return f"'{word}': {len(keys)} issues"

    def check_key_search(self) -> str:
        issue = self.sample()
        keys = self.search([issue.key])
        self.require(issue.key in keys, f"{issue.key} not found, got {keys[:5]}")
        return issue.key

    def check_number_search(self) -> str:
        projects = self.jira._project_names()
        issue = self.sample(lambda issue: issue.key.split("-")[0] in projects and str(issue.fields.issuetype) not in ("Sub-task", "Sub-task Bug"), "issue in the team's projects")
        number = issue.key.split("-")[1]
        keys = self.search([number])
        if issue.key not in keys:
            # The number search is scoped by product, which a key search is not
            raise CheckWarning(f"'{number}' did not find {issue.key}, got {keys[:5]}")
        return f"'{number}' found {issue.key}"

    def check_label_search(self) -> str:
        labels = self.jira.get_labels()
        self.require(labels, "Jira returned no labels")
        issue = self.sample(lambda issue: getattr(issue.fields, "labels", None), "labelled issue")
        label = issue.fields.labels[0]
        self.require(label in labels, f"{issue.key}'s label '{label}' is missing from the {len(labels)} labels Jira listed")
        keys = self.search(["CTRL-l", label], ViewMode.LABEL_SEARCH)
        if not keys:
            raise CheckWarning(f"no results for label '{label}' (from {issue.key})")
        return f"'{label}': {len(keys)} issues, {len(labels)} labels"

    def check_help(self) -> str:
        self.run_command("KEY_F1")
        self.require(len(self.ui.rows) > 0, "help drew no rows")
        return f"{len(self.ui.rows)} rows"

    # Columns and issue types
    def check_issue_types(self) -> str:
        if not self.seen:
            raise CheckWarning("no views returned any issues")
        types: Dict[str, int] = {}
        for issue in self.seen.values():
            name = str(issue.fields.issuetype)
            types[name] = types.get(name, 0) + 1
        return ", ".join(f"{count} {name}" for name, count in sorted(types.items()))

    def check_column(self, column: Callable[[Any], Any]) -> str:
        if not self.seen:
            raise CheckSkipped("no issues to show")
        # (issues, issues with a value) per project
        counts: Dict[str, List[int]] = {}
        for issue in self.seen.values():
            try:
                value = column(issue)
            except Exception as e:
                raise AssertionError(f"{issue.key} ({issue.fields.issuetype}): {type(e).__name__}: {e}")
            self.require(isinstance(value, str), f"{issue.key} gave {type(value).__name__} {value!r}, not text")
            project = counts.setdefault(issue.key.split("-")[0], [0, 0])
            project[0] += 1
            project[1] += value not in ("", "None")
        detail = ", ".join(f"{name} {filled}/{total}" for name, (total, filled) in sorted(counts.items()))
        # A column that renders but is blank everywhere is usually a field the
        # project doesn't use, or one we're reading from the wrong place. Boards
        # and shared views pull in other teams' projects, so the team's own
        # projects are judged on their own rather than lost in the pool
        team_projects = [name for name in self.jira._project_names() if name in counts] or list(counts)
        blank = [name for name in team_projects if counts[name][1] == 0]
        if blank:
            raise CheckWarning(f"blank for every {', '.join(blank)} issue ({detail})")
        return f"with values: {detail}"

    def check_all_columns(self) -> str:
        self.run_command("l")
        try:
            self.view.rebuild(extra_columns=self.jira.get_optional_fields())
            return self.check_table(ViewMode.BACKLOG, list(self.jira.get_optional_fields().keys()))
        finally:
            self.view.rebuild(extra_columns={})

    # Commands (read-only parts)
    def one_per_type(self) -> List[Any]:
        if not self.seen:
            raise CheckSkipped("no issues to show")
        by_type: Dict[str, Any] = {}
        for issue in self.seen.values():
            by_type.setdefault(str(issue.fields.issuetype), issue)
        return list(by_type.values())

    def check_body(self, as_html: bool) -> str:
        issues = self.one_per_type()
        for issue in issues:
            try:
                body = self.jira.get_body(issue, include_comments=True, format_as_html=as_html)
            except Exception as e:
                raise AssertionError(f"{issue.key} ({issue.fields.issuetype}): {type(e).__name__}: {e}")
            self.require(issue.fields.summary in body or (as_html and body), f"{issue.key}'s summary is missing from its body")
        return f"{len(issues)} issue types, editor not opened"

    def check_inspect(self) -> str:
        for issue in self.seen.values():
            json.dumps(issue.raw, indent=4, sort_keys=True)
        return f"{len(self.seen)} issues, editor not opened"

    def check_browse(self) -> str:
        url = self.sample().permalink()
        self.require(url.startswith(self.jira.url), f"permalink {url} is not on {self.jira.url}")
        boards = [name for name, board_id in (("sprintboard", self.jira.backlog_board_id), ("kanban", self.jira.kanban_board_id)) if board_id]
        detail = f"{url}, boards: {', '.join(boards) or 'none'}, browser not opened"
        if not boards:
            raise CheckWarning(detail)
        return detail

    def check_assign(self) -> str:
        users = self.jira.get_assignable_users()
        self.require(users, f"no assignable users for {self.jira.project_name}")
        return f"{len(users)} assignable users"

    def check_status(self) -> str:
        issue = self.sample(lambda issue: not self.jira.is_epic(issue), "non-epic")
        statuses = self.jira.get_statuses(issue)
        self.require(statuses, f"no statuses for {issue.key}")
        transitions = self.jira.transitions(issue)
        return f"{issue.key}: {len(statuses)} statuses, {len(transitions)} transitions"

    def check_points(self) -> str:
        issue = self.sample()
        fieldname = getattr(MyJiraIssue(issue, self.jira.jira), "story_points_fieldname", None)
        self.require(fieldname, "no story points field")
        if self.registry.get_command("P").description != "points":
            raise CheckWarning(f"field {fieldname} ok, but P runs '{self.describe('P')}' instead of points")
        return f"field {fieldname}"

    def check_create(self) -> str:
        types = self.jira.get_possible_types()
        self.require(types, "no issue types")
        components = self.jira.jira.project_components(self.jira.reference_issue.fields.project.id)
        return f"reference {self.jira.reference_issue.key}, {len(types)} types, {len(components)} components"

    def check_move(self) -> str:
        if not self.jira.get_sprint_issues():
            raise CheckSkipped("no open sprint to move issues to")
        return f"active sprint {self.jira._get_active_sprint_id()}"

    def check_teams(self) -> str:
        teams = self.jira.get_teams()
        self.require(self.jira.team_name in teams, f"{self.jira.team_name} is not a configured team")
        return f"{len(teams)} teams, not switched"

    def check_git_repo(self) -> Any:
        try:
            repo = Repo(".", search_parent_directories=True)
        except Exception:
            raise CheckSkipped("not in a git repository")
        refs = [ref.name for ref in repo.refs]
        self.require("main" in refs or "origin/main" in refs, "no main branch to start from")
        return repo

    def check_branch(self) -> str:
        repo = self.check_git_repo()
        self.require(self.mygit.initials, "git.initials not set in config")
        issue = self.sample()
        branch = self.mygit.branch_name_for_issue(issue.key, issue.fields.summary)
        self.require(branch.startswith(f"{self.mygit.initials}/{issue.key.lower()}/"), f"unexpected branch name {branch}")
        detail = f"{branch}, not created"
        if repo.is_dirty():
            raise CheckWarning(f"{detail}, but the repo is dirty so h would refuse")
        return detail

    def check_worktree(self) -> str:
        self.check_git_repo()
        if shutil.which("claude") is None:
            raise CheckWarning("claude is not on the PATH, so w cannot start it")
        return "claude found, worktree not created"

    def check_pr(self) -> str:
        if self.mygithub is None:
            raise CheckSkipped("no github token in config")
        repo = self.mygithub.github.get_repo(f"{self.mygithub.repo_owner}/{self.mygithub.repo_name}")
        branch = self.mygit.current_branch()
        detail = f"{repo.full_name} on branch {branch}, PR not created"
        if not repo.permissions.push:
            raise CheckWarning(f"{detail}, but the token cannot push")
        return detail

    def check_xray(self) -> str:
        xray = self.config.get("xray") or {}
        if not xray.get("client_id") or not xray.get("client_secret"):
            raise CheckSkipped("no xray client_id/client_secret in config")
        from .JiraXrayIssue import JiraXrayIssue
        from .XrayApi import XrayApi
        XrayApi(xray).authenticate()
        issue = self.sample(lambda issue: not self.jira.is_epic(issue), "non-epic")
        valid = JiraXrayIssue(issue, self.jira).sprint_item_has_valid_tests()
        return f"authenticated, {issue.key} {'has' if valid else 'has no'} test definitions"

    def check_visualise(self) -> str:
        if not os.environ.get("LOGSERVER") or not os.environ.get("LOGUSER"):
            raise CheckSkipped("LOGSERVER/LOGUSER not set")
        from .MyJiraLog import MyJiraLog
        log_file = MyJiraLog().get_log(1)
        os.unlink(log_file)
        return "sprint log fetched, nothing plotted"

    def check_coverage(self) -> str:
        missing = [shortcut for shortcut in self.registry.commands if shortcut not in self.covered]
        if missing:
            raise CheckWarning(f"not covered by --test: {', '.join(missing)}")
        return f"all {len(self.registry.commands)} commands"
