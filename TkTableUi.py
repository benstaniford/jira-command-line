import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

class TkTableUi:
    def __init__(self, title):
        self.headers = ()
        self.data = []    # List of tuples
        self.root = None
        self.tree = None
        self.title = title
        self.root = tk.Tk()
        self.root.title(self.title)
        self.root.geometry("1024x768")

    def add_headers(self, headers):
        self.headers = headers

    def add_row(self, row):
        self.data.append(row)

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for header in self.headers:
            self.tree.heading(header, text=header, anchor=tk.W, command=lambda: self.sort_column(header, False))
        for row in self.data:
            self.tree.insert("", tk.END, values=row)
            
    def close(self):
        self.root.destroy()

    def show_details(self):
        item = self.tree.selection()[0]
        item_name = self.tree.item(item, "values")[0]
        self.display_details(item_name)

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

    def add_right_click_menu(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Details", command=self.show_details)

        def popup(event):
            if self.tree.identify_region(event.x, event.y) == "cell":
                menu.post(event.x_root, event.y_root)

        self.tree.bind("<Button-3>", popup)

    def display_details(self, item_name):
        details_window = tk.Toplevel()
        details_window.title("Item Details")
        label = ttk.Label(details_window, text="Item Details: " + item_name)
        label.pack(padx=10, pady=10)
        close_button = ttk.Button(details_window, text="Close", command=details_window.destroy)
        close_button.pack(pady=5)

    def display(self):
        self.tree = ttk.Treeview(self.root, columns=self.headers, show="headings")
        self.tree.pack(expand=True, fill=tk.BOTH)
        self.add_scrollbar()

        # Add the data
        self.refresh()

        # Add buttons and right-click menu
        refresh_button = ttk.Button(self.root, text="Refresh", command=self.refresh)
        refresh_button.pack(side=tk.LEFT, padx=5, pady=5)
        close_button = ttk.Button(self.root, text="Close", command=self.close)
        close_button.pack(side=tk.RIGHT, padx=5, pady=5)
        self.add_right_click_menu()

        self.root.mainloop()
