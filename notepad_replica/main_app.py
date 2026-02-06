"""
FeatherPad - Main Application

A lightweight text editor with Notepad++ session recovery capabilities.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, font
import os
import sys
from typing import Optional, List, Dict
from dataclasses import dataclass

from .text_editor import TextEditor
from .session_parser import (
    recover_session, get_notepadpp_paths, TabInfo, SessionData,
    get_all_backup_files, read_file_content
)
from .session_manager import save_session, load_session, cleanup_old_backups
from .custom_tabbar import CustomTabBar
from .custom_titlebar import CustomTitleBar


@dataclass
class Tab:
    """Represents an open tab"""
    editor: TextEditor
    filepath: Optional[str]
    filename: str
    modified: bool = False
    is_new: bool = True
    encoding: str = 'utf-8'


class FindReplaceDialog(tk.Toplevel):
    """Find and Replace dialog with support for searching all tabs"""

    def __init__(self, parent, editor: TextEditor, get_all_tabs_func=None, select_tab_func=None):
        super().__init__(parent)
        self.editor = editor
        self.get_all_tabs = get_all_tabs_func  # Function to get all tabs
        self.select_tab = select_tab_func  # Function to select a specific tab
        self.title("Find and Replace")
        self.geometry("500x250")
        self.resizable(False, False)
        self.transient(parent)

        # Track search position across tabs
        self.current_search_tab_index = 0
        self.last_search_pos = '1.0'

        self._setup_ui()
        self.find_entry.focus_set()

    def _setup_ui(self):
        # Find row
        find_frame = ttk.Frame(self, padding=10)
        find_frame.pack(fill=tk.X)

        ttk.Label(find_frame, text="Find:").pack(side=tk.LEFT)
        self.find_entry = ttk.Entry(find_frame, width=40)
        self.find_entry.pack(side=tk.LEFT, padx=5)

        # Replace row
        replace_frame = ttk.Frame(self, padding=10)
        replace_frame.pack(fill=tk.X)

        ttk.Label(replace_frame, text="Replace:").pack(side=tk.LEFT)
        self.replace_entry = ttk.Entry(replace_frame, width=40)
        self.replace_entry.pack(side=tk.LEFT, padx=5)

        # Options
        options_frame = ttk.Frame(self, padding=10)
        options_frame.pack(fill=tk.X)

        self.case_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Case sensitive",
                        variable=self.case_var).pack(side=tk.LEFT)

        self.regex_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Regex",
                        variable=self.regex_var).pack(side=tk.LEFT, padx=10)

        self.all_tabs_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Search all tabs",
                        variable=self.all_tabs_var).pack(side=tk.LEFT, padx=10)

        # Buttons row 1
        btn_frame1 = ttk.Frame(self, padding=10)
        btn_frame1.pack(fill=tk.X)

        ttk.Button(btn_frame1, text="Find Next",
                   command=self._find_next).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame1, text="Find Previous",
                   command=self._find_prev).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame1, text="Find All in Tabs",
                   command=self._find_all_tabs).pack(side=tk.LEFT, padx=2)

        # Buttons row 2
        btn_frame2 = ttk.Frame(self, padding=10)
        btn_frame2.pack(fill=tk.X)

        ttk.Button(btn_frame2, text="Replace",
                   command=self._replace).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame2, text="Replace All",
                   command=self._replace_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame2, text="Close",
                   command=self.destroy).pack(side=tk.RIGHT, padx=2)

        # Status label
        self.status_label = ttk.Label(self, text="", padding=5)
        self.status_label.pack(fill=tk.X)

        # Bind Enter key
        self.find_entry.bind('<Return>', lambda e: self._find_next())
        self.find_entry.bind('<Shift-Return>', lambda e: self._find_prev())

    def _highlight_match(self, editor, start_pos, end_pos):
        """Highlight a match in the editor"""
        editor.text.tag_remove(tk.SEL, '1.0', tk.END)
        editor.text.tag_add(tk.SEL, start_pos, end_pos)
        editor.text.mark_set(tk.INSERT, end_pos)
        editor.text.see(start_pos)
        editor.text.focus_set()

    def _find_next(self):
        pattern = self.find_entry.get()
        if not pattern:
            return

        if self.all_tabs_var.get() and self.get_all_tabs:
            self._find_in_all_tabs(pattern, forward=True)
        else:
            self._find_in_current(pattern, forward=True)

    def _find_prev(self):
        pattern = self.find_entry.get()
        if not pattern:
            return

        # For previous, we need to search backwards
        self._find_in_current(pattern, forward=False)

    def _find_in_current(self, pattern, forward=True):
        """Find in current editor"""
        if forward:
            # Start from cursor position
            start = self.editor.text.index(tk.INSERT)
            result = self.editor.find_text(
                pattern, self.case_var.get(), self.regex_var.get(), start
            )
            if not result:
                # Wrap around to beginning
                result = self.editor.find_text(
                    pattern, self.case_var.get(), self.regex_var.get(), '1.0'
                )
        else:
            # Search backwards
            end_pos = self.editor.text.index(tk.INSERT)
            result = self._find_backwards(self.editor, pattern, end_pos)

        if result:
            self._highlight_match(self.editor, result[0], result[1])
            self.status_label.config(text=f"Found at line {result[0].split('.')[0]}")
        else:
            self.status_label.config(text="No matches found")
            messagebox.showinfo("Find", "No matches found")

    def _find_backwards(self, editor, pattern, before_pos):
        """Find text searching backwards"""
        content = editor.text.get('1.0', before_pos)
        import re
        flags = 0 if self.case_var.get() else re.IGNORECASE

        if self.regex_var.get():
            matches = list(re.finditer(pattern, content, flags))
        else:
            escaped = re.escape(pattern)
            matches = list(re.finditer(escaped, content, flags))

        if matches:
            last_match = matches[-1]
            # Convert string position to text index
            lines = content[:last_match.start()].split('\n')
            line_num = len(lines)
            col = len(lines[-1]) if lines else 0
            start_pos = f"{line_num}.{col}"
            end_pos = f"{start_pos}+{len(last_match.group())}c"
            return (start_pos, end_pos)
        return None

    def _find_in_all_tabs(self, pattern, forward=True):
        """Find pattern across all tabs"""
        if not self.get_all_tabs or not self.select_tab:
            self._find_in_current(pattern, forward)
            return

        tabs = self.get_all_tabs()
        if not tabs:
            return

        # Get current tab index
        current_idx = 0
        for i, (tab_id, tab) in enumerate(tabs):
            if tab.editor == self.editor:
                current_idx = i
                break

        # Start search from current cursor position in current tab
        start_pos = self.editor.text.index(tk.INSERT)

        # Search in current tab first (from cursor)
        result = self.editor.find_text(
            pattern, self.case_var.get(), self.regex_var.get(), start_pos
        )
        if result:
            self._highlight_match(self.editor, result[0], result[1])
            self.status_label.config(text=f"Found in current tab at line {result[0].split('.')[0]}")
            return

        # Search in other tabs
        for i in range(1, len(tabs) + 1):
            next_idx = (current_idx + i) % len(tabs)
            tab_id, tab = tabs[next_idx]

            result = tab.editor.find_text(
                pattern, self.case_var.get(), self.regex_var.get(), '1.0'
            )
            if result:
                # Switch to that tab and highlight
                self.select_tab(tab_id)
                self.editor = tab.editor
                self._highlight_match(tab.editor, result[0], result[1])
                self.status_label.config(text=f"Found in '{tab.filename}' at line {result[0].split('.')[0]}")
                return

        self.status_label.config(text="No matches found in any tab")
        messagebox.showinfo("Find", "No matches found in any open tab")

    def _find_all_tabs(self):
        """Find all occurrences in all tabs and show summary"""
        pattern = self.find_entry.get()
        if not pattern or not self.get_all_tabs:
            return

        tabs = self.get_all_tabs()
        total_matches = 0
        results = []

        for tab_id, tab in tabs:
            count = 0
            start = '1.0'
            while True:
                result = tab.editor.find_text(
                    pattern, self.case_var.get(), self.regex_var.get(), start
                )
                if not result:
                    break
                count += 1
                start = f"{result[1]}"

            if count > 0:
                results.append(f"{tab.filename}: {count} matches")
                total_matches += count

        if total_matches > 0:
            summary = f"Total: {total_matches} matches\n\n" + "\n".join(results)
            self.status_label.config(text=f"Found {total_matches} matches in {len(results)} tabs")
            messagebox.showinfo("Find All Results", summary)
        else:
            self.status_label.config(text="No matches found")
            messagebox.showinfo("Find All Results", "No matches found in any tab")

    def _replace(self):
        find_pattern = self.find_entry.get()
        replace_with = self.replace_entry.get()
        if find_pattern:
            self.editor.replace_text(
                find_pattern, replace_with,
                self.case_var.get(), self.regex_var.get()
            )

    def _replace_all(self):
        find_pattern = self.find_entry.get()
        replace_with = self.replace_entry.get()
        if not find_pattern:
            return

        if self.all_tabs_var.get() and self.get_all_tabs:
            # Replace in all tabs
            tabs = self.get_all_tabs()
            total_count = 0
            for tab_id, tab in tabs:
                count = tab.editor.replace_all(
                    find_pattern, replace_with,
                    self.case_var.get(), self.regex_var.get()
                )
                total_count += count
            self.status_label.config(text=f"Replaced {total_count} occurrences in all tabs")
            messagebox.showinfo("Replace All", f"Replaced {total_count} occurrences in all tabs")
        else:
            count = self.editor.replace_all(
                find_pattern, replace_with,
                self.case_var.get(), self.regex_var.get()
            )
            self.status_label.config(text=f"Replaced {count} occurrences")
            messagebox.showinfo("Replace All", f"Replaced {count} occurrences")


class GoToLineDialog(simpledialog.Dialog):
    """Go to line dialog"""

    def __init__(self, parent, max_line: int):
        self.max_line = max_line
        self.result = None
        super().__init__(parent, title="Go to Line")

    def body(self, master):
        ttk.Label(master, text=f"Line number (1 - {self.max_line}):").grid(row=0, column=0, pady=5)
        self.entry = ttk.Entry(master, width=20)
        self.entry.grid(row=0, column=1, padx=5, pady=5)
        return self.entry

    def apply(self):
        try:
            self.result = int(self.entry.get())
        except ValueError:
            self.result = None


class FeatherPad(tk.Tk):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Remove system title bar for custom theming
        self.overrideredirect(True)

        # Store window title for updates
        self._window_title = "FeatherPad"
        self.geometry("1200x800")

        # Center window on screen
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - 1200) // 2
        y = (screen_h - 800) // 2
        self.geometry(f"1200x800+{x}+{y}")

        # Make window appear in taskbar (Windows-specific workaround)
        self.after(10, self._setup_taskbar_icon)

        # Application state
        self.tabs: Dict[str, Tab] = {}  # tab_id -> Tab
        self.new_file_counter = 1
        self.word_wrap_enabled = False
        self.current_find_dialog: Optional[FindReplaceDialog] = None

        # Set up UI
        self._setup_styles()
        self._setup_titlebar()  # Custom title bar first
        self._setup_menu()
        self._setup_toolbar()
        self._setup_tabbar()
        self._setup_editor_container()
        self._setup_statusbar()
        self._setup_bindings()
        self._setup_resize_grip()  # Add resize capability

        # Set app icon (if available)
        try:
            self.iconbitmap('icon.ico')
        except:
            pass

        # Clean up old backups
        cleanup_old_backups()

        # Try to restore previous session
        if not self._restore_session():
            # Start with a new tab if no session
            self.new_file()

    def _setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')

        # Tab style
        style.configure('TNotebook.Tab', padding=[10, 5])

    def _setup_taskbar_icon(self):
        """Make the window appear in the taskbar (Windows-specific)"""
        try:
            import ctypes

            # Get window handle
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())

            # Set window style to appear in taskbar
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080

            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style & ~WS_EX_TOOLWINDOW
            style = style | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

            # Force window to refresh
            self.withdraw()
            self.after(10, self.deiconify)
        except Exception:
            # Not on Windows or error, ignore
            pass

    def _setup_titlebar(self):
        """Set up custom title bar"""
        self.titlebar = CustomTitleBar(self, title=self._window_title, theme='light')
        self.titlebar.pack(side=tk.TOP, fill=tk.X)
        self.titlebar.pack_border()

    def _setup_resize_grip(self):
        """Set up window resize grips"""
        # Resize grip at bottom-right corner
        self.resize_grip = tk.Frame(self, width=16, height=16, cursor='size_nw_se', bg='#e0e0e0')
        self.resize_grip.place(relx=1.0, rely=1.0, anchor='se')

        # Bind resize events
        self.resize_grip.bind('<Button-1>', self._start_resize)
        self.resize_grip.bind('<B1-Motion>', self._on_resize)

        # Edge resize areas (thin frames at edges) - transparent/matching window bg
        self._resize_edges = {}

        # Right edge - use a very thin invisible frame
        right_edge = tk.Frame(self, width=3, cursor='size_we')
        right_edge.place(relx=1.0, y=32, relheight=1.0, height=-48, anchor='ne')
        right_edge.bind('<Button-1>', lambda e: self._start_edge_resize(e, 'right'))
        right_edge.bind('<B1-Motion>', lambda e: self._on_edge_resize(e, 'right'))
        self._resize_edges['right'] = right_edge

        # Bottom edge
        bottom_edge = tk.Frame(self, height=3, cursor='size_ns')
        bottom_edge.place(x=0, rely=1.0, relwidth=1.0, width=-16, anchor='sw')
        bottom_edge.bind('<Button-1>', lambda e: self._start_edge_resize(e, 'bottom'))
        bottom_edge.bind('<B1-Motion>', lambda e: self._on_edge_resize(e, 'bottom'))
        self._resize_edges['bottom'] = bottom_edge

        # Left edge
        left_edge = tk.Frame(self, width=3, cursor='size_we')
        left_edge.place(x=0, y=32, relheight=1.0, height=-48, anchor='nw')
        left_edge.bind('<Button-1>', lambda e: self._start_edge_resize(e, 'left'))
        left_edge.bind('<B1-Motion>', lambda e: self._on_edge_resize(e, 'left'))
        self._resize_edges['left'] = left_edge

        # Store resize start position
        self._resize_start = {'x': 0, 'y': 0, 'w': 0, 'h': 0, 'win_x': 0, 'win_y': 0}

    def _start_resize(self, event):
        """Start window resize from corner"""
        self._resize_start['x'] = event.x_root
        self._resize_start['y'] = event.y_root
        self._resize_start['w'] = self.winfo_width()
        self._resize_start['h'] = self.winfo_height()

    def _on_resize(self, event):
        """Handle window resize from corner"""
        dx = event.x_root - self._resize_start['x']
        dy = event.y_root - self._resize_start['y']

        new_w = max(400, self._resize_start['w'] + dx)
        new_h = max(300, self._resize_start['h'] + dy)

        self.geometry(f'{new_w}x{new_h}')

    def _start_edge_resize(self, event, edge):
        """Start edge resize"""
        self._resize_start['x'] = event.x_root
        self._resize_start['y'] = event.y_root
        self._resize_start['w'] = self.winfo_width()
        self._resize_start['h'] = self.winfo_height()
        self._resize_start['win_x'] = self.winfo_x()
        self._resize_start['win_y'] = self.winfo_y()

    def _on_edge_resize(self, event, edge):
        """Handle edge resize"""
        dx = event.x_root - self._resize_start['x']
        dy = event.y_root - self._resize_start['y']

        if edge == 'right':
            new_w = max(400, self._resize_start['w'] + dx)
            self.geometry(f"{new_w}x{self.winfo_height()}")
        elif edge == 'bottom':
            new_h = max(300, self._resize_start['h'] + dy)
            self.geometry(f"{self.winfo_width()}x{new_h}")
        elif edge == 'left':
            new_w = max(400, self._resize_start['w'] - dx)
            new_x = self._resize_start['win_x'] + (self._resize_start['w'] - new_w)
            self.geometry(f"{new_w}x{self.winfo_height()}+{new_x}+{self.winfo_y()}")

    def _setup_menu(self):
        """Set up custom menu bar using frame and menubuttons for full theme control"""
        # Custom menu bar frame
        self.menubar = tk.Frame(self, bg='#f0f0f0', pady=1)
        self.menubar.pack(side=tk.TOP, fill=tk.X)

        # Store menu buttons for theming
        self.menu_buttons = []
        self.menus = {}

        # Menu button style
        mb_config = {'bg': '#f0f0f0', 'fg': '#000000', 'relief': 'flat',
                     'activebackground': '#0078d7', 'activeforeground': '#ffffff',
                     'padx': 8, 'pady': 2, 'bd': 0, 'highlightthickness': 0}

        # File menu
        file_mb = tk.Menubutton(self.menubar, text="File", **mb_config)
        file_mb.pack(side=tk.LEFT)
        self.menu_buttons.append(file_mb)
        file_menu = tk.Menu(file_mb, tearoff=0)
        file_mb.config(menu=file_menu)
        self.menus['File'] = file_menu
        file_menu.add_command(label="New", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Open Folder...", command=self.open_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_command(label="Save All", command=self.save_all, accelerator="Ctrl+Shift+A")
        file_menu.add_separator()
        file_menu.add_command(label="Close", command=self.close_current_tab, accelerator="Ctrl+W")
        file_menu.add_command(label="Close All", command=self.close_all_tabs)
        file_menu.add_separator()
        file_menu.add_command(label="Recover Notepad++ Session", command=self.recover_notepadpp_session)
        file_menu.add_command(label="Browse Notepad++ Backups", command=self.browse_notepadpp_backups)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit_app, accelerator="Alt+F4")

        # Edit menu
        edit_mb = tk.Menubutton(self.menubar, text="Edit", **mb_config)
        edit_mb.pack(side=tk.LEFT)
        self.menu_buttons.append(edit_mb)
        edit_menu = tk.Menu(edit_mb, tearoff=0)
        edit_mb.config(menu=edit_menu)
        self.menus['Edit'] = edit_menu
        edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=self.cut, accelerator="Ctrl+X")
        edit_menu.add_command(label="Copy", command=self.copy, accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", command=self.paste, accelerator="Ctrl+V")
        edit_menu.add_command(label="Delete", command=self.delete)
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", command=self.select_all, accelerator="Ctrl+A")
        edit_menu.add_separator()
        edit_menu.add_command(label="Duplicate Line", command=self.duplicate_line, accelerator="Ctrl+D")
        edit_menu.add_command(label="Delete Line", command=self.delete_line, accelerator="Ctrl+L")

        # Search menu
        search_mb = tk.Menubutton(self.menubar, text="Search", **mb_config)
        search_mb.pack(side=tk.LEFT)
        self.menu_buttons.append(search_mb)
        search_menu = tk.Menu(search_mb, tearoff=0)
        search_mb.config(menu=search_menu)
        self.menus['Search'] = search_menu
        search_menu.add_command(label="Find...", command=self.show_find_dialog, accelerator="Ctrl+F")
        search_menu.add_command(label="Find & Replace...", command=self.show_find_dialog, accelerator="Ctrl+H")
        search_menu.add_separator()
        search_menu.add_command(label="Go to Line...", command=self.goto_line, accelerator="Ctrl+G")

        # View menu
        view_mb = tk.Menubutton(self.menubar, text="View", **mb_config)
        view_mb.pack(side=tk.LEFT)
        self.menu_buttons.append(view_mb)
        view_menu = tk.Menu(view_mb, tearoff=0)
        view_mb.config(menu=view_menu)
        self.menus['View'] = view_menu

        self.word_wrap_var = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(label="Word Wrap", variable=self.word_wrap_var,
                                   command=self.toggle_word_wrap)

        view_menu.add_separator()
        view_menu.add_command(label="Zoom In", command=lambda: self.zoom(1), accelerator="Ctrl++")
        view_menu.add_command(label="Zoom Out", command=lambda: self.zoom(-1), accelerator="Ctrl+-")
        view_menu.add_command(label="Reset Zoom", command=lambda: self.zoom(0), accelerator="Ctrl+0")

        # Encoding menu
        encoding_mb = tk.Menubutton(self.menubar, text="Encoding", **mb_config)
        encoding_mb.pack(side=tk.LEFT)
        self.menu_buttons.append(encoding_mb)
        encoding_menu = tk.Menu(encoding_mb, tearoff=0)
        encoding_mb.config(menu=encoding_menu)
        self.menus['Encoding'] = encoding_menu

        self.encoding_var = tk.StringVar(value='utf-8')
        for enc in ['UTF-8', 'UTF-8 BOM', 'UTF-16', 'ANSI (Windows-1252)', 'ISO-8859-1']:
            encoding_menu.add_radiobutton(label=enc, variable=self.encoding_var,
                                           value=enc.lower().replace(' ', '-').replace('(', '').replace(')', ''))

        # Theme menu
        theme_mb = tk.Menubutton(self.menubar, text="Theme", **mb_config)
        theme_mb.pack(side=tk.LEFT)
        self.menu_buttons.append(theme_mb)
        theme_menu = tk.Menu(theme_mb, tearoff=0)
        theme_mb.config(menu=theme_menu)
        self.menus['Theme'] = theme_menu

        self.theme_var = tk.StringVar(value='light')
        theme_menu.add_radiobutton(label="Light Mode", variable=self.theme_var,
                                    value='light', command=self._apply_theme)
        theme_menu.add_radiobutton(label="Dark Mode", variable=self.theme_var,
                                    value='dark', command=self._apply_theme)

        # Help menu
        help_mb = tk.Menubutton(self.menubar, text="Help", **mb_config)
        help_mb.pack(side=tk.LEFT)
        self.menu_buttons.append(help_mb)
        help_menu = tk.Menu(help_mb, tearoff=0)
        help_mb.config(menu=help_menu)
        self.menus['Help'] = help_menu
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)

    def _setup_toolbar(self):
        """Set up toolbar"""
        # Use tk.Frame for full theme control
        self.toolbar = tk.Frame(self, padx=2, pady=2, bg='#f5f5f5')
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # Store buttons for theming
        self.toolbar_buttons = []

        # Toolbar buttons (using tk.Button for theme support)
        btn_config = {'relief': 'flat', 'padx': 8, 'pady': 2, 'bd': 1}

        btn_new = tk.Button(self.toolbar, text="New", command=self.new_file, **btn_config)
        btn_new.pack(side=tk.LEFT, padx=1)
        self.toolbar_buttons.append(btn_new)

        btn_open = tk.Button(self.toolbar, text="Open", command=self.open_file, **btn_config)
        btn_open.pack(side=tk.LEFT, padx=1)
        self.toolbar_buttons.append(btn_open)

        btn_save = tk.Button(self.toolbar, text="Save", command=self.save_file, **btn_config)
        btn_save.pack(side=tk.LEFT, padx=1)
        self.toolbar_buttons.append(btn_save)

        tk.Frame(self.toolbar, width=2, bg='#cccccc').pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        btn_undo = tk.Button(self.toolbar, text="Undo", command=self.undo, **btn_config)
        btn_undo.pack(side=tk.LEFT, padx=1)
        self.toolbar_buttons.append(btn_undo)

        btn_redo = tk.Button(self.toolbar, text="Redo", command=self.redo, **btn_config)
        btn_redo.pack(side=tk.LEFT, padx=1)
        self.toolbar_buttons.append(btn_redo)

        tk.Frame(self.toolbar, width=2, bg='#cccccc').pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        btn_find = tk.Button(self.toolbar, text="Find", command=self.show_find_dialog, **btn_config)
        btn_find.pack(side=tk.LEFT, padx=1)
        self.toolbar_buttons.append(btn_find)

        tk.Frame(self.toolbar, width=2, bg='#cccccc').pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        # Recovery button
        btn_recover = tk.Button(self.toolbar, text="Recover Notepad++", command=self.recover_notepadpp_session, **btn_config)
        btn_recover.pack(side=tk.LEFT, padx=5)
        self.toolbar_buttons.append(btn_recover)

    def _setup_tabbar(self):
        """Set up the custom tab bar"""
        self.tabbar = CustomTabBar(
            self,
            on_tab_select=self._on_tab_selected,
            on_tab_close=self._on_tab_close_clicked,
            on_new_tab=self.new_file
        )
        self.tabbar.pack(fill=tk.X, padx=5, pady=(5, 0))

        # Right-click menu for tabs
        self.tab_menu = tk.Menu(self, tearoff=0)
        self.tab_menu.add_command(label="Close", command=self.close_current_tab)
        self.tab_menu.add_command(label="Close Others", command=self.close_other_tabs)
        self.tab_menu.add_command(label="Close All", command=self.close_all_tabs)
        self.tab_menu.add_separator()
        self.tab_menu.add_command(label="Copy Path", command=self._copy_current_path)

    def _setup_editor_container(self):
        """Set up the container for editors"""
        self.editor_container = ttk.Frame(self)
        self.editor_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Dictionary to track editor frames
        self.editor_frames: Dict[str, ttk.Frame] = {}

    def _setup_statusbar(self):
        """Set up status bar"""
        # Use tk.Frame for full theme control
        self.statusbar = tk.Frame(self, padx=5, pady=2, bg='#f0f0f0')
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_text = tk.Label(self.statusbar, text="Ready", bg='#f0f0f0')
        self.status_text.pack(side=tk.LEFT)

        self.tab_count_label = tk.Label(self.statusbar, text="Tabs: 0", bg='#f0f0f0')
        self.tab_count_label.pack(side=tk.RIGHT, padx=10)

    def _setup_bindings(self):
        """Set up global keyboard bindings"""
        self.bind('<Control-n>', lambda e: self.new_file())
        self.bind('<Control-N>', lambda e: self.new_file())
        self.bind('<Control-o>', lambda e: self.open_file())
        self.bind('<Control-O>', lambda e: self.open_file())
        self.bind('<Control-s>', lambda e: self.save_file())
        self.bind('<Control-S>', lambda e: self.save_file())
        self.bind('<Control-Shift-s>', lambda e: self.save_file_as())
        self.bind('<Control-Shift-S>', lambda e: self.save_file_as())
        self.bind('<Control-w>', lambda e: self.close_current_tab())
        self.bind('<Control-W>', lambda e: self.close_current_tab())
        self.bind('<Control-f>', lambda e: self.show_find_dialog())
        self.bind('<Control-F>', lambda e: self.show_find_dialog())
        self.bind('<Control-h>', lambda e: self.show_find_dialog())
        self.bind('<Control-H>', lambda e: self.show_find_dialog())
        self.bind('<Control-g>', lambda e: self.goto_line())
        self.bind('<Control-G>', lambda e: self.goto_line())
        self.bind('<Control-plus>', lambda e: self.zoom(1))
        self.bind('<Control-minus>', lambda e: self.zoom(-1))
        self.bind('<Control-0>', lambda e: self.zoom(0))
        self.bind('<Control-Tab>', lambda e: self._next_tab())
        self.bind('<Control-Shift-Tab>', lambda e: self._prev_tab())

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    def _get_current_tab(self) -> Optional[Tab]:
        """Get the currently active tab"""
        tab_id = self.tabbar.get_selected()
        return self.tabs.get(tab_id)

    def _get_current_editor(self) -> Optional[TextEditor]:
        """Get the editor of the current tab"""
        tab = self._get_current_tab()
        return tab.editor if tab else None

    def _update_tab_title(self, tab_id: str):
        """Update tab title to reflect modified state"""
        tab = self.tabs.get(tab_id)
        if tab:
            self.tabbar.update_tab(tab_id, text=tab.filename, modified=tab.modified)

    def _update_status(self):
        """Update status bar"""
        self.tab_count_label.config(text=f"Tabs: {len(self.tabs)}")

    def _on_tab_selected(self, tab_id: str):
        """Handle tab selection from custom tab bar"""
        # Hide all editors
        for frame in self.editor_frames.values():
            frame.pack_forget()

        # Show selected editor
        if tab_id in self.editor_frames:
            self.editor_frames[tab_id].pack(fill=tk.BOTH, expand=True)

        # Update window title and encoding
        tab = self.tabs.get(tab_id)
        if tab:
            title = f"{tab.filename} - FeatherPad"
            self._window_title = title
            self.titlebar.set_title(title)
            self.encoding_var.set(tab.encoding.lower())
            tab.editor.focus()

    def _on_tab_close_clicked(self, tab_id: str):
        """Handle close button click on tab"""
        self._close_tab(tab_id)

    def _copy_current_path(self):
        """Copy current file path to clipboard"""
        tab = self._get_current_tab()
        if tab and tab.filepath:
            self.clipboard_clear()
            self.clipboard_append(tab.filepath)
            self.status_text.config(text="Path copied to clipboard")

    def _next_tab(self):
        """Switch to next tab"""
        tab_ids = self.tabbar.get_all_tabs()
        if len(tab_ids) > 1:
            current_id = self.tabbar.get_selected()
            if current_id in tab_ids:
                current_idx = tab_ids.index(current_id)
                next_idx = (current_idx + 1) % len(tab_ids)
                self.tabbar.select(tab_ids[next_idx])

    def _prev_tab(self):
        """Switch to previous tab"""
        tab_ids = self.tabbar.get_all_tabs()
        if len(tab_ids) > 1:
            current_id = self.tabbar.get_selected()
            if current_id in tab_ids:
                current_idx = tab_ids.index(current_id)
                prev_idx = (current_idx - 1) % len(tab_ids)
                self.tabbar.select(tab_ids[prev_idx])

    def _get_all_tabs_for_search(self):
        """Get all tabs for find/replace dialog"""
        return [(tab_id, tab) for tab_id, tab in self.tabs.items()]

    def _select_tab_by_id(self, tab_id: str):
        """Select a tab by its ID"""
        if tab_id in self.tabs:
            self.tabbar.select(tab_id)

    # File operations

    def new_file(self):
        """Create a new empty tab"""
        # Create editor frame in the container
        editor_frame = ttk.Frame(self.editor_container)
        editor = TextEditor(editor_frame)
        editor.pack(fill=tk.BOTH, expand=True)

        filename = f"new {self.new_file_counter}"
        self.new_file_counter += 1

        # Generate unique tab ID
        tab_id = f"tab_{id(editor)}"

        tab = Tab(
            editor=editor,
            filepath=None,
            filename=filename,
            is_new=True
        )

        self.tabs[tab_id] = tab
        self.editor_frames[tab_id] = editor_frame

        # Add to tab bar
        self.tabbar.add_tab(tab_id, filename)

        # Set up modification callback
        def on_modified():
            tab.modified = True
            self._update_tab_title(tab_id)

        editor.set_on_modified(on_modified)

        # Select the new tab
        self.tabbar.select(tab_id)

        self._update_status()
        return tab_id

    def open_file(self, filepath: str = None):
        """Open a file"""
        if filepath is None:
            filepath = filedialog.askopenfilename(
                title="Open File",
                filetypes=[
                    ("All Files", "*.*"),
                    ("Text Files", "*.txt"),
                    ("Python Files", "*.py"),
                    ("JavaScript Files", "*.js"),
                    ("HTML Files", "*.html"),
                    ("CSS Files", "*.css"),
                    ("JSON Files", "*.json"),
                    ("XML Files", "*.xml"),
                    ("Markdown Files", "*.md"),
                ]
            )

        if not filepath:
            return

        # Check if file is already open
        for tab_id, tab in self.tabs.items():
            if tab.filepath and os.path.normpath(tab.filepath) == os.path.normpath(filepath):
                self.tabbar.select(tab_id)
                return

        # Read file content
        content, error = read_file_content(filepath)
        if error:
            messagebox.showerror("Error", f"Could not open file:\n{error}")
            return

        # Create new tab
        editor_frame = ttk.Frame(self.editor_container)
        editor = TextEditor(editor_frame)
        editor.pack(fill=tk.BOTH, expand=True)

        filename = os.path.basename(filepath)
        tab_id = f"tab_{id(editor)}"

        tab = Tab(
            editor=editor,
            filepath=filepath,
            filename=filename,
            is_new=False
        )

        self.tabs[tab_id] = tab
        self.editor_frames[tab_id] = editor_frame

        # Add to tab bar
        self.tabbar.add_tab(tab_id, filename)

        # Set content
        editor.set_content(content or '')

        # Set up modification callback
        def on_modified():
            tab.modified = True
            self._update_tab_title(tab_id)

        editor.set_on_modified(on_modified)

        # Select the new tab
        self.tabbar.select(tab_id)

        self._update_status()
        self.status_text.config(text=f"Opened: {filepath}")

    def open_folder(self):
        """Open all files in a folder"""
        folder = filedialog.askdirectory(title="Open Folder")
        if not folder:
            return

        count = 0
        for entry in os.listdir(folder):
            filepath = os.path.join(folder, entry)
            if os.path.isfile(filepath):
                # Only open text-like files
                ext = os.path.splitext(entry)[1].lower()
                text_extensions = ['.txt', '.py', '.js', '.html', '.css', '.json',
                                   '.xml', '.md', '.yml', '.yaml', '.ini', '.cfg',
                                   '.sh', '.bat', '.ps1', '.sql', '.log', '.csv']
                if ext in text_extensions or not ext:
                    self.open_file(filepath)
                    count += 1

        self.status_text.config(text=f"Opened {count} files from {folder}")

    def save_file(self):
        """Save current file"""
        tab = self._get_current_tab()
        if not tab:
            return

        if tab.is_new or not tab.filepath:
            self.save_file_as()
        else:
            self._save_to_file(tab, tab.filepath)

    def save_file_as(self):
        """Save current file with new name"""
        tab = self._get_current_tab()
        if not tab:
            return

        filepath = filedialog.asksaveasfilename(
            title="Save As",
            defaultextension=".txt",
            initialfile=tab.filename,
            filetypes=[
                ("All Files", "*.*"),
                ("Text Files", "*.txt"),
                ("Python Files", "*.py"),
                ("JavaScript Files", "*.js"),
                ("HTML Files", "*.html"),
                ("CSS Files", "*.css"),
                ("JSON Files", "*.json"),
            ]
        )

        if filepath:
            self._save_to_file(tab, filepath)

    def _save_to_file(self, tab: Tab, filepath: str):
        """Save tab content to file"""
        try:
            content = tab.editor.get_content()
            encoding = tab.encoding

            with open(filepath, 'w', encoding=encoding) as f:
                f.write(content)

            # Update tab info
            tab.filepath = filepath
            tab.filename = os.path.basename(filepath)
            tab.is_new = False
            tab.modified = False

            # Update tab title
            tab_id = str(tab.editor)
            self.notebook.tab(tab_id, text=tab.filename)

            self.status_text.config(text=f"Saved: {filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")

    def save_all(self):
        """Save all modified files"""
        saved = 0
        for tab_id, tab in self.tabs.items():
            if tab.modified:
                if tab.is_new or not tab.filepath:
                    # Can't auto-save new files
                    continue
                self._save_to_file(tab, tab.filepath)
                saved += 1

        self.status_text.config(text=f"Saved {saved} files")

    def _close_tab(self, tab_id: str) -> bool:
        """Close a specific tab"""
        tab = self.tabs.get(tab_id)
        if not tab:
            return True

        # Check for unsaved changes
        if tab.modified:
            result = messagebox.askyesnocancel(
                "Unsaved Changes",
                f"Do you want to save changes to {tab.filename}?"
            )
            if result is None:  # Cancel
                return False
            elif result:  # Yes
                self.tabbar.select(tab_id)
                self.save_file()
                if tab.modified:  # Save was cancelled
                    return False

        # Remove from tab bar
        self.tabbar.remove_tab(tab_id)

        # Remove editor frame
        if tab_id in self.editor_frames:
            self.editor_frames[tab_id].destroy()
            del self.editor_frames[tab_id]

        del self.tabs[tab_id]

        self._update_status()

        # If no tabs left, create a new one
        if not self.tabs:
            self.new_file()

        return True

    def close_current_tab(self):
        """Close the current tab"""
        tab_id = self.tabbar.get_selected()
        if tab_id:
            self._close_tab(tab_id)

    def close_other_tabs(self):
        """Close all tabs except current"""
        current_id = self.tabbar.get_selected()
        for tab_id in list(self.tabs.keys()):
            if tab_id != current_id:
                if not self._close_tab(tab_id):
                    break

    def close_all_tabs(self):
        """Close all tabs"""
        for tab_id in list(self.tabs.keys()):
            if not self._close_tab(tab_id):
                break

    # Session recovery

    def recover_notepadpp_session(self):
        """Recover tabs from Notepad++ session"""
        npp_dir, session_file, backup_dir = get_notepadpp_paths()

        if not session_file or not os.path.exists(session_file):
            # Ask user to locate session file
            session_file = filedialog.askopenfilename(
                title="Locate Notepad++ session.xml",
                filetypes=[("XML Files", "*.xml"), ("All Files", "*.*")],
                initialdir=os.environ.get('APPDATA', '')
            )
            if not session_file:
                messagebox.showinfo(
                    "Recovery",
                    "Could not find Notepad++ session file.\n\n"
                    "Please locate your session.xml file manually.\n"
                    "It's usually in: %APPDATA%\\Notepad++"
                )
                return

            # Derive backup dir from session file location
            backup_dir = os.path.join(os.path.dirname(session_file), 'backup')

        # Show progress
        self.status_text.config(text="Recovering Notepad++ session...")
        self.update()

        # Recover session
        session = recover_session(session_file, backup_dir)

        if session.errors:
            for error in session.errors[:5]:  # Show first 5 errors
                print(f"Warning: {error}")

        if not session.tabs:
            messagebox.showinfo(
                "Recovery",
                "No tabs found in Notepad++ session.\n\n"
                f"Session file: {session_file}"
            )
            return

        # Close default new tab if empty
        if len(self.tabs) == 1:
            tab = self._get_current_tab()
            if tab and tab.is_new and not tab.modified:
                tab_id = self.tabbar.get_selected()
                if tab_id:
                    self.tabbar.remove_tab(tab_id)
                    if tab_id in self.editor_frames:
                        self.editor_frames[tab_id].destroy()
                        del self.editor_frames[tab_id]
                    del self.tabs[tab_id]

        # Create tabs for recovered files
        recovered = 0
        first_tab_id = None
        for tab_info in session.tabs:
            editor_frame = ttk.Frame(self.editor_container)
            editor = TextEditor(editor_frame)
            editor.pack(fill=tk.BOTH, expand=True)

            # Determine display name
            if tab_info.is_backup:
                display_name = f"{tab_info.filename} (recovered)"
            else:
                display_name = tab_info.filename

            tab_id = f"tab_{id(editor)}"

            tab = Tab(
                editor=editor,
                filepath=tab_info.filepath if not tab_info.is_new_file else None,
                filename=tab_info.filename,
                is_new=tab_info.is_new_file,
                encoding=tab_info.encoding
            )

            self.tabs[tab_id] = tab
            self.editor_frames[tab_id] = editor_frame

            # Add to tab bar
            self.tabbar.add_tab(tab_id, display_name, modified=tab_info.is_backup)

            if first_tab_id is None:
                first_tab_id = tab_id

            # Set content
            if tab_info.content:
                editor.set_content(tab_info.content)
                if tab_info.is_backup:
                    tab.modified = True
            else:
                editor.set_content(f"# Could not recover content for: {tab_info.filepath}")

            # Set encoding
            editor.set_encoding(tab_info.encoding)

            # Set up modification callback
            def on_modified(t=tab, tid=tab_id):
                t.modified = True
                self._update_tab_title(tid)

            editor.set_on_modified(on_modified)
            recovered += 1

        # Select first recovered tab
        if first_tab_id:
            self.tabbar.select(first_tab_id)

        self._update_status()
        self.status_text.config(text=f"Recovered {recovered} tabs from Notepad++")

        messagebox.showinfo(
            "Recovery Complete",
            f"Successfully recovered {recovered} tabs from Notepad++!\n\n"
            f"Session file: {session_file}\n"
            f"Backup directory: {backup_dir}\n\n"
            "Note: Unsaved changes are marked with *"
        )

    def browse_notepadpp_backups(self):
        """Browse all Notepad++ backup files"""
        _, _, backup_dir = get_notepadpp_paths()

        if not backup_dir or not os.path.exists(backup_dir):
            backup_dir = filedialog.askdirectory(
                title="Locate Notepad++ backup folder",
                initialdir=os.environ.get('APPDATA', '')
            )
            if not backup_dir:
                return

        # Get all backup files
        backup_tabs = get_all_backup_files(backup_dir)

        if not backup_tabs:
            messagebox.showinfo("Backups", "No backup files found.")
            return

        # Create tabs for backup files
        for tab_info in backup_tabs:
            editor_frame = ttk.Frame(self.editor_container)
            editor = TextEditor(editor_frame)
            editor.pack(fill=tk.BOTH, expand=True)

            tab_id = f"tab_{id(editor)}"

            tab = Tab(
                editor=editor,
                filepath=tab_info.backup_path,
                filename=tab_info.filename,
                is_new=True
            )

            self.tabs[tab_id] = tab
            self.editor_frames[tab_id] = editor_frame

            # Add to tab bar
            self.tabbar.add_tab(tab_id, tab_info.filename)

            if tab_info.content:
                editor.set_content(tab_info.content)

            def on_modified(t=tab, tid=tab_id):
                t.modified = True
                self._update_tab_title(tid)

            editor.set_on_modified(on_modified)

        self._update_status()
        self.status_text.config(text=f"Loaded {len(backup_tabs)} backup files")

    # Edit operations

    def undo(self):
        """Undo last edit"""
        editor = self._get_current_editor()
        if editor:
            try:
                editor.text.edit_undo()
            except tk.TclError:
                pass

    def redo(self):
        """Redo last undone edit"""
        editor = self._get_current_editor()
        if editor:
            try:
                editor.text.edit_redo()
            except tk.TclError:
                pass

    def cut(self):
        """Cut selection"""
        editor = self._get_current_editor()
        if editor:
            editor.text.event_generate('<<Cut>>')

    def copy(self):
        """Copy selection"""
        editor = self._get_current_editor()
        if editor:
            editor.text.event_generate('<<Copy>>')

    def paste(self):
        """Paste from clipboard"""
        editor = self._get_current_editor()
        if editor:
            editor.text.event_generate('<<Paste>>')

    def delete(self):
        """Delete selection"""
        editor = self._get_current_editor()
        if editor:
            try:
                editor.text.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass

    def select_all(self):
        """Select all text"""
        editor = self._get_current_editor()
        if editor:
            editor._select_all()

    def duplicate_line(self):
        """Duplicate current line"""
        editor = self._get_current_editor()
        if editor:
            editor._duplicate_line()

    def delete_line(self):
        """Delete current line"""
        editor = self._get_current_editor()
        if editor:
            editor._delete_line()

    # Search operations

    def show_find_dialog(self):
        """Show find and replace dialog"""
        editor = self._get_current_editor()
        if editor:
            if self.current_find_dialog:
                self.current_find_dialog.destroy()
            self.current_find_dialog = FindReplaceDialog(
                self, editor,
                get_all_tabs_func=self._get_all_tabs_for_search,
                select_tab_func=self._select_tab_by_id
            )

    def goto_line(self):
        """Go to specific line"""
        editor = self._get_current_editor()
        if editor:
            content = editor.get_content()
            max_line = content.count('\n') + 1
            dialog = GoToLineDialog(self, max_line)
            if dialog.result and 1 <= dialog.result <= max_line:
                editor.goto_line(dialog.result)

    # View operations

    def toggle_word_wrap(self):
        """Toggle word wrap"""
        self.word_wrap_enabled = self.word_wrap_var.get()
        for tab in self.tabs.values():
            tab.editor.set_word_wrap(self.word_wrap_enabled)

    def zoom(self, direction: int):
        """Zoom text (direction: 1=in, -1=out, 0=reset)"""
        for tab in self.tabs.values():
            current_font = font.Font(font=tab.editor.text['font'])
            current_size = current_font.actual()['size']

            if direction == 0:
                new_size = 10
            else:
                new_size = max(6, min(72, current_size + (2 * direction)))

            new_font = font.Font(family='Consolas', size=new_size)
            tab.editor.text.configure(font=new_font)
            tab.editor.line_numbers.font = new_font

    def _apply_theme(self):
        """Apply the selected theme to the application"""
        theme = self.theme_var.get()

        # Claude Code inspired dark theme colors
        if theme == 'dark':
            # Main backgrounds
            editor_bg = '#0d0d0d'      # Very dark, almost black
            editor_fg = '#e5e5e5'      # Light grey text
            line_num_bg = '#1a1a1a'    # Slightly lighter dark
            line_num_fg = '#6b7280'    # Muted grey
            select_bg = '#2563eb'      # Blue selection
            select_fg = '#ffffff'
            cursor_color = '#f5f5f5'
            main_bg = '#171717'        # Dark grey background
            toolbar_bg = '#262626'     # Toolbar dark grey
            status_bg = '#1a1a1a'      # Status bar dark
            button_bg = '#374151'      # Button grey
            button_fg = '#e5e5e5'
            menu_bg = '#1f1f1f'
            menu_fg = '#e5e5e5'
            border_color = '#404040'
            scrollbar_bg = '#262626'
            scrollbar_fg = '#525252'
        else:  # light
            editor_bg = '#ffffff'
            editor_fg = '#000000'
            line_num_bg = '#f0f0f0'
            line_num_fg = '#666666'
            select_bg = '#0078d7'
            select_fg = '#ffffff'
            cursor_color = '#000000'
            main_bg = '#f0f0f0'
            toolbar_bg = '#f5f5f5'
            status_bg = '#f0f0f0'
            button_bg = '#e0e0e0'
            button_fg = '#000000'
            menu_bg = '#ffffff'
            menu_fg = '#000000'
            border_color = '#cccccc'
            scrollbar_bg = '#f0f0f0'
            scrollbar_fg = '#c0c0c0'

        # Apply to tab bar
        self.tabbar.set_theme(theme)

        # Configure ttk styles for the theme
        style = ttk.Style()

        if theme == 'dark':
            # Configure dark theme styles
            style.configure('TFrame', background=main_bg)
            style.configure('TLabel', background=main_bg, foreground=editor_fg)
            style.configure('TButton', background=button_bg, foreground=button_fg)
            style.map('TButton',
                      background=[('active', '#4b5563'), ('pressed', '#1f2937')],
                      foreground=[('active', '#ffffff')])
            style.configure('TCheckbutton', background=main_bg, foreground=editor_fg)
            style.configure('TRadiobutton', background=main_bg, foreground=editor_fg)
            style.configure('TEntry', fieldbackground='#374151', foreground=editor_fg)
            style.configure('TSeparator', background=border_color)

            # Scrollbar styling for dark mode
            style.configure('Vertical.TScrollbar',
                           background=scrollbar_bg,
                           troughcolor=main_bg,
                           bordercolor=main_bg,
                           arrowcolor=scrollbar_fg)
            style.configure('Horizontal.TScrollbar',
                           background=scrollbar_bg,
                           troughcolor=main_bg,
                           bordercolor=main_bg,
                           arrowcolor=scrollbar_fg)
            style.map('Vertical.TScrollbar',
                     background=[('active', '#525252'), ('pressed', '#6b7280')])
            style.map('Horizontal.TScrollbar',
                     background=[('active', '#525252'), ('pressed', '#6b7280')])
        else:
            # Configure light theme styles
            style.configure('TFrame', background=main_bg)
            style.configure('TLabel', background=main_bg, foreground='#000000')
            style.configure('TButton', background=button_bg, foreground=button_fg)
            style.map('TButton',
                      background=[('active', '#d0d0d0'), ('pressed', '#c0c0c0')])
            style.configure('TCheckbutton', background=main_bg, foreground='#000000')
            style.configure('TRadiobutton', background=main_bg, foreground='#000000')
            style.configure('TEntry', fieldbackground='#ffffff', foreground='#000000')
            style.configure('TSeparator', background='#cccccc')

            style.configure('Vertical.TScrollbar',
                           background=scrollbar_bg,
                           troughcolor='#e0e0e0')
            style.configure('Horizontal.TScrollbar',
                           background=scrollbar_bg,
                           troughcolor='#e0e0e0')

        # Apply to all editors
        for tab in self.tabs.values():
            tab.editor.text.configure(
                bg=editor_bg,
                fg=editor_fg,
                insertbackground=cursor_color,
                selectbackground=select_bg,
                selectforeground=select_fg
            )
            tab.editor.line_numbers.configure(bg=line_num_bg)
            # Store theme colors for line numbers redraw
            tab.editor.line_numbers.fg_color = line_num_fg
            tab.editor.line_numbers.redraw()
            # Apply scrollbar theming
            tab.editor.v_scrollbar.configure(
                bg=scrollbar_fg,
                troughcolor=scrollbar_bg,
                activebackground='#6b7280' if theme == 'dark' else '#a0a0a0',
                highlightbackground=scrollbar_bg,
                highlightthickness=0,
                bd=0
            )
            tab.editor.h_scrollbar.configure(
                bg=scrollbar_fg,
                troughcolor=scrollbar_bg,
                activebackground='#6b7280' if theme == 'dark' else '#a0a0a0',
                highlightbackground=scrollbar_bg,
                highlightthickness=0,
                bd=0
            )

        # Apply to main window
        self.configure(bg=main_bg)

        # Apply to menu bar frame
        self.menubar.configure(bg=menu_bg)

        # Apply to menu buttons
        for mb in self.menu_buttons:
            mb.configure(
                bg=menu_bg,
                fg=menu_fg,
                activebackground=select_bg,
                activeforeground=select_fg,
                highlightbackground=menu_bg
            )

        # Style all dropdown menus
        for menu in self.menus.values():
            menu.configure(
                bg=menu_bg,
                fg=menu_fg,
                activebackground=select_bg,
                activeforeground=select_fg
            )

        # Apply to status bar
        self.statusbar.configure(bg=status_bg)
        self.status_text.configure(bg=status_bg, fg=editor_fg)
        self.tab_count_label.configure(bg=status_bg, fg=editor_fg)

        # Apply to toolbar - use grey hover colors instead of blue
        self.toolbar.configure(bg=toolbar_bg)
        if theme == 'dark':
            btn_active_bg = '#4b5563'  # Grey hover for dark mode
        else:
            btn_active_bg = '#c0c0c0'  # Grey hover for light mode

        for btn in self.toolbar_buttons:
            btn.configure(
                bg=button_bg,
                fg=button_fg,
                activebackground=btn_active_bg,
                activeforeground=button_fg,
                highlightbackground=toolbar_bg
            )
        # Update toolbar separators
        for child in self.toolbar.winfo_children():
            if isinstance(child, tk.Frame) and child not in []:
                # This is a separator frame
                if child.winfo_width() <= 5:  # separator is thin
                    child.configure(bg=border_color)

        # Apply to custom title bar
        self.titlebar.set_theme(theme)

        # Apply to resize grip and edges
        grip_color = '#1a1a1a' if theme == 'dark' else '#e0e0e0'
        self.resize_grip.configure(bg=grip_color)
        for edge in self._resize_edges.values():
            edge.configure(bg=main_bg)

    # Help

    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About",
            "FeatherPad v1.0.0\n\n"
            "A portable text editor with Notepad++ session recovery.\n\n"
            "Features:\n"
            "- Recover open tabs from Notepad++\n"
            "- Recover unsaved backup files\n"
            "- Full text editing capabilities\n"
            "- Find and Replace\n"
            "- Multiple tabs support\n\n"
            "Created to help users transition from Notepad++"
        )

    def show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """
