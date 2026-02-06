"""
Custom Tab Bar for FeatherPad

A Notepad++-style tab bar with:
- Navigation arrows (first, previous, next, last)
- Close button (x) on each tab
- Double-click on empty space to create new tab
- Scrollable tabs
- Theme support (light/dark mode)
"""

import tkinter as tk
from tkinter import ttk, font
from typing import Callable, Optional, Dict, List


# Theme color definitions (Claude Code inspired dark theme)
THEMES = {
    'light': {
        'tab_bar_bg': '#e0e0e0',
        'tab_selected_bg': '#ffffff',
        'tab_selected_fg': '#000000',
        'tab_unselected_bg': '#c0c0c0',
        'tab_unselected_fg': '#666666',
        'close_btn_fg': '#cc0000',
        'close_btn_bg': '#d9d9d9',
        'close_btn_hover_bg': '#ffcccc',
        'close_btn_hover_fg': '#990000',
        'arrow_btn_bg': '#d0d0d0',
        'arrow_btn_fg': '#333333',
        'arrow_btn_active_bg': '#b0b0b0',
    },
    'dark': {
        'tab_bar_bg': '#1a1a1a',        # Very dark background
        'tab_selected_bg': '#2d2d2d',   # Selected tab slightly lighter
        'tab_selected_fg': '#e5e5e5',   # Light grey text
        'tab_unselected_bg': '#141414', # Darker unselected tabs
        'tab_unselected_fg': '#6b7280', # Muted grey text
        'close_btn_fg': '#ef4444',      # Red close button
        'close_btn_bg': '#2d2d2d',
        'close_btn_hover_bg': '#3f1f1f',
        'close_btn_hover_fg': '#ff6b6b',
        'arrow_btn_bg': '#2d2d2d',      # Arrow button background
        'arrow_btn_fg': '#9ca3af',      # Arrow button text
        'arrow_btn_active_bg': '#404040', # Arrow button hover
    }
}


