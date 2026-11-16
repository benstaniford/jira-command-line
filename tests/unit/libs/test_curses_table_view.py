import pytest
from unittest.mock import Mock, patch

from libs.CursesTableView import CursesTableView


# Real curses constants, so the patched module behaves predictably
KEY_UP = 259
KEY_DOWN = 258
KEY_NPAGE = 338
A_REVERSE = 262144


@pytest.fixture
def curses_mock():
    """Patches the curses module inside CursesTableView with sane screen dimensions"""
    with patch("libs.CursesTableView.curses") as mock_curses:
        mock_curses.LINES = 30
        mock_curses.COLS = 120
        mock_curses.KEY_UP = KEY_UP
        mock_curses.KEY_DOWN = KEY_DOWN
        mock_curses.KEY_NPAGE = KEY_NPAGE
        mock_curses.KEY_PPAGE = 339
        mock_curses.KEY_RESIZE = 410
        mock_curses.KEY_F0 = 264
        mock_curses.A_REVERSE = A_REVERSE
        mock_curses.A_NORMAL = 0
        mock_curses.A_BOLD = 2097152
        mock_curses.COLOR_WHITE = 7
        mock_curses.COLOR_RED = 1
        mock_curses.color_pair.side_effect = lambda n: n * 256
        yield mock_curses


def move_cursor(view, increment):
    """Presses an arrow key, which is what the real prompt loop does"""
    getattr(view, "_CursesTableView__move_cursor")(increment)


def move_page(view, increment):
    """Presses PgUp/PgDn"""
    getattr(view, "_CursesTableView__move_page")(increment)


def rows_per_page(view):
    return getattr(view, "_CursesTableView__calc_rows_per_page")()


def build_view(curses_mock, num_rows=10):
    """A view with num_rows rows, each carrying a mock issue as its data"""
    view = CursesTableView(Mock())
    view.header_color = 1
    view.set_column_colors([1, 2, 3])
    view.add_header(["Key", "Summary", "Status"])
    for i in range(num_rows):
        issue = Mock()
        issue.key = f"TEST-{i + 1}"
        view.add_row([issue.key, f"Summary {i + 1}", "Open"], issue)
    return view


class TestCursorState:
    def test_no_cursor_by_default(self, curses_mock):
        view = build_view(curses_mock)
        assert view.cursor_index is None
        assert view.has_selection() is False
        assert view.get_selected_row() is None

    def test_first_down_summons_cursor_at_top_of_page(self, curses_mock):
        view = build_view(curses_mock)
        move_cursor(view, 1)
        assert view.cursor_index == 0
        assert view.has_selection() is True

    def test_first_up_summons_cursor_at_top_of_page(self, curses_mock):
        """The first press only makes the cursor appear, whichever direction it was"""
        view = build_view(curses_mock)
        move_cursor(view, -1)
        assert view.cursor_index == 0

    def test_cursor_moves_down_and_up(self, curses_mock):
        view = build_view(curses_mock)
        for _ in range(3):
            move_cursor(view, 1)
        assert view.cursor_index == 2
        move_cursor(view, -1)
        assert view.cursor_index == 1

    def test_cursor_stops_at_top(self, curses_mock):
        view = build_view(curses_mock)
        for _ in range(5):
            move_cursor(view, -1)
        assert view.cursor_index == 0

    def test_cursor_stops_at_last_row(self, curses_mock):
        view = build_view(curses_mock, num_rows=4)
        for _ in range(10):
            move_cursor(view, 1)
        assert view.cursor_index == 3

    def test_cursor_ignored_on_empty_table(self, curses_mock):
        view = build_view(curses_mock, num_rows=0)
        move_cursor(view, 1)
        assert view.cursor_index is None

    def test_get_selected_row_returns_issue(self, curses_mock):
        view = build_view(curses_mock)
        move_cursor(view, 1)
        move_cursor(view, 1)
        [row, issue] = view.get_selected_row()
        assert issue.key == "TEST-2"

    def test_clear_selection_hides_cursor(self, curses_mock):
        view = build_view(curses_mock)
        move_cursor(view, 1)
        view.clear_selection()
        assert view.get_selected_row() is None

    def test_clear_resets_cursor(self, curses_mock):
        """Every view rebuild goes through clear(), so the cursor must not survive it"""
        view = build_view(curses_mock)
        move_cursor(view, 1)
        view.clear()
        assert view.cursor_index is None