Keyboard Shortcuts:

File:
  Ctrl+N         New file
  Ctrl+O         Open file
  Ctrl+S         Save
  Ctrl+Shift+S   Save As
  Ctrl+W         Close tab

Edit:
  Ctrl+Z         Undo
  Ctrl+Y         Redo
  Ctrl+A         Select All
  Ctrl+D         Duplicate line
  Ctrl+L         Delete line
  Ctrl+Shift+Up  Move line up
  Ctrl+Shift+Down Move line down

Search:
  Ctrl+F         Find
  Ctrl+H         Find & Replace
  Ctrl+G         Go to line

View:
  Ctrl++         Zoom in
  Ctrl+-         Zoom out
  Ctrl+0         Reset zoom

Navigation:
  Ctrl+Tab       Next tab
  Ctrl+Shift+Tab Previous tab
"""
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)

    def _save_current_session(self):
        """Save the current session state"""
        tabs_data = []
        for tab_id in self.tabbar.get_all_tabs():
            tab = self.tabs.get(tab_id)
            if tab:
                cursor_pos = tab.editor.text.index(tk.INSERT)
                first_visible = tab.editor.text.index("@0,0")
                tabs_data.append({
                    'filename': tab.filename,
                    'filepath': tab.filepath,
                    'content': tab.editor.get_content(),
                    'cursor_pos': cursor_pos,
                    'first_visible': first_visible,
                    'is_new': tab.is_new,
                    'modified': tab.modified,
                    'encoding': tab.encoding
                })

        active_index = 0
        current_id = self.tabbar.get_selected()
        if current_id:
            tab_ids = self.tabbar.get_all_tabs()
            if current_id in tab_ids:
                active_index = tab_ids.index(current_id)

        save_session(
            tabs_data,
            active_index,
            self.new_file_counter,
            self.geometry(),
            self.word_wrap_enabled,
            self.theme_var.get()
        )

    def _restore_session(self) -> bool:
        """Restore the previous session"""
        session_data = load_session()
        if not session_data or not session_data.get('tabs'):
            return False

        # Restore window geometry
        geometry = session_data.get('window_geometry')
        if geometry:
            try:
                self.geometry(geometry)
            except:
                pass

        # Restore word wrap state
        self.word_wrap_enabled = session_data.get('word_wrap_enabled', False)
        self.word_wrap_var.set(self.word_wrap_enabled)

        # Restore theme
        theme = session_data.get('theme', 'light')
        self.theme_var.set(theme)
        self._apply_theme()

        # Restore new file counter
        self.new_file_counter = session_data.get('new_file_counter', 1)

        # Restore tabs
        first_tab_id = None
        active_index = session_data.get('active_tab_index', 0)
        restored_tab_ids = []

        for tab_data in session_data.get('tabs', []):
            editor_frame = ttk.Frame(self.editor_container)
            editor = TextEditor(editor_frame)
            editor.pack(fill=tk.BOTH, expand=True)

            tab_id = f"tab_{id(editor)}"
            filename = tab_data.get('filename', 'untitled')

            tab = Tab(
                editor=editor,
                filepath=tab_data.get('filepath'),
                filename=filename,
                is_new=tab_data.get('is_new', True),
                modified=tab_data.get('modified', False),
                encoding=tab_data.get('encoding', 'utf-8')
            )

            self.tabs[tab_id] = tab
            self.editor_frames[tab_id] = editor_frame
            restored_tab_ids.append(tab_id)

            # Add to tab bar
            self.tabbar.add_tab(tab_id, filename, modified=tab.modified)

            if first_tab_id is None:
                first_tab_id = tab_id

            # Set content
            content = tab_data.get('content', '')
            editor.set_content(content)

            # Restore cursor position
            cursor_line = tab_data.get('cursor_line', 1)
            cursor_col = tab_data.get('cursor_col', 0)
            try:
                editor.text.mark_set(tk.INSERT, f"{cursor_line}.{cursor_col}")
            except:
                pass

            # Restore first visible line
            first_visible = tab_data.get('first_visible_line', 1)
            try:
                editor.text.yview(f"{first_visible}.0")
            except:
                pass

            # Set encoding
            editor.set_encoding(tab.encoding)

            # Apply word wrap if enabled
            if self.word_wrap_enabled:
                editor.set_word_wrap(True)

            # Mark as modified if it was modified
            if tab.modified:
                editor.modified = True

            # Set up modification callback
            def on_modified(t=tab, tid=tab_id):
                t.modified = True
                self._update_tab_title(tid)

            editor.set_on_modified(on_modified)

        # Select the active tab
        if restored_tab_ids:
            if 0 <= active_index < len(restored_tab_ids):
                self.tabbar.select(restored_tab_ids[active_index])
            elif first_tab_id:
                self.tabbar.select(first_tab_id)

        self._update_status()
        self.status_text.config(text=f"Restored {len(restored_tab_ids)} tabs from previous session")
        return len(restored_tab_ids) > 0

    def quit_app(self):
        """Quit application"""
        # Save session in a thread so it doesn't block the close
        import threading

        def save_and_exit():
            try:
                self._save_current_session()
            except Exception:
                pass
            # Force immediate termination - os._exit bypasses all Python cleanup
            os._exit(0)

        # Start save in background and exit immediately after a short delay
        save_thread = threading.Thread(target=save_and_exit, daemon=True)
        save_thread.start()

        # Hide window immediately for perceived faster close
        self.withdraw()

        # Give the save thread a moment, then force exit
        self.after(100, lambda: os._exit(0))


def main():
    """Main entry point"""
    app = FeatherPad()
    app.mainloop()


if __name__ == '__main__':
    main()
