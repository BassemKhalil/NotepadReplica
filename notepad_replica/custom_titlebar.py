"""
Custom Title Bar

A custom window title bar that supports full theming, including dark mode.
Replaces the system title bar to allow Claude Code inspired dark theme.
"""

import tkinter as tk
from tkinter import font


# Theme colors for title bar
TITLEBAR_THEMES = {
    'light': {
        'bg': '#e0e0e0',
        'fg': '#000000',
        'button_bg': '#e0e0e0',
        'button_fg': '#000000',
        'button_hover_bg': '#c0c0c0',
        'close_hover_bg': '#e81123',
        'close_hover_fg': '#ffffff',
        'border': '#cccccc',
    },
    'dark': {
        'bg': '#0d0d0d',           # Claude Code very dark
        'fg': '#e5e5e5',           # Light grey text
        'button_bg': '#0d0d0d',
        'button_fg': '#9ca3af',    # Muted grey for buttons
        'button_hover_bg': '#262626',
        'close_hover_bg': '#dc2626',
        'close_hover_fg': '#ffffff',
        'border': '#262626',
    }
}


class CustomTitleBar(tk.Frame):
    """Custom title bar with minimize, maximize, and close buttons"""

    def __init__(self, parent, title="FeatherPad", theme='light'):
        super().__init__(parent)
        self.parent = parent
        self.title_text = title
        self.theme = theme
        self.colors = TITLEBAR_THEMES[theme]

        # State for window dragging
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._maximized = False
        self._restore_geometry = None

        self._setup_ui()
        self._setup_bindings()

    def _setup_ui(self):
        """Set up the title bar UI"""
        self.configure(bg=self.colors['bg'], height=32)
        self.pack_propagate(False)

        # Left side: Icon and title
        left_frame = tk.Frame(self, bg=self.colors['bg'])
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))

        # App icon (simple feather-like symbol)
        icon_font = font.Font(family='Segoe UI', size=12)
        self.icon_label = tk.Label(
            left_frame,
            text="\u270E",  # Pencil symbol as placeholder
            font=icon_font,
            bg=self.colors['bg'],
            fg=self.colors['fg']
        )
        self.icon_label.pack(side=tk.LEFT, padx=(0, 8), pady=6)

        # Title
        title_font = font.Font(family='Segoe UI', size=9)
        self.title_label = tk.Label(
            left_frame,
            text=self.title_text,
            font=title_font,
            bg=self.colors['bg'],
            fg=self.colors['fg']
        )
        self.title_label.pack(side=tk.LEFT, pady=6)

        # Right side: Window control buttons
        right_frame = tk.Frame(self, bg=self.colors['bg'])
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # Button style
        btn_font = font.Font(family='Segoe MDL2 Assets', size=10)
        btn_width = 46
        btn_height = 32

        # Minimize button
        self.min_btn = tk.Label(
            right_frame,
            text="\u2500",  # Horizontal line
            font=btn_font,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            width=5,
            height=1,
            cursor='hand2'
        )
        self.min_btn.pack(side=tk.LEFT, fill=tk.Y)

        # Maximize button
        self.max_btn = tk.Label(
            right_frame,
            text="\u25A1",  # Square
            font=btn_font,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            width=5,
            height=1,
            cursor='hand2'
        )
        self.max_btn.pack(side=tk.LEFT, fill=tk.Y)

        # Close button
        self.close_btn = tk.Label(
            right_frame,
            text="\u2715",  # X mark
            font=btn_font,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            width=5,
            height=1,
            cursor='hand2'
        )
        self.close_btn.pack(side=tk.LEFT, fill=tk.Y)

        # Bottom border
        self.border = tk.Frame(self.parent, height=1, bg=self.colors['border'])

    def _setup_bindings(self):
        """Set up event bindings"""
        # Window dragging
        for widget in [self, self.title_label, self.icon_label]:
            widget.bind('<Button-1>', self._start_drag)
            widget.bind('<B1-Motion>', self._on_drag)
            widget.bind('<Double-Button-1>', self._toggle_maximize)

        # Button hover effects
        self.min_btn.bind('<Enter>', lambda e: self._on_button_hover(self.min_btn, True))
        self.min_btn.bind('<Leave>', lambda e: self._on_button_hover(self.min_btn, False))
        self.min_btn.bind('<Button-1>', self._minimize)

        self.max_btn.bind('<Enter>', lambda e: self._on_button_hover(self.max_btn, True))
        self.max_btn.bind('<Leave>', lambda e: self._on_button_hover(self.max_btn, False))
        self.max_btn.bind('<Button-1>', self._toggle_maximize)

        self.close_btn.bind('<Enter>', lambda e: self._on_button_hover(self.close_btn, True, is_close=True))
        self.close_btn.bind('<Leave>', lambda e: self._on_button_hover(self.close_btn, False, is_close=True))
        self.close_btn.bind('<Button-1>', self._close)

    def _on_button_hover(self, button, entering, is_close=False):
        """Handle button hover effects"""
        if entering:
            if is_close:
                button.configure(bg=self.colors['close_hover_bg'], fg=self.colors['close_hover_fg'])
            else:
                button.configure(bg=self.colors['button_hover_bg'])
        else:
            button.configure(bg=self.colors['button_bg'], fg=self.colors['button_fg'])

    def _start_drag(self, event):
        """Start window drag"""
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        """Handle window drag"""
        if self._maximized:
            # Restore window when dragging from maximized state
            self._restore_from_maximize(event)
            return

        x = self.parent.winfo_x() + (event.x - self._drag_start_x)
        y = self.parent.winfo_y() + (event.y - self._drag_start_y)
        self.parent.geometry(f'+{x}+{y}')

    def _restore_from_maximize(self, event):
        """Restore window when dragging from maximized state"""
        self._maximized = False
        self.max_btn.configure(text="\u25A1")

        # Calculate position to center window on cursor
        if self._restore_geometry:
            # Extract width and height from stored geometry
            geom = self._restore_geometry.split('+')[0]
            w, h = map(int, geom.split('x'))

            # Position window so cursor is at the center of title bar
            x = event.x_root - w // 2
            y = event.y_root - 16  # Half of title bar height

            self.parent.geometry(f'{w}x{h}+{x}+{y}')
            self._drag_start_x = w // 2
            self._drag_start_y = 16

    def _minimize(self, event=None):
        """Minimize window - use Windows API for overrideredirect windows"""
        try:
            import ctypes
            # Get the window handle
            hwnd = ctypes.windll.user32.GetParent(self.parent.winfo_id())
            # SW_MINIMIZE = 6
            ctypes.windll.user32.ShowWindow(hwnd, 6)
        except Exception:
            # Fallback for non-Windows
            self.parent.iconify()

    def _toggle_maximize(self, event=None):
        """Toggle maximize/restore"""
        if self._maximized:
            # Restore
            self._maximized = False
            self.max_btn.configure(text="\u25A1")
            if self._restore_geometry:
                self.parent.geometry(self._restore_geometry)
        else:
            # Maximize
            self._restore_geometry = self.parent.geometry()
            self._maximized = True
            self.max_btn.configure(text="\u25A3")  # Overlapping squares

            # Get screen dimensions
            screen_w = self.parent.winfo_screenwidth()
            screen_h = self.parent.winfo_screenheight()

            # Account for taskbar (roughly 40px)
            self.parent.geometry(f'{screen_w}x{screen_h - 40}+0+0')

    def _close(self, event=None):
        """Close window - calls parent's quit method"""
        if hasattr(self.parent, 'quit_app'):
            self.parent.quit_app()
        else:
            self.parent.destroy()

    def set_title(self, title):
        """Update the window title"""
        self.title_text = title
        self.title_label.configure(text=title)

    def set_theme(self, theme):
        """Apply theme to title bar"""
        self.theme = theme
        self.colors = TITLEBAR_THEMES[theme]

        # Update title bar background
        self.configure(bg=self.colors['bg'])

        # Update border
        self.border.configure(bg=self.colors['border'])

        # Update icon and title
        self.icon_label.configure(bg=self.colors['bg'], fg=self.colors['fg'])
        self.title_label.configure(bg=self.colors['bg'], fg=self.colors['fg'])

        # Update left frame
        for widget in self.winfo_children():
            if isinstance(widget, tk.Frame):
                widget.configure(bg=self.colors['bg'])
                for child in widget.winfo_children():
                    if isinstance(child, tk.Frame):
                        child.configure(bg=self.colors['bg'])

        # Update buttons
        self.min_btn.configure(bg=self.colors['button_bg'], fg=self.colors['button_fg'])
        self.max_btn.configure(bg=self.colors['button_bg'], fg=self.colors['button_fg'])
        self.close_btn.configure(bg=self.colors['button_bg'], fg=self.colors['button_fg'])

    def pack_border(self):
        """Pack the bottom border - call after packing title bar"""
        self.border.pack(side=tk.TOP, fill=tk.X)