class TestCursorPaging:
    def test_cursor_pages_forward_off_the_bottom(self, curses_mock):
        view = build_view(curses_mock, num_rows=60)
        per_page = rows_per_page(view)

        # Walk to the last row of page one
        for _ in range(per_page):
            move_cursor(view, 1)
        assert view.cursor_index == per_page - 1
        assert view.current_page == 1

        # One more step lands on the first row of page two
        move_cursor(view, 1)
        assert view.cursor_index == per_page
        assert view.current_page == 2

    def test_cursor_pages_back_off_the_top(self, curses_mock):
        view = build_view(curses_mock, num_rows=60)
        per_page = rows_per_page(view)
        for _ in range(per_page + 1):
            move_cursor(view, 1)
        assert view.current_page == 2

        move_cursor(view, -1)
        assert view.cursor_index == per_page - 1
        assert view.current_page == 1

    def test_page_key_takes_cursor_along(self, curses_mock):
        """PgDn must not leave the cursor off-screen on a page nobody is looking at"""
        view = build_view(curses_mock, num_rows=60)
        per_page = rows_per_page(view)
        move_cursor(view, 1)
        move_page(view, 1)
        assert view.current_page == 2
        assert view.cursor_index == per_page

    def test_page_key_leaves_cursor_absent(self, curses_mock):
        view = build_view(curses_mock, num_rows=60)
        move_page(view, 1)
        assert view.cursor_index is None


class TestCursorClamping:
    def test_filter_shrinking_table_clamps_cursor(self, curses_mock):
        view = build_view(curses_mock, num_rows=10)
        for _ in range(8):
            move_cursor(view, 1)
        assert view.cursor_index == 7

        view.current_filter = "TEST-1 "  # matches only the first row
        [row, issue] = view.get_selected_row()
        assert view.cursor_index == 0
        assert issue.key == "TEST-1"

    def test_filter_matching_nothing_drops_cursor(self, curses_mock):
        view = build_view(curses_mock)
        move_cursor(view, 1)
        view.current_filter = "no such issue"
        assert view.get_selected_row() is None
        assert view.has_selection() is False


class TestPromptGetIssue:
    def test_cursor_answers_without_prompting(self, curses_mock):
        view = build_view(curses_mock)
        move_cursor(view, 1)
        view.prompt_get_string = Mock()

        [selection, row, issue] = view.prompt_get_issue()

        view.prompt_get_string.assert_not_called()
        assert selection == ""
        assert issue.key == "TEST-1"

    def test_prompts_when_no_cursor(self, curses_mock):
        view = build_view(curses_mock)
        view.prompt_get_string = Mock(return_value="3")

        [selection, row, issue] = view.prompt_get_issue()

        view.prompt_get_string.assert_called_once()
        assert selection == "3"
        assert issue.key == "TEST-3"

    def test_keypresses_still_prompt_when_cursor_set(self, curses_mock):
        """Browse keeps its board options reachable even with a row selected"""
        view = build_view(curses_mock)
        move_cursor(view, 1)
        view.prompt_get_string = Mock(return_value="k")

        [selection, row, issue] = view.prompt_get_issue("Enter issue number", ("s", "l", "k"))

        view.prompt_get_string.assert_called_once()
        assert selection == "k"
        assert issue is None

    def test_empty_answer_falls_back_to_cursor(self, curses_mock):
        view = build_view(curses_mock)
        move_cursor(view, 1)
        view.prompt_get_string = Mock(return_value="")

        [selection, row, issue] = view.prompt_get_issue("Enter issue number", ("s", "l", "k"))

        assert issue.key == "TEST-1"

    def test_escape_returns_nothing(self, curses_mock):
        view = build_view(curses_mock)
        move_cursor(view, 1)
        view.prompt_get_string = Mock(return_value=None)

        [selection, row, issue] = view.prompt_get_issue("Enter issue number", ("s", "l", "k"))

        assert selection == ""
        assert issue is None

    def test_out_of_range_number_returns_nothing(self, curses_mock):
        view = build_view(curses_mock, num_rows=3)
        view.prompt_get_string = Mock(return_value="99")

        [selection, row, issue] = view.prompt_get_issue()

        assert selection == "99"
        assert issue is None

    def test_zero_returns_nothing(self, curses_mock):
        """Row numbers are 1-based, so 0 must not wrap round to the last row"""
        view = build_view(curses_mock, num_rows=3)
        view.prompt_get_string = Mock(return_value="0")

        [selection, row, issue] = view.prompt_get_issue()

        assert issue is None

    def test_non_numeric_returns_nothing(self, curses_mock):
        view = build_view(curses_mock)
        view.prompt_get_string = Mock(return_value="abc")

        [selection, row, issue] = view.prompt_get_issue()

        assert selection == "abc"
        assert issue is None


