"""
Session Manager for NotepadReplica

Handles saving and restoring application sessions, including:
- Open tabs and their content
- Cursor positions
- Unsaved file backups
"""

import os
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class TabState:
    """State of a single tab"""
    filename: str
    filepath: Optional[str]
    content_hash: str  # Hash of content for change detection
    cursor_line: int
    cursor_col: int
    first_visible_line: int
    is_new: bool
    modified: bool
    encoding: str
    backup_file: Optional[str]  # Path to temp backup file


@dataclass
class SessionState:
    """Complete session state"""
    tabs: List[TabState]
    active_tab_index: int
    new_file_counter: int
    window_geometry: str
    word_wrap_enabled: bool
    timestamp: str


def get_app_data_dir() -> Path:
    """Get the application data directory"""
    if os.name == 'nt':  # Windows
        base = os.environ.get('LOCALAPPDATA', os.environ.get('APPDATA', ''))
    else:  # Linux/Mac
        base = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))

    app_dir = Path(base) / 'NotepadReplica'
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_backup_dir() -> Path:
    """Get the backup directory for unsaved files"""
    backup_dir = get_app_data_dir() / 'backup'
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def get_session_file() -> Path:
    """Get the session file path"""
    return get_app_data_dir() / 'session.json'


def content_hash(content: str) -> str:
    """Generate a hash of content for change detection"""
    return hashlib.md5(content.encode('utf-8', errors='replace')).hexdigest()[:16]


def generate_backup_filename(tab_filename: str, tab_index: int) -> str:
    """Generate a unique backup filename"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = "".join(c if c.isalnum() or c in '._-' else '_' for c in tab_filename)
    return f"{safe_name}_{tab_index}_{timestamp}.backup"


def save_backup_content(content: str, backup_filename: str) -> str:
    """Save content to a backup file and return the path"""
    backup_path = get_backup_dir() / backup_filename
    try:
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return str(backup_path)
    except Exception as e:
        print(f"Warning: Could not save backup {backup_filename}: {e}")
        return ""


def load_backup_content(backup_path: str) -> Optional[str]:
    """Load content from a backup file"""
    try:
        if os.path.exists(backup_path):
            with open(backup_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        print(f"Warning: Could not load backup {backup_path}: {e}")
    return None


def cleanup_old_backups(max_age_days: int = 7):
    """Remove backup files older than max_age_days"""
    backup_dir = get_backup_dir()
    cutoff = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)

    try:
        for entry in backup_dir.iterdir():
            if entry.is_file() and entry.suffix == '.backup':
                if entry.stat().st_mtime < cutoff:
                    entry.unlink()
    except Exception as e:
        print(f"Warning: Error cleaning up backups: {e}")


def save_session(tabs_data: List[Dict], active_index: int, new_file_counter: int,
                 geometry: str, word_wrap: bool) -> bool:
    """
    Save the current session state.

    Args:
        tabs_data: List of dicts with tab info:
            - filename: str
            - filepath: Optional[str]
            - content: str
            - cursor_pos: str (e.g., "1.0")
            - first_visible: str
            - is_new: bool
            - modified: bool
            - encoding: str
        active_index: Index of the active tab
        new_file_counter: Counter for new file naming
        geometry: Window geometry string
        word_wrap: Word wrap state

    Returns:
        True if saved successfully
    """
    try:
        tab_states = []

        for i, tab in enumerate(tabs_data):
            content = tab.get('content', '')
            chash = content_hash(content)

            # Save backup for all tabs (so we can restore unsaved content)
            backup_filename = generate_backup_filename(tab['filename'], i)
            backup_path = save_backup_content(content, backup_filename)

            # Parse cursor position
            cursor_pos = tab.get('cursor_pos', '1.0')
            parts = cursor_pos.split('.')
            cursor_line = int(parts[0]) if parts else 1
            cursor_col = int(parts[1]) if len(parts) > 1 else 0

            # Parse first visible line
            first_visible = tab.get('first_visible', '1.0')
            first_line = int(first_visible.split('.')[0]) if first_visible else 1

            tab_state = TabState(
                filename=tab['filename'],
                filepath=tab.get('filepath'),
                content_hash=chash,
                cursor_line=cursor_line,
                cursor_col=cursor_col,
                first_visible_line=first_line,
                is_new=tab.get('is_new', True),
                modified=tab.get('modified', False),
                encoding=tab.get('encoding', 'utf-8'),
                backup_file=backup_path
            )
            tab_states.append(tab_state)

        session = SessionState(
            tabs=[asdict(t) for t in tab_states],
            active_tab_index=active_index,
            new_file_counter=new_file_counter,
            window_geometry=geometry,
            word_wrap_enabled=word_wrap,
            timestamp=datetime.now().isoformat()
        )

        session_file = get_session_file()
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(session), f, indent=2)

        return True

    except Exception as e:
        print(f"Error saving session: {e}")
        return False


def load_session() -> Optional[Dict]:
    """
    Load the previous session state.

    Returns:
        Dictionary with session data, or None if no session exists
    """
    session_file = get_session_file()

    if not session_file.exists():
        return None

    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)

        # Load content from backup files for each tab
        tabs_with_content = []
        for tab in session_data.get('tabs', []):
            tab_data = dict(tab)

            # Try to load from backup file first
            backup_path = tab.get('backup_file')
            if backup_path:
                content = load_backup_content(backup_path)
                if content is not None:
                    tab_data['content'] = content
                else:
                    # Fall back to original file if it exists
                    filepath = tab.get('filepath')
                    if filepath and os.path.exists(filepath):
                        try:
                            with open(filepath, 'r', encoding=tab.get('encoding', 'utf-8')) as f:
                                tab_data['content'] = f.read()
                        except:
                            tab_data['content'] = ''
                    else:
                        tab_data['content'] = ''
            else:
                tab_data['content'] = ''

            tabs_with_content.append(tab_data)

        session_data['tabs'] = tabs_with_content
        return session_data

    except Exception as e:
        print(f"Error loading session: {e}")
        return None


def clear_session():
    """Clear the saved session"""
    try:
        session_file = get_session_file()
        if session_file.exists():
            session_file.unlink()

        # Also clear backup files
        backup_dir = get_backup_dir()
        for entry in backup_dir.iterdir():
            if entry.is_file() and entry.suffix == '.backup':
                entry.unlink()
    except Exception as e:
        print(f"Error clearing session: {e}")
