import sv_ttk
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import threading

class TkTableUi:
    def __init__(self, title):
        self.headers = ()
        self.data = []    # List of tuples, last item is an caller provided object to be used in the callbacks
        self.callback_objects = {}
        self.root = None
        self.tree = None
        self.title = title
        self.root = tk.Tk()
        style = ttk.Style()
        sv_ttk.set_theme("dark")
        self.root.title(self.title)
        self.root.geometry("1024x500")
        self.rightclick_menu = None
        
        self.disable_list = []
        self.disable_list_state = False

    def set_icon(self, icon_path):
        self.icon_path = icon_path
        try:
            self.root.iconbitmap(icon_path)
        except:
            pass # Probably not running on Windows

    def add_headers(self, headers):
        self.headers = headers

    def add_row(self, row, obj=None):
        self.data.append(row)
        self.callback_objects[row[0]] = obj  # First column is the key

    def clear(self):
        self.data.clear()

    def set_window_title(self, title):
        self.root.title(title)

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for header in self.headers:
            self.tree.heading(header, text=header, anchor=tk.W, command=lambda: self.sort_column(header, False))
        for row in self.data:
            self.tree.insert("", tk.END, values=row)

    def show_determinate_progress(self, message, max_value):
        self.set_state_disable_list(True)
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=200, mode="determinate", maximum=max_value)
        self.progress.pack(side=tk.LEFT, padx=5, pady=5)

    def show_indeterminate_progress(self):
        self.set_state_disable_list(True)
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=200, mode="indeterminate")
        self.progress.pack(side=tk.LEFT, padx=5, pady=5)
        self.progress.start()

    def update_progress(self, message = None):
        self.progress.step(1)

    def hide_progress_bar(self):
        self.progress.stop()
        self.progress.pack_forget()
        self.set_state_disable_list(False)

    def add_dropdown(self, items, selected_item, selected_callback):
        self.selected_team = tk.StringVar()
        self.selected_team.set(selected_item)
        dropdown = ttk.Combobox(self.root, textvariable=self.selected_team, values=items)
        dropdown.pack(side=tk.LEFT, padx=5, pady=5)
        dropdown.bind("<<ComboboxSelected>>", lambda event: selected_callback(self.selected_team.get()))
        self.disable_list.append(dropdown)
        return dropdown

    def do_task_with_progress(self, task):
        return_obj = None
        self.show_indeterminate_progress()
        thread_exception = None
        def inner_task():
            try:
                nonlocal return_obj
                return_obj = task()
            except Exception as e:
                nonlocal thread_exception
                thread_exception = e
        thread = threading.Thread(target=inner_task)
        thread.start()
        while thread.is_alive():
            self.root.update_idletasks()
            self.root.update()
        self.hide_progress_bar()
        if thread_exception:
            raise thread_exception
        return return_obj
            
    def close(self):
        self.root.destroy()

    def get_selected_item(self):
        try:
            item = self.tree.selection()[0]
            callback_object = self.callback_objects[self.tree.item(item, "values")[0]]
            return callback_object
        except:
            return None

    def sort_column(self, col, reverse):
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]
        data.sort(reverse=reverse)

        for index, (val, child) in enumerate(data):
            self.tree.move(child, '', index)

        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))

    def add_scrollbar(self):
        vscrollbar = ttk.Scrollbar(self.tree, orient="vertical", command=self.tree.yview)
        vscrollbar.pack(side="right", fill="y")
        hscrollbar = ttk.Scrollbar(self.tree, orient="horizontal", command=self.tree.xview)
        hscrollbar.pack(side="bottom", fill="x")
        self.tree.configure(yscrollcommand=vscrollbar.set, xscrollcommand=hscrollbar.set)

    def build_callback_labmda(self, callback):
        return lambda: callback(self.get_selected_item())

    def add_right_click_menu(self, callback_list, on_right_click_callback = None):
        self.rightclick_menu = tk.Menu(self.root, tearoff=0)
        for callback in callback_list:
            self.rightclick_menu.add_command(label=callback[0], command=self.build_callback_labmda(callback[1]))

        def popup(event):
            if self.disable_list_state:
                return
            if self.tree.identify_region(event.x, event.y) == "cell":
                if on_right_click_callback:
                    on_right_click_callback(self.get_selected_item())
                self.rightclick_menu.post(event.x_root, event.y_root)

        self.tree.bind("<Button-3>", popup)

    def set_rightclick_item_enabled_by_name(self, item_name, enabled):
        for index in range(len(self.rightclick_menu._tclCommands)):
            if self.rightclick_menu.entrycget(index, "label") == item_name:
                self.rightclick_menu.entryconfig(index, state="normal" if enabled else "disabled")

    def show_yesno_dialog(self, title, message):
        return messagebox.askyesno(title, message)

    def show_error_dialog(self, title, message):
        messagebox.showerror(title, message)

    def show_info_dialog(self, title, message):
        messagebox.showinfo(title, message)

    def show_warning_dialog(self, title, message):
        messagebox.showwarning(title, message)

    def show_text_dialog(self, title, message):
        """ A dialog to show text in monospace font with a scrollbar and a close button """
        top = tk.Toplevel()
        top.title(title)
        if hasattr(self, 'icon_path'):
            try:
                top.iconbitmap(self.icon_path)
            except:
                pass # Probably not running on Windows
        text = tk.Text(top, wrap=tk.WORD, font=("Courier", 10))
        scrollbar = ttk.Scrollbar(top, orient=tk.VERTICAL, command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=scrollbar.set)
        text.pack(expand=True, fill=tk.BOTH)
        text.insert(tk.END, message)
        button = ttk.Button(top, text="Close", command=top.destroy)
        button.pack(side=tk.BOTTOM)

    def add_button(self, label, right, callback):
        button = ttk.Button(self.root, text=label, command=callback)
        if (right):
            button.pack(side=tk.RIGHT, padx=5, pady=5)
        else:
            button.pack(side=tk.LEFT, padx=5, pady=5)
        self.disable_list.append(button)
        return button

    def set_column_widths(self, widths):
        for index, width in enumerate(widths):
            self.tree.column(self.headers[index], width=width, minwidth=width, stretch=tk.NO)

    def display(self, init_callback):
        self.tree = ttk.Treeview(self.root, columns=self.headers, show="headings", selectmode="browse")
        self.tree.pack(expand=True, fill=tk.BOTH)
        self.disable_list.append(self.tree)
        self.add_scrollbar()
        self.refresh()
        init_callback()

        # Start the UI loop
        self.root.mainloop()
    
    def set_state_disable_list(self, disable = True):
        self.disable_list_state = disable
        if disable:
            action = "disabled"
            tree_action = "none"
        else:
            action = "normal"
            tree_action = "browse"
        for widget in self.disable_list:
            if isinstance(widget, ttk.Treeview):
                widget.config(selectmode=tree_action)
            else:
                widget.config(state=action)
