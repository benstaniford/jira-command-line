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