class CustomTabBar(ttk.Frame):
    """
    Custom tab bar widget with Notepad++-style navigation
    """

    def __init__(self, parent, on_tab_select: Callable, on_tab_close: Callable,
                 on_new_tab: Callable, **kwargs):
        super().__init__(parent)

        self.on_tab_select = on_tab_select
        self.on_tab_close = on_tab_close
        self.on_new_tab = on_new_tab

        # Tab data: {tab_id: {'text': str, 'widget': Frame, 'modified': bool}}
        self.tabs: Dict[str, dict] = {}
        self.tab_order: List[str] = []  # Maintain tab order
        self.selected_tab: Optional[str] = None

        # Current theme
        self.current_theme = 'light'
        self.colors = THEMES['light']

        # Scroll position
        self.scroll_offset = 0
        self.visible_tabs_start = 0

        self._setup_ui()

    def set_theme(self, theme_name: str):
        """Set the current theme"""
        if theme_name in THEMES:
            self.current_theme = theme_name
            self.colors = THEMES[theme_name]
            self._apply_theme()

    def _apply_theme(self):
        """Apply the current theme to all UI elements"""
        # Update navigation frame
        self.nav_frame.configure(bg=self.colors['tab_bar_bg'])

        # Update arrow buttons
        for btn in self.arrow_buttons:
            btn.configure(
                bg=self.colors['arrow_btn_bg'],
                fg=self.colors['arrow_btn_fg'],
                activebackground=self.colors['arrow_btn_active_bg'],
                activeforeground=self.colors['arrow_btn_fg'],
                highlightbackground=self.colors['tab_bar_bg']
            )

        # Update separator
        self.separator.configure(bg=self.colors['tab_bar_bg'])

        # Update canvas and spacer background
        self.canvas.configure(bg=self.colors['tab_bar_bg'])
        self.spacer_frame.configure(bg=self.colors['tab_bar_bg'])

        # Update all tabs
        for tab_id, tab_data in self.tabs.items():
            self._style_tab(tab_id, is_selected=(tab_id == self.selected_tab))

    def _setup_ui(self):
        """Set up the tab bar UI"""
        # Navigation frame (left side with arrows) - use tk.Frame for full theme control
        self.nav_frame = tk.Frame(self, bg=self.colors['tab_bar_bg'])
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y)

        # Navigation buttons - use tk.Button for full theme control
        btn_style = {
            'width': 2,
            'relief': 'flat',
            'bd': 1,
            'bg': self.colors['arrow_btn_bg'],
            'fg': self.colors['arrow_btn_fg'],
            'activebackground': self.colors['arrow_btn_active_bg'],
            'activeforeground': self.colors['arrow_btn_fg'],
            'highlightthickness': 0
        }

        self.btn_first = tk.Button(self.nav_frame, text="|<", command=self._go_first, **btn_style)
        self.btn_first.pack(side=tk.LEFT, padx=1, pady=2)

        self.btn_prev = tk.Button(self.nav_frame, text="<", command=self._go_prev, **btn_style)
        self.btn_prev.pack(side=tk.LEFT, padx=1, pady=2)

        self.btn_next = tk.Button(self.nav_frame, text=">", command=self._go_next, **btn_style)
        self.btn_next.pack(side=tk.LEFT, padx=1, pady=2)

        self.btn_last = tk.Button(self.nav_frame, text=">|", command=self._go_last, **btn_style)
        self.btn_last.pack(side=tk.LEFT, padx=1, pady=2)

        # Store arrow buttons for theming
        self.arrow_buttons = [self.btn_first, self.btn_prev, self.btn_next, self.btn_last]

        # Separator
        self.separator = tk.Frame(self.nav_frame, width=2, bg=self.colors['tab_bar_bg'])
        self.separator.pack(side=tk.LEFT, fill=tk.Y, padx=3)

        # Tab container (scrollable area)
        self.tab_container = ttk.Frame(self)
        self.tab_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Canvas for scrolling tabs
        self.canvas = tk.Canvas(self.tab_container, height=28, highlightthickness=0,
                                bg='#e0e0e0')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Frame inside canvas to hold tabs
        self.tabs_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.tabs_frame,
                                                        anchor='nw')

        # Add a permanent spacer at the end for double-click new tab
        self.spacer_frame = tk.Frame(self.tabs_frame, width=100, height=24, bg='#e0e0e0')
        self.spacer_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.spacer_frame.pack_propagate(False)  # Maintain minimum width
        self.spacer_frame.bind('<Double-Button-1>', lambda e: self.on_new_tab())

        # Bind canvas events
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.tabs_frame.bind('<Configure>', self._on_tabs_configure)

        # Double-click on empty space creates new tab
        self.canvas.bind('<Double-Button-1>', self._on_canvas_double_click)

        # Mouse wheel scrolling
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.canvas.bind('<Button-4>', lambda e: self._scroll_tabs(-1))
        self.canvas.bind('<Button-5>', lambda e: self._scroll_tabs(1))

    def _on_canvas_configure(self, event):
        """Handle canvas resize"""
        self._update_scroll_region()

    def _on_tabs_configure(self, event):
        """Handle tabs frame resize"""
        self._update_scroll_region()

    def _update_scroll_region(self):
        """Update the canvas scroll region"""
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _on_canvas_double_click(self, event):
        """Handle double-click on canvas (empty space)"""
        # Check if click is on empty space (not on a tab)
        widget = event.widget.winfo_containing(event.x_root, event.y_root)
        if widget == self.canvas:
            self.on_new_tab()

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        if event.delta > 0:
            self._scroll_tabs(-1)
        else:
            self._scroll_tabs(1)

    def _scroll_tabs(self, direction):
        """Scroll tabs left (-1) or right (1)"""
        self.canvas.xview_scroll(direction, 'units')

    def _go_first(self):
        """Go to first tab"""
        if self.tab_order:
            self.select(self.tab_order[0])
            self.canvas.xview_moveto(0)

    def _go_prev(self):
        """Go to previous tab"""
        if self.selected_tab and self.tab_order:
            idx = self.tab_order.index(self.selected_tab)
            if idx > 0:
                self.select(self.tab_order[idx - 1])
                self._ensure_tab_visible(idx - 1)

    def _go_next(self):
        """Go to next tab"""
        if self.selected_tab and self.tab_order:
            idx = self.tab_order.index(self.selected_tab)
            if idx < len(self.tab_order) - 1:
                self.select(self.tab_order[idx + 1])
                self._ensure_tab_visible(idx + 1)

    def _go_last(self):
        """Go to last tab"""
        if self.tab_order:
            self.select(self.tab_order[-1])
            self.canvas.xview_moveto(1)

    def _ensure_tab_visible(self, index):
        """Ensure the tab at index is visible"""
        if not self.tab_order or index >= len(self.tab_order):
            return

        tab_id = self.tab_order[index]
        tab_data = self.tabs.get(tab_id)
        if not tab_data:
            return

        widget = tab_data['widget']
        widget.update_idletasks()

        # Get widget position relative to canvas
        tab_x = widget.winfo_x()
        tab_width = widget.winfo_width()
        canvas_width = self.canvas.winfo_width()

        # Get current scroll position
        scroll_region = self.canvas.bbox('all')
        if scroll_region:
            total_width = scroll_region[2] - scroll_region[0]
            if total_width > canvas_width:
                # Calculate scroll position to make tab visible
                xview = self.canvas.xview()
                visible_start = xview[0] * total_width
                visible_end = xview[1] * total_width

                if tab_x < visible_start:
                    # Scroll left
                    self.canvas.xview_moveto(tab_x / total_width)
                elif tab_x + tab_width > visible_end:
                    # Scroll right
                    new_pos = (tab_x + tab_width - canvas_width) / total_width
                    self.canvas.xview_moveto(new_pos)

    def add_tab(self, tab_id: str, text: str, modified: bool = False) -> str:
        """Add a new tab"""
        # Create tab frame - insert before spacer (use tk.Frame for better color control)
        tab_frame = tk.Frame(self.tabs_frame, relief='raised', borderwidth=1,
                             bg=self.colors['tab_unselected_bg'])
        tab_frame.pack(side=tk.LEFT, padx=1, pady=2, before=self.spacer_frame)

        # Icon label (file icon simulation)
        icon_label = tk.Label(tab_frame, text="\U0001F4C4", width=2,
                              bg=self.colors['tab_unselected_bg'],
                              fg=self.colors['tab_unselected_fg'])
        icon_label.pack(side=tk.LEFT, padx=(3, 0))

        # Text label
        display_text = f"*{text}" if modified else text
        text_label = tk.Label(tab_frame, text=display_text, padx=3, pady=2,
                              bg=self.colors['tab_unselected_bg'],
                              fg=self.colors['tab_unselected_fg'])
        text_label.pack(side=tk.LEFT)

        # Small red close button using tk.Label
        close_font = font.Font(size=8, weight='bold')
        close_btn = tk.Label(
            tab_frame,
            text="x",
            font=close_font,
            fg=self.colors['close_btn_fg'],
            bg=self.colors['tab_unselected_bg'],
            cursor='hand2',
            padx=2,
            pady=0
        )
        close_btn.pack(side=tk.LEFT, padx=(2, 3))

        # Bind close button events with theme-aware colors
        def on_close_enter(e):
            close_btn.configure(bg=self.colors['close_btn_hover_bg'],
                               fg=self.colors['close_btn_hover_fg'])

        def on_close_leave(e):
            is_sel = (tab_id == self.selected_tab)
            bg = self.colors['tab_selected_bg'] if is_sel else self.colors['tab_unselected_bg']
            close_btn.configure(bg=bg, fg=self.colors['close_btn_fg'])

        close_btn.bind('<Button-1>', lambda e, tid=tab_id: self.on_tab_close(tid))
        close_btn.bind('<Enter>', on_close_enter)
        close_btn.bind('<Leave>', on_close_leave)

        # Store tab data
        self.tabs[tab_id] = {
            'text': text,
            'widget': tab_frame,
            'text_label': text_label,
            'icon_label': icon_label,
            'close_btn': close_btn,
            'modified': modified
        }
        self.tab_order.append(tab_id)

        # Bind click events
        for widget in [tab_frame, icon_label, text_label]:
            widget.bind('<Button-1>', lambda e, tid=tab_id: self._on_tab_click(tid))
            widget.bind('<Button-2>', lambda e, tid=tab_id: self.on_tab_close(tid))  # Middle click
            widget.bind('<Button-3>', lambda e, tid=tab_id: self._on_tab_right_click(e, tid))

        self._update_scroll_region()

        # Auto-select if first tab
        if len(self.tabs) == 1:
            self.select(tab_id)
        else:
            # Style as unselected
            self._style_tab(tab_id, is_selected=False)

        return tab_id

    def _style_tab(self, tab_id: str, is_selected: bool):
        """Apply styling to a tab based on selection state"""
        if tab_id not in self.tabs:
            return

        tab_data = self.tabs[tab_id]

        if is_selected:
            bg = self.colors['tab_selected_bg']
            fg = self.colors['tab_selected_fg']
            relief = 'sunken'
        else:
            bg = self.colors['tab_unselected_bg']
            fg = self.colors['tab_unselected_fg']
            relief = 'raised'

        # Update tab frame
        tab_data['widget'].configure(bg=bg, relief=relief)

        # Update labels
        tab_data['text_label'].configure(bg=bg, fg=fg)
        tab_data['icon_label'].configure(bg=bg, fg=fg)
        tab_data['close_btn'].configure(bg=bg, fg=self.colors['close_btn_fg'])

    def remove_tab(self, tab_id: str):
        """Remove a tab"""
        if tab_id not in self.tabs:
            return

        tab_data = self.tabs[tab_id]
        tab_data['widget'].destroy()

        del self.tabs[tab_id]
        self.tab_order.remove(tab_id)

        # Select another tab if the removed tab was selected
        if self.selected_tab == tab_id:
            self.selected_tab = None
            if self.tab_order:
                self.select(self.tab_order[-1])

        self._update_scroll_region()

    def select(self, tab_id: str):
        """Select a tab"""
        if tab_id not in self.tabs:
            return

        # Deselect previous tab
        if self.selected_tab and self.selected_tab in self.tabs:
            self._style_tab(self.selected_tab, is_selected=False)

        # Select new tab
        self.selected_tab = tab_id
        self._style_tab(tab_id, is_selected=True)

        # Ensure visible
        idx = self.tab_order.index(tab_id)
        self._ensure_tab_visible(idx)

        # Notify callback
        self.on_tab_select(tab_id)

    def update_tab(self, tab_id: str, text: Optional[str] = None, modified: Optional[bool] = None):
        """Update tab text and/or modified state"""
        if tab_id not in self.tabs:
            return

        tab_data = self.tabs[tab_id]

        if text is not None:
            tab_data['text'] = text

        if modified is not None:
            tab_data['modified'] = modified

        # Update display
        display_text = tab_data['text']
        if tab_data['modified']:
            display_text = f"*{display_text}"

        tab_data['text_label'].configure(text=display_text)

    def get_selected(self) -> Optional[str]:
        """Get the currently selected tab ID"""
        return self.selected_tab

    def get_tab_index(self, tab_id: str) -> int:
        """Get the index of a tab"""
        if tab_id in self.tab_order:
            return self.tab_order.index(tab_id)
        return -1

    def get_all_tabs(self) -> List[str]:
        """Get all tab IDs in order"""
        return self.tab_order.copy()

    def _on_tab_click(self, tab_id: str):
        """Handle tab click"""
        self.select(tab_id)

    def _on_tab_right_click(self, event, tab_id: str):
        """Handle right-click on tab"""
        self.select(tab_id)
        # The main app will handle the context menu

    def tab_count(self) -> int:
        """Get number of tabs"""
        return len(self.tabs)
