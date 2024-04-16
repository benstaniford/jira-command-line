import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

class TkTableUi:
    def __init__(self, title):
        self.headers = ()
        self.data = []    # List of tuples, last item is an caller provided object to be used in the callbacks
        self.callback_objects = {}
        self.root = None
        self.tree = None
        self.title = title
        self.root = tk.Tk()
        self.root.title(self.title)
        self.root.geometry("1024x768")
        self.rightclick_menu = None

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

    def show_progress_bar(self, message, max_value):
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=200, mode="determinate", maximum=max_value)
        self.progress.pack(side=tk.LEFT, padx=5, pady=5)

    def update_progress(self, message = None):
        self.progress.step(1)

    def hide_progress_bar(self):
        self.progress.pack_forget()
            
    def close(self):
        self.root.destroy()

    def get_selected_item(self):
        item = self.tree.selection()[0]
        callback_object = self.callback_objects[self.tree.item(item, "values")[0]]
        return callback_object

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

    def show_dialog(self, window_title, message):
        dialog_window = tk.Toplevel()
        dialog_window.title(window_title)
        label = ttk.Label(dialog_window, text=message)
        label.pack(padx=10, pady=10)
        close_button = ttk.Button(dialog_window, text="Close", command=dialog_window.destroy)
        close_button.pack(pady=5)
        width = self.root.winfo_width() / 2 - dialog_window.winfo_reqwidth() / 2
        height = self.root.winfo_height() / 2 - dialog_window.winfo_reqheight() / 2
        dialog_window.geometry("+%d+%d" % (self.root.winfo_x() + width, self.root.winfo_y() + height))

    def add_button(self, label, right, callback):
        button = ttk.Button(self.root, text=label, command=callback)
        if (right):
            button.pack(side=tk.RIGHT, padx=5, pady=5)
        else:
            button.pack(side=tk.LEFT, padx=5, pady=5)
        return button

    def display(self, init_callback):
        self.tree = ttk.Treeview(self.root, columns=self.headers, show="headings")
        self.tree.pack(expand=True, fill=tk.BOTH)
        self.add_scrollbar()
        self.refresh()
        init_callback()

        # Start the UI loop
        self.root.mainloop()