class TestLiveFilterEditing:
    """Backspace must work whichever code the terminal sends: 8, 127 (macOS) or 263 (linux)"""

    def type_filter(self, view, keys):
        view.stdscr.getch.side_effect = keys
        getattr(view, "_CursesTableView__perform_live_filter")()

    @pytest.mark.parametrize("backspace", [8, 127, 263])
    def test_backspace_removes_last_character(self, curses_mock, backspace):
        view = build_view(curses_mock)
        # "TEST-12", backspace, then enter -> "TEST-1"
        self.type_filter(view, [ord(c) for c in "TEST-12"] + [backspace, 10])

        assert view.current_filter == "TEST-1"

    @pytest.mark.parametrize("backspace", [8, 127, 263])
    def test_backspace_on_empty_term_cancels_filter(self, curses_mock, backspace):
        view = build_view(curses_mock)
        view.current_filter = "old"
        self.type_filter(view, [backspace])

        assert view.current_filter is None

    def test_escape_cancels_filter(self, curses_mock):
        view = build_view(curses_mock)
        self.type_filter(view, [ord(c) for c in "TEST"] + [27])

        assert view.current_filter is None


class TestCursorRendering:
    def test_cursor_row_drawn_reversed(self, curses_mock):
        view = build_view(curses_mock, num_rows=3)
        move_cursor(view, 1)
        move_cursor(view, 1)  # cursor on row index 1
        view.stdscr.reset_mock()
        view.draw()

        # Cells are drawn in order, one addstr per cell plus a newline per row
        attrs = [call.args[1] for call in view.stdscr.addstr.call_args_list
                 if len(call.args) > 1 and isinstance(call.args[1], int)]
        reversed_attrs = [a for a in attrs if a & A_REVERSE]
        assert len(reversed_attrs) == len(view.header)

    def test_no_reverse_without_cursor(self, curses_mock):
        view = build_view(curses_mock, num_rows=3)
        view.stdscr.reset_mock()
        view.draw()

        attrs = [call.args[1] for call in view.stdscr.addstr.call_args_list
                 if len(call.args) > 1 and isinstance(call.args[1], int)]
        assert not any(a & A_REVERSE for a in attrs)


def build_tree_view(curses_mock, row_numbers=True):
    """
    Three top level rows: TEST-1, an epic EPIC-2 whose children are loaded on
    expand, and TEST-3 with two sub-tasks supplied up front
    """
    view = CursesTableView(Mock())
    view.header_color = 1
    view.set_column_colors([1, 2, 3])
    if row_numbers:
        view.enable_row_numbers()
    view.add_header(["Key", "Summary", "Status"])
    view.add_row(["TEST-1", "Plain", "Open"], "TEST-1")
    view.add_row(["EPIC-2", "Epic", "Open"], "EPIC-2", expandable=True)
    view.add_row(["TEST-3", "Story", "Done"], "TEST-3", [(["SUB-1", "Sub one", "Open"], "SUB-1"),
                                                          (["SUB-2", "Sub two", "Done"], "SUB-2")])
    loads = []
    def loader(data):
        loads.append(data)
        return [(["STORY-1", "Story one", "Open"], "STORY-1"),
                (["STORY-2", "Story two", "Open"], "STORY-2", [(["SUB-9", "Deep", "Open"], "SUB-9")], False)]
    view.set_child_loader(loader)
    view.loads = loads
    return view


def shown(view):
    return [(row.label, row.data) for row in view.get_rows()]


