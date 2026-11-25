"""Portable desktop interface for Disk Space Lens."""

import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from scanner import scan


BG, INK, MUTED, ACCENT = "#edf3fa", "#152842", "#435c76", "#1d56b2"


def display_size(size):
    for multiplier, unit in ((2**40, "TB"), (2**30, "GB"), (2**20, "MB"), (2**10, "KB")):
        if size >= multiplier:
            return f"{size / multiplier:.2f} {unit}"
    return f"{size:,} B"


class DiskLens(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("磁盘空间分析器 · Disk Space Lens")
        self.geometry("1000x680")
        self.minsize(740, 500)
        self.configure(bg=BG)
        self.option_add("*Font", ("Microsoft YaHei UI", 10))
        self.events = queue.Queue()
        self.cancelled = threading.Event()
        self.rows = {}
        default_folder = "C:\\" if os.name == "nt" else str(Path.home())
        self.directory = tk.StringVar(value=default_folder)
        self.summary = tk.StringVar(value="选择磁盘或文件夹开始扫描")
        self.selection = tk.StringVar(value="选中一行可查看完整路径")
        self.style_widgets()
        self.build()
        self.after(80, self.read_events)

    def style_widgets(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=INK)
        style.configure("TEntry", fieldbackground="white", padding=8)
        style.configure("TButton", padding=(13, 8))
        style.configure("Primary.TButton", background=ACCENT, foreground="white")
        style.map("Primary.TButton", background=[("active", "#144491"), ("disabled", "#7391b9")])
        style.configure("Treeview", background="white", fieldbackground="white", rowheight=30)
        style.configure("Treeview.Heading", background="#dbe7f5", padding=(8, 6))
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        style.configure("TNotebook.Tab", padding=(16, 8))

    def label(self, parent, text, **options):
        return tk.Label(parent, text=text, bg=BG, fg=INK, anchor="w", **options)

    def build(self):
        banner = tk.Frame(self, bg="#142c4c")
        banner.pack(fill="x")
        tk.Label(banner, text="磁盘空间分析器", font=("Microsoft YaHei UI", 24, "bold"),
                 bg="#142c4c", fg="white").pack(anchor="w", padx=24, pady=(19, 2))
        tk.Label(banner, text="Disk Space Lens  ·  只读扫描本机文件大小",
                 bg="#142c4c", fg="#d5e6fa").pack(anchor="w", padx=26, pady=(0, 18))

        body = ttk.Frame(self, padding=(22, 16))
        body.pack(fill="both", expand=True)
        toolbar = ttk.Frame(body)
        toolbar.pack(fill="x")
        self.label(toolbar, "扫描位置").pack(side="left", padx=(0, 10))
        self.path_input = ttk.Entry(toolbar, textvariable=self.directory)
        self.path_input.pack(side="left", fill="x", expand=True)
        self.path_input.bind("<Return>", lambda _event: self.start())
        self.browse_button = ttk.Button(toolbar, text="选择文件夹", command=self.browse)
        self.browse_button.pack(side="left", padx=7)
        self.scan_button = ttk.Button(toolbar, text="扫描", style="Primary.TButton", command=self.start)
        self.scan_button.pack(side="left", padx=(0, 7))
        self.stop_button = ttk.Button(toolbar, text="停止", command=self.cancel, state="disabled")
        self.stop_button.pack(side="left")
        tk.Label(body, textvariable=self.summary, bg=BG, fg=MUTED, anchor="w",
                 justify="left").pack(fill="x", pady=(12, 10))

        self.tabs = ttk.Notebook(body)
        self.tabs.pack(fill="both", expand=True)
        self.folders = self.table("大文件夹")
        self.files = self.table("大文件")
        self.tabs.bind("<<NotebookTabChanged>>", lambda _event: self.show_selection())

        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(11, 0))
        label = tk.Label(footer, textvariable=self.selection, bg=BG, fg=MUTED,
                         anchor="w", justify="left")
        label.pack(side="left", fill="x", expand=True)
        label.bind("<Configure>", lambda event: label.configure(wraplength=event.width))
        self.open_button = ttk.Button(footer, text="打开所在位置", command=self.reveal, state="disabled")
        self.open_button.pack(side="right", padx=(10, 0))

    def table(self, title):
        panel = ttk.Frame(self.tabs)
        self.tabs.add(panel, text=title)
        table = ttk.Treeview(panel, columns=("size", "path"), show="headings", selectmode="browse")
        table.heading("size", text="大小")
        table.heading("path", text="完整路径")
        table.column("size", width=114, stretch=False, anchor="e")
        table.column("path", width=640, minwidth=340)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        table.pack(side="left", fill="both", expand=True)
        table.bind("<<TreeviewSelect>>", lambda _event: self.show_selection())
        table.bind("<Double-1>", lambda event: self.reveal() if table.identify_row(event.y) else None)
        table.bind("<Return>", lambda _event: self.reveal())
        self.rows[table] = {}
        return table

    def browse(self):
        path = filedialog.askdirectory(parent=self, mustexist=True)
        if path:
            self.directory.set(path)

    def set_busy(self, busy):
        for widget in (self.path_input, self.browse_button, self.scan_button):
            widget.configure(state="disabled" if busy else "normal")
        self.stop_button.configure(state="normal" if busy else "disabled")

    def start(self):
        if self.scan_button.instate(["disabled"]):
            return
        requested = self.directory.get().strip().strip('"')
        if not requested:
            self.summary.set("请输入扫描位置。")
            return
        path = os.path.abspath(os.path.expanduser(requested))
        if os.name == "nt" and path.startswith("\\\\"):
            self.summary.set("请选择本机磁盘或文件夹。")
            return
        self.directory.set(path)
        for table, rows in self.rows.items():
            table.delete(*table.get_children())
            rows.clear()
        self.show_selection()
        self.cancelled = threading.Event()
        self.summary.set("正在扫描…")
        self.set_busy(True)

        def work():
            try:
                result = scan(path, self.cancelled, lambda count: self.events.put(("count", count)))
                available = shutil.disk_usage(path).free if result else None
                self.events.put(("result", (result, available)))
            except (OSError, ValueError) as error:
                self.events.put(("error", str(error)))

        threading.Thread(target=work, daemon=True).start()

    def cancel(self):
        self.cancelled.set()
        self.stop_button.configure(state="disabled")
        self.summary.set("正在停止…")

    def read_events(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "count":
                    if not self.cancelled.is_set():
                        self.summary.set(f"正在扫描 · 已读取 {data:,} 个文件")
                else:
                    self.set_busy(False)
                    if kind == "error":
                        self.summary.set(f"读取失败 · {data}")
                    else:
                        self.display_result(*data)
        except queue.Empty:
            pass
        self.after(80, self.read_events)

    def display_result(self, result, available):
        if result is None:
            self.summary.set("扫描已停止。可以选择位置重新扫描。")
            return
        self.summary.set(f"已统计 {display_size(result.size)}   ·   {result.files:,} 个文件   ·   "
                         f"跳过 {result.skipped:,} 项   ·   磁盘可用 {display_size(available)}")
        for table, entries in ((self.folders, result.folders), (self.files, result.largest)):
            for index, (size, path) in enumerate(entries):
                row = table.insert("", "end", values=(display_size(size), path))
                self.rows[table][row] = path

    def selected_path(self):
        current = self.tabs.select()
        if not current:
            return None
        table = self.nametowidget(current).winfo_children()
        active = next(widget for widget in table if isinstance(widget, ttk.Treeview))
        selected = active.selection()
        return self.rows[active].get(selected[0]) if selected else None

    def show_selection(self):
        if not hasattr(self, "open_button"):
            return
        path = self.selected_path()
        self.selection.set(path or "选中一行可查看完整路径")
        self.open_button.configure(state="normal" if path else "disabled")

    def reveal(self):
        path = self.selected_path()
        if not path:
            return
        try:
            if os.name == "nt":
                if os.path.isdir(path):
                    subprocess.Popen([os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "explorer.exe"), path])
                elif os.path.isfile(path):
                    explorer = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "explorer.exe")
                    subprocess.Popen([explorer, "/select,", path])
                else:
                    raise FileNotFoundError("该路径可能已移动。")
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, path if os.path.isdir(path) else os.path.dirname(path)])
        except OSError as error:
            messagebox.showerror("无法打开位置", str(error), parent=self)


if __name__ == "__main__":
    DiskLens().mainloop()
