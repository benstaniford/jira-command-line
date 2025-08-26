#scriptdoc: title="A wrapper designed to make curses programs based on a table", tags="library,curses"

# pip install windows-curses
# docs: https://docs.python.org/3/howto/curses.html
import curses

class KeyCode:
    ESCAPE = 27
    ENTER = 10
    BACKSPACE = 8
    PRINTABLE_START = 32
    PRINTABLE_END = 126

class RowContainer:
    """
    Initializes a RowContainer object, which is used to store the row number, data, and parent RowContainer object for a given row.

    Args:
        row (list): The list of strings that make up a row
        data (Any, optional): The data associated with the row. Defaults to None.
        child_of (RowContainer, optional): The parent RowContainer object. Defaults to None.
    """
    def __init__(self, row, data=None, row_index=None, child_of=None):
        self.row = row
        self.data = data
        self.child_of = child_of
        # The original order of either the row, or the subrow in the row
        self.row_index = row_index

    def is_subrow(self):
        """
        Returns True if the row is a subrow, False otherwise.
        """
        return self.child_of is not None

class CursesTableView:
    def __init__(self, stdscr):
        self.column_colors = []
        self.current_filter = None
        self.current_search = None
        self.current_page = 1
        self.header = []
        self.header_color = None
        self.help_text_color = None
        self.max_column_width = 80
        self.padding = 2
        self.prompt_max = 5
        self.row_numbers = False
        self.rows = []
        self.row_offset = 0
        self.stdscr = stdscr
        self.subrows_enabled = False

    def set_column_colors(self, colors):
        """
        Sets the colors for the columns.

        Parameters: colors (list): A list of colors to be assigned to the columns.

        Returns: None
        """
        self.column_colors = colors

    def set_help_text_color(self, color):
        """
        Sets the color for the help text.

        Parameters: color (str): The color to be assigned to the help text.

        Returns: None
        """
        self.help_text_color = color

    def set_header_color(self, color):
        """
        Sets the color for the header.

        Parameters: color (str): The color to be assigned to the header.

        Returns: None
        """
        self.header_color = color

    def enable_row_numbers(self):
        """
        Enable row numbers for the table.

        This method adds a row number column to the table by inserting "#" at the beginning of the header
        and inserting the row numbers at the beginning of each row.

        Args: None

        Returns: None
        """
        if not self.row_numbers:
            self.row_numbers = True
            self.header.insert(0, "#")
            if self.subrows_enabled:
                for row_index, row_container in enumerate(self.rows):
                    row_container.row.insert(0, str(row_index + 1))
            else:
                for row_index, row_container in enumerate(self.__get_parent_rows()):
                    row_container.row.insert(0, str(row_index + 1))
                for row_index, row_container in enumerate(self.__get_subrows()):
                    row_container.row.insert(0, "")

    def toggle_subrows(self):
        """
        Toggle subrows for the table.

        This method toggles whether or not subrows are shown for the table. 

        Args: None

        Returns: None
        """
        self.subrows_enabled = not self.subrows_enabled
        if self.row_numbers:
            if self.subrows_enabled:
                for row_index, row_container in enumerate(self.rows):
                    row_container.row[0] = str(row_index + 1)
            else:
                for row_index, row_container in enumerate(self.__get_parent_rows()):
                    row_container.row[0] = str(row_index + 1)
                for row_index, row_container in enumerate(self.__get_subrows()):
                    row_container.row[0] = ""

    def disable_row_numbers(self):
        """
        Disable row numbers for the table.

        This method removes the row number column from the table by removing "#" from the header
        and removing the row numbers from each row.

        Args: None

        Returns: None
        """
        if self.row_numbers:
            self.row_numbers = False
            self.header.pop(0)
            for row_container in self.rows:
                row_container.row.pop(0)

    def add_header(self, header):
        """
        Add a header to the existing header.

        Parameters: header (str): The header to be added.

        Returns: None
        """
        self.header += header

    def add_row(self, row, data=None, subrows=None, row_index=None, parent_row=None):
        """
        Adds a row to the table, and optionally associates data with it, the data will remain associated even if the row is sorted.
        The table also has a concept of optional subrows, which are rows that are associated with another row, and are hidden until the parent row is expanded.

        Parameters:
        row (list): The row to be added to the table
        data (Any, optional): Data to be associated with the row (default is None)
        subrows (list, optional): List of tuples, (subrow, data) to be associated with the row (default is None).
        parent_row (list, optional): The row that the subrows are associated with (default is None).

        Raises: None

        Returns: None 
        """
        row_container = RowContainer(row, data, row_index if row_index else len(self.rows), parent_row)
        if (self.row_numbers):
            if (self.subrows_enabled):
                row_container.row.insert(0, str(len(self.rows) + 1))
            else:
                # Only increment the row number if the row is not a subrow
                if (parent_row is None):
                    row_container.row.insert(0, str(len(self.__get_parent_rows()) + 1))
                else:
                    row_container.row.insert(0, "") 

        self.rows.append(row_container)
        for subrow_index, (subrow, subrow_data) in enumerate(subrows or []):
            self.add_row(subrow, subrow_data, None, row_index, row_container)

    def get_row(self, row_index):
        """
        Return the row and its corresponding data for the given row index.

        Parameters:
        - row_index (int): The index of the row to retrieve.

        Returns:
        - row (list): The row at the given index.
        - data (any): The corresponding data for the row.
        """
        row_container = self.__get_active_rows()[row_index]
        return row_container.row, row_container.data

    def get_rows(self):
        """
        Returns the active rows in the view

        Parameters: None

        Returns: list of rows
        """
        return self.__get_active_rows()

    def clear(self):
        """
        Clears the data in the table including the headers.

        Args: None

        Returns: None
        """
        self.header = []
        if (self.row_numbers):
            self.header.insert(0, "#")
        self.rows = []
        self.current_page = 1
        self.current_filter = None
        self.current_search = None
        if (self.row_numbers):
            self.enable_row_numbers()

    def yield_screen(self):
        """
        Clears the screen and yields to other terminal input/output
        Args: None
        Returns: None
        """
        self.stdscr.clear()
        self.stdscr.refresh()
        curses.update_lines_cols()
        curses.endwin()

    def restore_screen(self):
        """
        Restores the screen after yielding to other terminal input/output
        Args: None
        Returns: None
        """
        curses.initscr()
        self.stdscr.clear()
        self.stdscr.refresh()
        curses.update_lines_cols()
        self.draw()

    def clear_prompt(self):
        """
        Clears the prompt at the bottom of the screen.

        This method attempts to move the cursor to the last line of the screen
        and clears everything below it.  If an exception is raised by the
        curses "addstr" method, this can safely be ignored as it is likely due
        to the screen being resized.

        Parameters:
        - self: the current instance of the class

        Returns: None
        """
        try:
            self.stdscr.move(curses.LINES - self.prompt_max, 0)
        except Exception as e:
            if "addstr" in e.args[0]:
                return
        self.stdscr.clrtobot()
        self.stdscr.refresh()

    def prompt(self, prompt_text, prompt_suffix = " >", color=None):
        """
        Sets the prompt and displays it on the screen.

        Parameters:
        - prompt_text (str): The text to be displayed in the prompt.
        - prompt_suffix (str, optional): The suffix to be added to the prompt text. Default is " >".
        - color (int, optional): The color code for the prompt text. Default is None.

        Returns: None

        Raises: Exception: If there are too many lines in the prompt.
        """
        curses.update_lines_cols()
        self.clear_prompt()
        lines = prompt_text.split("\n")
        num_lines = len(lines)
        if (num_lines > self.prompt_max):
            raise Exception("Too many lines in prompt")
        try:
            color = (color + 1) if color != None else curses.A_NORMAL
            color_pair = curses.color_pair(color)
            self.stdscr.addstr(curses.LINES - num_lines, 0, f"{prompt_text}{prompt_suffix}", color_pair | curses.A_BOLD)
        except Exception as e:
            if "addstr" in e.args[0]:
                return
        self.stdscr.refresh()
    
    def prompt_with_colored_help(self, prompt, prompt_suffix=" >"):
        """
        Display a prompt with colored help text lines.
        
        Parameters:
        - prompt (str|list): All lines in the prompt. If str, treated as simple text prompt.
                            If list, can contain:
                            - Strings for simple text lines
                            - Lists of (text, is_highlighted) tuples for colored lines
                            The last item should be a string for the input prompt line
        - prompt_suffix (str, optional): The suffix to be added to the prompt text. Default is " >".
        """
        curses.update_lines_cols()
        self.clear_prompt()
        
        # Convert prompt to consistent list format
        if isinstance(prompt, str):
            # Simple string prompt
            lines = prompt.split("\n")
            prompt_lines = lines[:-1]  # All but last line are help text
            last_line = lines[-1] if lines else ""
        else:
            # List format - last item is the prompt line, rest are help lines
            prompt_lines = prompt[:-1] if len(prompt) > 1 else []
            last_line = prompt[-1] if prompt else ""
        
        total_lines = len(prompt_lines) + 1  # help lines + last line
        if total_lines > self.prompt_max:
            raise Exception("Too many lines in prompt")
        
        try:
            current_line = curses.LINES - total_lines
            
            # Display help lines
            for i, line in enumerate(prompt_lines):
                # First line has no indentation, subsequent lines get 2-space indent  
                indent = 0 if i == 0 else 2
                if indent > 0:
                    self.stdscr.addstr(current_line, 0, "  ", curses.A_NORMAL)
                
                col_pos = indent
                
                if isinstance(line, str):
                    # Simple string line
                    self.stdscr.addstr(current_line, col_pos, line, curses.A_NORMAL)
                else:
                    # Colored line - list of (text, is_highlighted) tuples
                    for text, is_highlighted in line:
                        help_color = self.help_text_color if self.help_text_color is not None else self.header_color
                        color_attr = curses.color_pair(help_color + 1) | curses.A_BOLD if is_highlighted else curses.A_NORMAL
                        self.stdscr.addstr(current_line, col_pos, text, color_attr)
                        col_pos += len(text)
                current_line += 1
            
            # Display last line with suffix (normal color)
            self.stdscr.addstr(current_line, 0, f"{last_line}{prompt_suffix}", curses.A_NORMAL | curses.A_BOLD)
            
        except Exception as e:
            if "addstr" in str(e):
                return
        
        self.stdscr.refresh()

    def error(self, msg, exception = None):
        """
        Show a red error prompt, and offer to view the exception

        Parameters:
        - msg (str): The error message to display
        - exception (Exception): The exception object (optional)

        Returns: None
        """
        exception_first_line = str(exception).split("\n")[0] if exception != None else ""
        exception_first_line = exception_first_line[:self.max_column_width] if len(exception_first_line) > self.max_column_width else exception_first_line
        prompt_text = f"Error: {exception_first_line}\nMsg: {msg}\nPress v to view the exception..." if exception != None else f"Error: {msg}\nPress any key to continue..."

        curses.init_pair(curses.COLOR_RED + 1, curses.COLOR_RED, curses.COLOR_BLACK)   # Just in case
        self.prompt(prompt_text, "", color=curses.COLOR_RED)
        if self.stdscr.getch() == ord('v') and exception != None:
            import tempfile, traceback, os
            self.prompt("", "")
            with tempfile.NamedTemporaryFile(mode='w+t', suffix=".txt") as f:
                f.write(f"Error: {exception}\nMsg: {msg}\n\n")
                traceback.print_exc(file=f)
                f.flush()
                os.system("less " + f.name)

    def prompt_with_choice_dictionary(self, prompt_text, dictionary):
        """
        Displays a prompt with shortcuts for each choice in the dictionary, returns the value of the choice selected

        Args:
            prompt_text (str): The text to display as the prompt
            dictionary (dict): The dictionary containing the choices

        Returns: The value of the choice selected from the dictionary
        """
        choice_text = " ".join(f"{key}:{value}" for key, value in dictionary.items())
        
        if len(choice_text) > self.max_column_width:
            split_index = choice_text.partition(' ')[2]
            choice_text = choice_text[:split_index] + "\n" + choice_text[split_index:]
            
        prompt_text = choice_text + "\n" + prompt_text
        selection = self.prompt_get_character(prompt_text) if len(dictionary) < 10 else self.prompt_get_string(prompt_text)
        
        return dictionary.get(selection)

    def prompt_with_choice_list(self, prompt_text, choices, non_numeric_keypresses=False):
        """
        Displays a prompt with numbered shortcuts for each choice in the list, returns the choice selected and its index

        Parameters:
        - prompt_text (str): The text to be displayed as the prompt
        - choices (list): The list of choices
        - non_numeric_keypresses (bool): If True, the first and last letter of each choice will be used as a shortcut if possible

        Returns:
        - tuple: (index, selected_choice) if found, otherwise (None, "")
        """
        choice_text = ""

        if non_numeric_keypresses:
            key_presses_to_names = self.__get_keypresses_from_names(choices)
            names_to_key_presses = {v: k for k, v in key_presses_to_names.items()}
            for choice in choices:
                choice_text += f"{names_to_key_presses[str(choice)]}:{str(choice)} "
        else:
            for i, choice in enumerate(choices):
                choice_text += f"{i+1}:{choice} "
            choice_text = choice_text[:-1]
        
        if len(choice_text) > self.max_column_width:
            # Split towards the middle of the string on a space
            split_index = len(choice_text) // 2
            while choice_text[split_index] != ' ': split_index += 1
            choice_text = choice_text[:split_index] + "\n" + choice_text[split_index:]

        prompt_text = choice_text + "\n" + prompt_text
        selection = self.prompt_get_character(prompt_text) if (len(choices) < 10 or non_numeric_keypresses) else self.prompt_get_string(prompt_text)
        if non_numeric_keypresses:
            if selection in key_presses_to_names:
                return (selection, key_presses_to_names[selection])
        else:
            if selection.isdigit():
                index = int(selection) - 1
                if index < len(choices):
                    return (index, choices[index])
        return (None, "")

    def prompt_get_character(self, prompt_text):
        """
        Displays a prompt and returns the first keypress.  Will resize the terminal and
        redraw the prompt if necessary and will return an empty string if the escape key is pressed.

        Args:
            prompt_text (str): The text to display as the prompt.

        Returns: str: The character that was pressed.
        """
        while True:
            self.prompt(prompt_text)
            typed_character = self.stdscr.getch()
            if typed_character == curses.KEY_RESIZE:
                self.draw()
            elif typed_character == KeyCode.ESCAPE:
                return ''
            else:
                return chr(typed_character)

    def prompt_get_string(self, prompt, keypresses=None, filter_key=None, sort_keys=None, search_key=None):
        """
        Displays a prompt with unified colored help text and returns the string entered by the user, or the first keypress in keypresses.
        
        Args:
            prompt (str|list): All lines in the prompt. If str, treated as simple text prompt.
                              If list, can contain:
                              - Strings for simple text lines
                              - Lists of (text, is_highlighted) tuples for colored lines
                              The last item should be a string for the input prompt line
            keypresses (str, optional): A string of characters to match against keypresses. Defaults to None.
            filter_key (str, optional): A character that triggers a live filter on the table. Defaults to None.
            sort_keys (list(str), optional): A list of two characters that triggers a sort on the table (back/forwards). Defaults to None.
            search_key (str, optional): A character that triggers a search on the table. Defaults to None.

        Returns:
            str: The string entered by the user or the first matching keypress, or an empty string if escape was pressed
        """
        # Convert prompt to consistent format and extract last line
        if isinstance(prompt, str):
            lines = prompt.split("\n")
            all_colored_lines = lines[:-1] if len(lines) > 1 else []
            last_line = lines[-1] if lines else ""
        else:
            all_colored_lines = prompt[:-1] if len(prompt) > 1 else []
            last_line = prompt[-1] if prompt else ""
        
        while True:
            self.prompt_with_colored_help(prompt)
            # Count total lines for positioning
            total_lines = len(all_colored_lines) + 1
            ord_keypresses = [ord(keypress) for keypress in keypresses] if keypresses is not None else ()
            prompt_with_padding = len(last_line) + 3
            last_line_pos = curses.LINES - 1
            answer = ""
            while True:
                typed_char = self.stdscr.getch()
                if typed_char == KeyCode.ENTER:
                    return answer
                if typed_char == KeyCode.ESCAPE:
                    return ""
                elif typed_char == KeyCode.BACKSPACE and len(answer) > 0:
                    answer = answer[:-1]
                    self.stdscr.move(last_line_pos, prompt_with_padding)
                    self.stdscr.clrtoeol()
                    self.stdscr.addstr(last_line_pos, prompt_with_padding, answer)
                    self.stdscr.refresh()
                elif typed_char in ord_keypresses:
                    return chr(typed_char)
                elif typed_char in (curses.KEY_F1, curses.KEY_F2, curses.KEY_F3, curses.KEY_F4, curses.KEY_F5, curses.KEY_F6,
                                    curses.KEY_F7, curses.KEY_F8, curses.KEY_F9, curses.KEY_F10, curses.KEY_F11, curses.KEY_F12):
                    return f"KEY_F{str(typed_char - curses.KEY_F0)}"
                elif chr(typed_char) == filter_key:
                    self.__perform_live_filter()
                    answer = ""
                    break
                elif sort_keys and typed_char in [ord(key) for key in sort_keys]:
                    return chr(typed_char)
                elif chr(typed_char) == search_key:
                    self.__perform_live_search()
                    answer = ""
                    break
                elif typed_char == curses.KEY_RESIZE:
                    break  # Will redraw the prompt
                elif typed_char == curses.KEY_NPAGE:
                    self.__move_page(1)
                    break
                elif typed_char == curses.KEY_PPAGE:
                    self.__move_page(-1)
                    break
                elif typed_char == curses.KEY_DOWN:
                    self.row_offset += 1 if self.row_offset < len(self.__get_active_rows()) - 1 else 0
                    self.draw()
                    break
                elif typed_char == curses.KEY_UP:
                    self.row_offset -= 1 if self.row_offset > 0 else 0
                    self.draw()
                    break
                elif chr(typed_char).isprintable():
                    answer += chr(typed_char)
                    self.stdscr.addstr(last_line_pos, prompt_with_padding + len(answer) - 1, chr(typed_char))
                    continue

    def sort(self, column_index, reverse=False):
        """
        Sorts the table by the column the user selects, and redraws the window.
        subrows should be sorted beneath their parent rows.  If the column is not numeric,
        it will be sorted alphabetically.

        Args:
            column_index (int): The index of the column to sort by.
            reverse (bool, optional): Whether to reverse the sort order. Defaults to False.

        Returns: None

        Raises: None
        """
        for row_container in self.rows:
            try:
                self.__get_column_as_numeric(row_container.row, column_index)
            except Exception as e:
                return self.__sort_alpha(column_index, reverse)
        try:
            def FnNumericColumnSortPreserveSubrows(row_container):
                if (row_container.is_subrow()):
                    parent_row = row_container.child_of
                    parent_number_val = self.__get_column_as_numeric(parent_row.row, column_index)
                    return (parent_number_val, parent_row.row_index, row_container.row_index + 1)
                return (self.__get_column_as_numeric(row_container.row, column_index), row_container.row_index, 0)
            self.rows.sort(key=FnNumericColumnSortPreserveSubrows, reverse=reverse)
        except Exception as e:
            return
        self.draw()

    def close(self):
        """ Close the curses window and clean up resources.  """
        curses.endwin()

    def draw(self):
        """
            Draws the content on the screen.
            
            This method clears the screen, calculates the number of rows per page, 
            initializes the color pairs, calculates the lengths of each column, 
            draws the header, draws the rows, and refreshes the screen.
            
            Raises:
                Exception: If an error occurs during the drawing process.
            """
        if (self.row_numbers):
            self.__renumber_active_rows()
        self.stdscr.clear()
        rows_per_page = self.__calc_rows_per_page()
        self.__initialize_color_pairs()
        column_lengths = self.__calculate_column_lengths()
        try:
            self.__draw_header(column_lengths)
            self.stdscr.addstr("\n\n")
            self.__draw_rows(column_lengths, rows_per_page)
        except Exception as e:
            if "addstr" in e.args[0]:
                return
        self.stdscr.refresh()

    def __draw_header(self, column_lengths):
        if self.header_color:
            for col_index, header_text in enumerate(self.header):
                str_justified = f"{header_text}".ljust(column_lengths[col_index] + self.padding)
                self.stdscr.addstr(str_justified, curses.color_pair(self.header_color + 1))

    def __draw_rows(self, column_lengths, rows_per_page):
        for row_index, row_container in enumerate(self.__get_active_rows()):
            combined_row_text = " ".join(row_container.row)
            highlight_search = True if self.current_search and self.current_search.lower() in combined_row_text.lower() else False

            __is_subrow = row_container.is_subrow()
            if row_index < (self.current_page - 1) * rows_per_page:
                continue
            if row_index >= self.current_page * rows_per_page:
                break
            for col_index, col_text in enumerate(row_container.row):
                txt = self.__apply_max_col_width(col_text)
                str_justified = f"{txt}".ljust(column_lengths[col_index] + self.padding)

                if __is_subrow:
                    self.stdscr.addstr(str_justified, curses.color_pair(curses.COLOR_WHITE + 1))
                elif highlight_search:
                    self.stdscr.addstr(str_justified, curses.color_pair(self.highlight_index + 1))
                elif col_index + 1 <= len(self.column_colors):
                    self.stdscr.addstr(str_justified, curses.color_pair(self.column_colors[col_index] + 1))
                else:
                    self.stdscr.addstr(str_justified)
            self.stdscr.addstr("\n")

    def __initialize_color_pairs(self):
        curses.start_color()
        curses.init_pair(curses.COLOR_WHITE + 1, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(self.header_color + 1, self.header_color, curses.COLOR_BLACK)
        if self.help_text_color is not None:
            curses.init_pair(self.help_text_color + 1, self.help_text_color, curses.COLOR_BLACK)
        for color in self.column_colors:
            curses.init_pair(color + 1, color, curses.COLOR_BLACK)
        self.highlight_index = len(self.column_colors)
        curses.init_pair(self.highlight_index + 1, curses.COLOR_BLACK, curses.COLOR_WHITE)

    def __calculate_column_lengths(self):
        column_lengths = ()
        for col_index, cell_text in enumerate(self.header):
            if col_index >= len(column_lengths):
                column_lengths += (0,)
            column_lengths = column_lengths[:col_index] + (max(column_lengths[col_index], len(cell_text)),) + column_lengths[col_index+1:]
        for row_container in self.rows:
            for col_index, col_text in enumerate(row_container.row):
                if col_index >= len(column_lengths):
                    column_lengths += (0,)
                txt = self.__apply_max_col_width(col_text)
                column_lengths = column_lengths[:col_index] + (max(column_lengths[col_index], len(txt)),) + column_lengths[col_index+1:]
        return column_lengths

    def __calc_rows_per_page(self):
        curses.update_lines_cols()
        rows_per_page = curses.LINES - self.prompt_max - 1
        if (self.row_numbers):
            rows_per_page -= 1
        return rows_per_page

    def __apply_max_col_width(self, cell):
        if len(cell) > self.max_column_width:
            return cell[:self.max_column_width - 3] + "..."
        return cell

    def __perform_live_filter(self):
        search_term = ""
        while True:
            self.prompt("filter: " + search_term, "")
            typed_character = self.stdscr.getch()
            if typed_character == KeyCode.ESCAPE:
                self.current_filter = None
                self.draw()
                return
            elif typed_character == KeyCode.ENTER:
                self.current_filter = search_term if (len(search_term.strip()) > 0) else None
                self.draw()
                return
            elif typed_character == KeyCode.BACKSPACE:
                if len(search_term) == 0:
                    self.current_filter = None
                    self.draw()
                    return
                search_term = search_term[:-1]
            elif typed_character == curses.KEY_RESIZE:
                pass
            elif typed_character < KeyCode.PRINTABLE_START or typed_character > KeyCode.PRINTABLE_END:
                continue
            else:
                search_term += chr(typed_character)

            self.current_filter = search_term if (len(search_term.strip()) > 0) else None
            self.draw()

    def __perform_live_search(self):
        search_term = ""
        while True:
            self.prompt("filter: " + search_term, "")
            typed_character = self.stdscr.getch()
            if typed_character == KeyCode.ESCAPE:
                self.current_search = None
                self.draw()
                return
            elif typed_character == KeyCode.ENTER:
                self.current_search = search_term if (len(search_term.strip()) > 0) else None
                self.draw()
                return
            elif typed_character == KeyCode.BACKSPACE:
                if len(search_term) == 0:
                    self.current_search = None
                    self.draw()
                    return
                search_term = search_term[:-1]
            elif typed_character == curses.KEY_RESIZE:
                pass
            elif typed_character < KeyCode.PRINTABLE_START or typed_character > KeyCode.PRINTABLE_END:
                continue
            else:
                search_term += chr(typed_character)

            self.current_search = search_term if (len(search_term.strip()) > 0) else None
            self.draw()

    def __perform_column_sort(self, reverse=False):
        [i, item] = self.prompt_with_choice_list("Sort by:", self.header[1:]) if (self.row_numbers) else self.prompt_with_choice_list("Sort by:", self.header)
        if i != None:
            self.sort(i + 1, reverse)

    def __get_column_safe(self, row, column_index):
        try:
            return row[column_index]
        except IndexError:
            return ""

    def __get_column_as_numeric(self, row, column_index):
        value = self.__get_column_safe(row, column_index)
        value = value if value not in ("", None) else 0
        return float(value)

    def __sort_alpha(self, column_index, reverse=False):
        def FnColumnSortPreserveSubrows(row_container):
            if (row_container.is_subrow()):
                parent_row = row_container.child_of
                return (parent_row.row[column_index], parent_row.row_index, row_container.row_index + 1)
            return (row_container.row[column_index], row_container.row_index, 0)
        self.rows.sort(key=FnColumnSortPreserveSubrows, reverse=reverse)
        self.draw()

    def __renumber_active_rows(self):
        for row_index, row_container in enumerate(self.__get_active_rows()):
            row_container.row[0] = str(row_index + 1)

    def __move_page(self, increment):
        # Work out how many rows/pages we have
        rows_per_page = self.__calc_rows_per_page()
        num_rows_total = len(self.__get_active_rows())
        total_pages = num_rows_total // rows_per_page
        if (num_rows_total % rows_per_page > 0):
            total_pages += 1

        # Increment current page if we can
        if (self.current_page > 1 and increment < 0):
            self.current_page += increment
        elif (self.current_page < total_pages and increment > 0):
            self.current_page += increment 

        # Always redraw to ensure table is visible
        self.draw()

    def __get_keypresses_from_names(self, list_names):
        key_presses_to_names = {}
        for entry in list_names:
            name = str(entry)
            possible_keypresses = [name[0].lower(), name[0].upper(), name[-1].lower(), name[-1].upper()]
            for keypress in possible_keypresses:
                if keypress not in key_presses_to_names:
                    key_presses_to_names[keypress] = name
                    break
                if keypress == possible_keypresses[-1]:
                    # If we get here, we have a collision, so we need to add a number to the keypress
                    for i in range(1, 10):
                        keypress_with_number = keypress + str(i)
                        if keypress_with_number not in key_presses_to_names:
                            key_presses_to_names[keypress_with_number] = name
                            break
        return key_presses_to_names

    def __get_active_rows(self):
        """Returns a list of rows that are active, i.e. potentially not subrows or rows that are filtered out"""
        rows = self.rows if self.subrows_enabled else self.__get_parent_rows()
        if (self.current_filter == None):
            return rows
        filtered_rows = []
        row_index = 0
        for row_container in rows:
            combined_row_text = " ".join(row_container.row)
            if (self.current_filter.lower() in combined_row_text.lower()):
                row_index += 1
                if (self.row_numbers):
                    row_container.row[0] = str(row_index)
                filtered_rows.append(row_container)
        return filtered_rows

    def __get_parent_rows(self):
        """Returns a list of rows that are not subrows"""
        return [row_container for row_container in self.rows if not row_container.is_subrow()]

    def __get_subrows(self):
        return [row_container for row_container in self.rows if row_container.is_subrow()]
            
