import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import os # remove

def get_files_and_sizes():
    files = os.listdir('.')
    files_and_sizes = {}
    for file in files:
        if os.path.isfile(file):
            size = os.path.getsize(file)
            files_and_sizes[file] = size
    return files_and_sizes

def display_details(file_name):
    details_window = tk.Toplevel()
    details_window.title("File Details")

    label = ttk.Label(details_window, text="File Name: " + file_name)
    label.pack(padx=10, pady=10)

    close_button = ttk.Button(details_window, text="Close", command=details_window.destroy)
    close_button.pack(pady=5)

class TkTableUi:
    def __init__(self):
        self.root = None
        self.tree = None
        self.files_and_sizes = get_files_and_sizes()

    def refresh():
        # Clear the treeview
        for row in self.tree.get_children():
            self.tree.delete(row)
        # Refresh files and sizes
        self.files_and_sizes = get_files_and_sizes()
        index = 1
        for file, size in self.files_and_sizes.items():
            self.tree.insert("", index, text=str(index), values=(file, size))
            index += 1
            
    def close(self):
        self.root.destroy()

    def show_details(self, event):
        item = self.tree.selection()[0]
        file_name = self.tree.item(item, "values")[0]
        display_details(file_name)

    def sort_column(self, col, reverse):
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]
        data.sort(reverse=reverse)

        for index, (val, child) in enumerate(data):
            self.tree.move(child, '', index)

        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))

    def display(self):
        self.root = tk.Tk()
        self.root.title("Files and Sizes")
        self.root.geometry("1024x768")

        self.tree = ttk.Treeview(self.root, columns=("File", "Size"))
        self.tree.heading("#0", text="Index", anchor=tk.W, command=lambda: self.sort_column("#0", False))
        self.tree.heading("File", text="File", anchor=tk.W, command=lambda: self.sort_column("File", False))
        self.tree.heading("Size", text="Size", anchor=tk.W, command=lambda: self.sort_column("Size", False))
        self.tree["show"] = "headings"

        index = 1
        for file, size in self.files_and_sizes.items():
            self.tree.insert("", index, text=str(index), values=(file, size))
            index += 1

        self.tree.pack(expand=True, fill=tk.BOTH)

        # Add a vertical and horizontal scrollbar
        vscrollbar = ttk.Scrollbar(self.tree, orient="vertical", command=self.tree.yview)
        vscrollbar.pack(side="right", fill="y")
        hscrollbar = ttk.Scrollbar(self.tree, orient="horizontal", command=self.tree.xview)
        hscrollbar.pack(side="bottom", fill="x")
        self.tree.configure(yscrollcommand=vscrollbar.set, xscrollcommand=hscrollbar.set)

        refresh_button = ttk.Button(self.root, text="Refresh", command=self.refresh)
        refresh_button.pack(side=tk.LEFT, padx=5, pady=5)

        close_button = ttk.Button(self.root, text="Close", command=self.close)
        close_button.pack(side=tk.RIGHT, padx=5, pady=5)

        # Right-click menu
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Details", command=self.show_details)

        def popup(event):
            if self.tree.identify_region(event.x, event.y) == "cell":
                menu.post(event.x_root, event.y_root)

        self.tree.bind("<Button-3>", popup)

        self.root.mainloop()