class TestExpandableRows:
    def test_children_hidden_until_expanded(self, curses_mock):
        view = build_tree_view(curses_mock)
        assert shown(view) == [("1", "TEST-1"), ("2", "EPIC-2"), ("3", "TEST-3")]

    def test_expanding_numbers_children_under_the_parent(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.expand_row(2)
        assert shown(view) == [("1", "TEST-1"), ("2", "EPIC-2"), ("3", "TEST-3"),
                               ("3.1", "SUB-1"), ("3.2", "SUB-2")]
        assert view.get_rows()[3].row[0] == "3.1"

    def test_top_level_numbers_do_not_move_when_a_row_above_expands(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.expand_row(1)
        assert ("3", "TEST-3") in shown(view)
        assert view.get_row_by_label("3")[1] == "TEST-3"

    def test_children_load_on_first_expand_only(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.expand_row(1)
        view.collapse_row(1)
        view.expand_row(1)
        assert view.loads == ["EPIC-2"]
        assert shown(view)[1:4] == [("2", "EPIC-2"), ("2.1", "STORY-1"), ("2.2", "STORY-2")]

    def test_loaded_children_can_nest(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.expand_row(1)
        view.expand_row(3)
        assert view.get_row_by_label("2.2.1")[1] == "SUB-9"

    def test_row_with_no_children_stops_being_expandable(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.set_child_loader(lambda data: [])
        assert view.expand_row(1) is False
        assert view.rows[1].expandable is False

    def test_loader_failure_is_reported_and_leaves_row_collapsed(self, curses_mock):
        view = build_tree_view(curses_mock)
        def broken(data):
            raise RuntimeError("down")
        view.set_child_loader(broken)
        view.error = Mock()
        assert view.expand_row(1) is False
        view.error.assert_called_once()
        assert view.rows[1].children_loaded is False

    def test_expand_defaults_to_cursor_row(self, curses_mock):
        view = build_tree_view(curses_mock)
        move_cursor(view, 1)
        move_cursor(view, 1)
        move_cursor(view, 1)
        assert view.expand_row() is True
        assert view.get_selected_row()[1] == "TEST-3"

    def test_collapsing_a_child_collapses_its_parent_and_moves_the_cursor(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.expand_row(2)
        view.cursor_index = 4  # SUB-2
        assert view.collapse_row() is True
        assert view.get_selected_row()[1] == "TEST-3"
        assert len(view.get_rows()) == 3

    def test_collapsing_a_top_level_leaf_does_nothing(self, curses_mock):
        view = build_tree_view(curses_mock)
        assert view.collapse_row(0) is False

    def test_typed_label_resolves_through_prompt(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.expand_row(2)
        view.prompt_get_string = Mock(return_value="3.2")
        assert view.prompt_get_issue()[2] == "SUB-2"

    def test_unknown_label_resolves_to_nothing(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.prompt_get_string = Mock(return_value="3.1")
        assert view.prompt_get_issue() == ["3.1", None, None]

    @pytest.mark.parametrize("text,expected", [("3", True), ("3.1", True), ("12.3.4", True),
                                               ("", False), ("3.", False), (".1", False), ("a", False)])
    def test_is_row_label(self, text, expected):
        assert CursesTableView.is_row_label(text) is expected


class TestExpandAll:
    def test_expand_all_then_collapse_all(self, curses_mock):
        view = build_tree_view(curses_mock)
        assert view.toggle_expand_all() is True
        assert [data for _, data in shown(view)] == ["TEST-1", "EPIC-2", "STORY-1", "STORY-2", "SUB-9",
                                                     "TEST-3", "SUB-1", "SUB-2"]
        assert view.toggle_expand_all() is False
        assert len(view.get_rows()) == 3

    def test_expand_all_uses_the_batch_loader(self, curses_mock):
        view = CursesTableView(Mock())
        view.header_color = 1
        view.add_header(["Key"])
        view.add_row(["EPIC-1"], "EPIC-1", expandable=True)
        view.add_row(["EPIC-2"], "EPIC-2", expandable=True)
        single, batch = Mock(), Mock(return_value=[[(["A"], "A")], []])
        view.set_child_loader(single, batch)
        view.toggle_expand_all()
        batch.assert_called_once_with(["EPIC-1", "EPIC-2"])
        single.assert_not_called()
        assert [data for _, data in shown(view)] == ["EPIC-1", "A", "EPIC-2"]
        assert view.rows[-1].expandable is False

    def test_expand_where_only_expands_matches(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.expand_where(lambda data: data == "TEST-3")
        assert view.loads == []
        assert len(view.get_rows()) == 5
        assert view.get_expansion_state() == [("EPIC-2", False), ("TEST-3", True)]


class TestTreeSortAndFilter:
    def test_sort_keeps_children_under_their_parent(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.toggle_expand_all()
        view.sort(3)  # Status, with the # column first
        order = [data for _, data in shown(view)]
        # TEST-3 is the only Done top level row; its Done sub-task now sorts above its Open one
        assert order[:3] == ["TEST-3", "SUB-2", "SUB-1"]
        assert order[order.index("EPIC-2") + 1:order.index("EPIC-2") + 4] == ["STORY-1", "STORY-2", "SUB-9"]

    def test_filter_keeps_the_parents_of_a_matching_child(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.toggle_expand_all()
        view.current_filter = "deep"
        assert shown(view) == [("1", "EPIC-2"), ("1.1", "STORY-2"), ("1.1.1", "SUB-9")]

    def test_filter_does_not_match_row_numbers(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.current_filter = "2"
        assert [data for _, data in shown(view)] == ["EPIC-2"]


class TestTreeDrawing:
    def drawn_text(self, view):
        view.stdscr.reset_mock()
        view.draw()
        return "".join(c.args[0] for c in view.stdscr.addstr.call_args_list if c.args)

    def test_markers_and_indent(self, curses_mock):
        view = build_tree_view(curses_mock)
        view.expand_row(2)
        text = self.drawn_text(view)
        assert "▸ EPIC-2" in text
        assert "▾ TEST-3" in text
        assert "    SUB-1" in text

    def test_flat_table_has_no_markers(self, curses_mock):
        view = build_view(curses_mock)
        text = self.drawn_text(view)
        assert "▸" not in text and "  TEST-1" not in text.split("TEST-1")[0][-3:]


KEY_RIGHT = 261
KEY_LEFT = 260
ENTER = 10


class TestExpandKeys:
    """Drives the real prompt loop with scripted keypresses, ending each script with enter"""
    def press(self, curses_mock, view, *keys):
        curses_mock.KEY_RIGHT = KEY_RIGHT
        curses_mock.KEY_LEFT = KEY_LEFT
        view.stdscr.getch.side_effect = list(keys) + [ENTER]
        return view.prompt_get_string("prompt >")

    def test_right_without_a_cursor_summons_it(self, curses_mock):
        view = build_tree_view(curses_mock)
        self.press(curses_mock, view, KEY_RIGHT)
        assert view.cursor_index == 0
        assert len(view.get_rows()) == 3

    def test_right_expands_and_left_collapses_the_cursor_row(self, curses_mock):
        view = build_tree_view(curses_mock)
        self.press(curses_mock, view, KEY_DOWN, KEY_DOWN, KEY_DOWN, KEY_RIGHT)
        assert view.get_row_by_label("3.2")[1] == "SUB-2"
        self.press(curses_mock, view, KEY_LEFT)
        assert len(view.get_rows()) == 3

    def test_plus_and_minus_work_while_a_row_is_selected(self, curses_mock):
        view = build_tree_view(curses_mock)
        answer = self.press(curses_mock, view, KEY_DOWN, KEY_DOWN, ord('+'))
        assert answer == ""
        assert view.get_row_by_label("2.1")[1] == "STORY-1"
        self.press(curses_mock, view, ord('-'))
        assert len(view.get_rows()) == 3

    def test_plus_is_typed_without_a_cursor(self, curses_mock):
        view = build_tree_view(curses_mock)
        assert self.press(curses_mock, view, ord('+')) == "+"

    def test_right_on_a_row_that_cannot_expand_beeps(self, curses_mock):
        view = build_tree_view(curses_mock)
        self.press(curses_mock, view, KEY_DOWN, KEY_RIGHT)
        curses_mock.beep.assert_called_once()

    def test_callable_prompt_is_redrawn_after_each_key(self, curses_mock):
        view = build_tree_view(curses_mock)
        prompt = Mock(return_value="prompt >")
        curses_mock.KEY_RIGHT = KEY_RIGHT
        curses_mock.KEY_LEFT = KEY_LEFT
        view.stdscr.getch.side_effect = [KEY_DOWN, KEY_DOWN, ENTER]
        view.prompt_get_string(prompt)
        assert prompt.call_count == 3
