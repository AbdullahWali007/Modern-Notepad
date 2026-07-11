"""
Modern Notepad - Production Ready (Enhanced, Fixed)
A multi-tab text editor with persistent settings, undo/redo, find/replace,
and a clean MVC architecture. Uses global AppConfig with subscription pattern.
"""

import abc
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, List, Callable

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont

try:
    import pywinstyles
except ImportError:
    pywinstyles = None

try:
    import chardet
except ImportError:
    chardet = None

# ---------------------------- Logging Setup ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('ModernNotepad')


# ---------------------------- Settings Persistence ----------------------------
class SettingsManager:
    """Handles saving/loading user preferences to/from a JSON file."""

    CONFIG_DIR = Path.home() / '.config' / 'modern_notepad'
    CONFIG_FILE = CONFIG_DIR / 'settings.json'

    DEFAULT_SETTINGS = {
        'font_family': 'Segoe UI',
        'font_size': 12,
        'theme': 'dark',
        'window_width': 900,
        'window_height': 650,
    }

    def __init__(self):
        self._settings = self.DEFAULT_SETTINGS.copy()
        self._load()

    def _load(self):
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._settings.update(data)
            except Exception as e:
                logger.warning(f"Could not load settings: {e}")

    def save(self):
        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get(self, key: str, default=None):
        return self._settings.get(key, default)

    def set(self, key: str, value):
        self._settings[key] = value
        self.save()


# ---------------------------- Global App Configuration ----------------------------
class AppConfig:
    """
    Centralised configuration with subscriber notifications.
    All UI components that depend on font/theme should subscribe.
    """
    _settings_mgr = SettingsManager()

    font_family: str = _settings_mgr.get('font_family', 'Segoe UI') or 'Segoe UI'
    font_size: int = _settings_mgr.get('font_size', 12) or 12
    theme: str = _settings_mgr.get('theme', 'dark') or 'dark'

    _subscribers: List[Callable[[], None]] = []

    @classmethod
    def subscribe(cls, callback: Callable[[], None]):
        if callback not in cls._subscribers:
            cls._subscribers.append(callback)

    @classmethod
    def unsubscribe(cls, callback: Callable[[], None]):
        if callback in cls._subscribers:
            cls._subscribers.remove(callback)

    @classmethod
    def update_settings(cls, family: str, size: int, theme: str):
        cls.font_family = family
        cls.font_size = size
        cls.theme = theme

        # Apply theme globally
        ctk.set_appearance_mode("dark" if theme == "dark" else "light")

        # Persist
        cls._settings_mgr.set('font_family', family)
        cls._settings_mgr.set('font_size', size)
        cls._settings_mgr.set('theme', theme)

        # Notify all subscribers
        for callback in cls._subscribers:
            try:
                callback()
            except Exception as e:
                logger.error(f"Subscriber callback failed: {e}")

    @classmethod
    def load(cls):
        """Load saved settings on startup."""
        cls.font_family = str(cls._settings_mgr.get('font_family', 'Segoe UI') or 'Segoe UI')
        cls.font_size = int(cls._settings_mgr.get('font_size', 12) or 12)
        cls.theme = str(cls._settings_mgr.get('theme', 'dark') or 'dark')
        ctk.set_appearance_mode("dark" if cls.theme == "dark" else "light")


# ---------------------------- Model: Document ----------------------------
class Document:
    """Represents a text document with content, file path, and modified state."""

    def __init__(self, content: str = "", filepath: Optional[Path] = None):
        self._content = content
        self._filepath = filepath
        self._modified = False
        self._observers: List[Callable[[], None]] = []

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str):
        if self._content != value:
            self._content = value
            self.modified = True

    @property
    def filepath(self) -> Optional[Path]:
        return self._filepath

    @filepath.setter
    def filepath(self, value: Optional[Path]):
        self._filepath = value
        self._notify_observers()

    @property
    def modified(self) -> bool:
        return self._modified

    @modified.setter
    def modified(self, value: bool):
        if self._modified != value:
            self._modified = value
            self._notify_observers()

    def add_observer(self, callback: Callable[[], None]):
        self._observers.append(callback)

    def _notify_observers(self):
        for cb in self._observers:
            try:
                cb()
            except Exception as e:
                logger.error(f"Observer callback failed: {e}")

    def load_from_file(self, filepath: Path) -> str:
        """Load content from file with automatic encoding detection."""
        try:
            content = filepath.read_text(encoding='utf-8')
            self._content = content
            self._filepath = filepath
            self._modified = False
            self._notify_observers()
            return content
        except UnicodeDecodeError:
            if chardet:
                raw = filepath.read_bytes()
                result = chardet.detect(raw)
                detected_enc = result['encoding'] or 'utf-8'
                content = raw.decode(detected_enc, errors='replace')
                self._content = content
                self._filepath = filepath
                self._modified = False
                self._notify_observers()
                return content
            raise

    def save_to_file(self, filepath: Optional[Path] = None) -> bool:
        if filepath:
            self._filepath = filepath
        if not self._filepath:
            return False
        try:
            self._filepath.write_text(self._content, encoding='utf-8')
            self._modified = False
            self._notify_observers()
            return True
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise


# ---------------------------- View: Text Editor ----------------------------
class TextEditorView(ctk.CTkFrame):
    """Composite view: line numbers + text area, bound to a Document."""

    def __init__(self, parent, document: Document, **kwargs):
        super().__init__(parent, corner_radius=0, fg_color="transparent", **kwargs)
        self.document = document
        self._redraw_timer = None
        self.tab_update_callback: Optional[Callable[[], None]] = None

        # Line numbers canvas - width will be updated dynamically
        self.line_numbers = tk.Canvas(self, bg='#1a1a1a', highlightthickness=0)
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        # Text area
        self.text_area = ctk.CTkTextbox(
            self,
            wrap=tk.WORD,
            font=(AppConfig.font_family, AppConfig.font_size),
            undo=True,
            corner_radius=0
        )
        self.text_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._tk_text = self.text_area._textbox
        self._tk_text.configure(insertbackground='white', selectbackground='#3e3e3e')

        # Find/Replace highlight tags
        self._tk_text.tag_configure("find_highlight", background="#ffff00" if AppConfig.theme == "light" else "#4a4a00")
        self._tk_text.tag_configure("find_current", background="#ff9632" if AppConfig.theme == "light" else "#b85900")

        # Bind events
        self._tk_text.bind("<KeyRelease>", self._on_key_release)
        self._tk_text.bind("<MouseWheel>", self._schedule_redraw)
        self._tk_text.bind("<Button-1>", self._schedule_redraw)
        self._tk_text.bind("<Configure>", self._schedule_redraw)

        # Subscribe to global config changes
        AppConfig.subscribe(self._apply_config)
        self._apply_config()

        # Observe document changes for tab title updates
        self.document.add_observer(self._on_document_modified)

        # Set initial text
        self._set_text(self.document.content)

    def destroy(self):
        # Clean up timers and unbind events to prevent Tcl/Tk crashes
        if self._redraw_timer:
            self.after_cancel(self._redraw_timer)
            self._redraw_timer = None
        AppConfig.unsubscribe(self._apply_config)
        # Unbind all events from _tk_text
        for event in ("<KeyRelease>", "<MouseWheel>", "<Button-1>", "<Configure>"):
            try:
                self._tk_text.unbind(event)
            except tk.TclError:
                pass
        # Destroy the text widget and canvas explicitly
        self.text_area.destroy()
        self.line_numbers.destroy()
        super().destroy()

    # ---------- Configuration ----------
    def _apply_config(self):
        """Apply current font and theme from AppConfig."""
        self.text_area.configure(font=(AppConfig.font_family, AppConfig.font_size))
        if AppConfig.theme == "dark":
            self.text_area.configure(fg_color='#242424', text_color='#ffffff')
            self._tk_text.configure(insertbackground='white', selectbackground='#3e3e3e')
            self.line_numbers.config(bg='#1a1a1a')
            self._tk_text.tag_configure("find_highlight", background="#4a4a00")
            self._tk_text.tag_configure("find_current", background="#b85900")
        else:
            self.text_area.configure(fg_color='#ffffff', text_color='#000000')
            self._tk_text.configure(insertbackground='black', selectbackground='#d4d4d4')
            self.line_numbers.config(bg='#f0f0f0')
            self._tk_text.tag_configure("find_highlight", background="#ffff00")
            self._tk_text.tag_configure("find_current", background="#ff9632")
        self._update_line_numbers_width()
        self._schedule_redraw()

    # ---------- Line Numbers ----------
    def _update_line_numbers_width(self):
        """Adjust canvas width based on number of lines and font size."""
        font = self.text_area.cget("font")
        try:
            line_count = int(self._tk_text.index("end-1c").split(".")[0])
        except tk.TclError:
            line_count = 1
        sample = str(line_count)
        tk_font = tkfont.Font(font=font)
        width = tk_font.measure(sample) + 15
        width = max(width, 30)
        self.line_numbers.config(width=width)

    def _schedule_redraw(self, event=None):
        if self._redraw_timer:
            self.after_cancel(self._redraw_timer)
        self._redraw_timer = self.after(100, self._draw_line_numbers)

    def _draw_line_numbers(self):
        self.line_numbers.delete("all")
        if not self._tk_text.winfo_exists():
            return
        i = self._tk_text.index("@0,0")
        text_color = "#666666" if AppConfig.theme == "light" else "#888888"
        font = self.text_area.cget("font")
        canvas_width = self.line_numbers.winfo_width()

        while True:
            dline = self._tk_text.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = i.split(".")[0]
            self.line_numbers.create_text(
                canvas_width - 5, y,
                anchor="ne", text=linenum,
                fill=text_color, font=font
            )
            i = self._tk_text.index(f"{i}+1line")
        self._redraw_timer = None

    # ---------- Content & Modification ----------
    def _on_key_release(self, event=None):
        self._schedule_redraw()
        ignore_keys = {"Up", "Down", "Left", "Right", "Shift_L", "Shift_R",
                       "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock"}
        if event and event.keysym not in ignore_keys:
            self.document.content = self._get_text()
            # If a find dialog is open, we might want to refresh highlights
            self._refresh_find_highlights()

    def _refresh_find_highlights(self):
        """Called when content changes; informs the find dialog to update."""
        # We'll use a global reference if needed; for now, we'll let the find dialog handle it.
        pass

    def _on_document_modified(self):
        if self.tab_update_callback:
            self.tab_update_callback()

    def _get_text(self) -> str:
        return self.text_area.get("1.0", "end-1c")

    def _set_text(self, text: str, reset_undo: bool = True):
        """Replace entire content and optionally reset the undo stack."""
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", text)
        if reset_undo:
            self._tk_text.edit_reset()  # Makes the current state the base for undo
        self._schedule_redraw()

    def get_text(self) -> str:
        return self._get_text()

    def set_text(self, text: str):
        self._set_text(text, reset_undo=True)
        self.document.content = text

    def clear(self):
        self._set_text("", reset_undo=True)
        self.document.content = ""

    def load_from_file(self, filepath: Path) -> bool:
        try:
            content = self.document.load_from_file(filepath)
            self._set_text(content, reset_undo=True)
            return True
        except Exception as e:
            messagebox.showerror("Open Error", f"Failed to open file:\n{str(e)}")
            return False

    def save_to_file(self, filepath: Optional[Path] = None) -> bool:
        try:
            self.document.content = self._get_text()
            return self.document.save_to_file(filepath)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save file:\n{str(e)}")
            return False

    def focus(self):
        self.text_area.focus_set()

    # ---------- Find / Replace helpers ----------
    def clear_find_highlights(self):
        """Remove all find-related tags."""
        self._tk_text.tag_remove("find_highlight", "1.0", tk.END)
        self._tk_text.tag_remove("find_current", "1.0", tk.END)

    def highlight_all(self, pattern, case_sensitive=False, whole_word=False, regex=False):
        """Highlight all matches of pattern in the text.
        Returns the number of matches found.
        """
        self.clear_find_highlights()
        matches = self._get_matches(pattern, case_sensitive, whole_word, regex)
        for start, end in matches:
            self._tk_text.tag_add("find_highlight", f"1.0+{start}c", f"1.0+{end}c")
        return len(matches)

    def find_next(self, pattern, case_sensitive=False, whole_word=False, regex=False):
        """Find next occurrence and highlight it, return (start_index, end_index) or None."""
        start = self._tk_text.index(tk.INSERT)
        if self._tk_text.tag_ranges(tk.SEL):
            start = self._tk_text.index(tk.SEL_LAST)

        if regex:
            # Use _get_matches to get all matches and find the first one after cursor
            matches = self._get_matches(pattern, case_sensitive, whole_word, regex)
            for match_start, match_end in matches:
                tk_start = f"1.0+{match_start}c"
                if self._tk_text.compare(tk_start, ">=", start):
                    self._select_and_highlight(match_start, match_end)
                    return (match_start, match_end)
            # If none found after cursor, wrap to start
            for match_start, match_end in matches:
                tk_start = f"1.0+{match_start}c"
                if self._tk_text.compare(tk_start, ">=", "1.0"):
                    self._select_and_highlight(match_start, match_end)
                    return (match_start, match_end)
            return None
        else:
            # Plain text search (incremental)
            query = pattern
            if not query:
                return None
            pos = self._tk_text.search(query, start, stopindex=tk.END,
                                       nocase=not case_sensitive, regexp=False)
            if pos:
                end = f"{pos}+{len(query)}c"
                if whole_word:
                    # Check boundaries
                    before = self._tk_text.get(f"{pos}-1c", pos)
                    after = self._tk_text.get(end, f"{end}+1c")
                    if (before and before.isalnum()) or (after and after.isalnum()):
                        # Not a whole word, continue search from end
                        self._tk_text.mark_set(tk.INSERT, end)
                        return self.find_next(pattern, case_sensitive, whole_word, regex)
                self._select_and_highlight_pos(pos, end)
                return (pos, end)
            return None

    def _select_and_highlight(self, start_offset, end_offset):
        start = f"1.0+{start_offset}c"
        end = f"1.0+{end_offset}c"
        self._select_and_highlight_pos(start, end)

    def _select_and_highlight_pos(self, start, end):
        self._tk_text.tag_remove("find_current", "1.0", tk.END)
        self._tk_text.tag_add("find_current", start, end)
        self._tk_text.tag_add(tk.SEL, start, end)
        self._tk_text.mark_set(tk.INSERT, end)
        self._tk_text.see(tk.INSERT)

    def _get_matches(self, pattern, case_sensitive, whole_word, regex):
        """Return list of (start, end) offsets for all matches.
        Handles whole_word for both plain text and regex by checking boundaries.
        """
        content = self._get_text()
        if not content or not pattern:
            return []

        if regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                compiled = re.compile(pattern, flags)
                matches = [(m.start(), m.end()) for m in compiled.finditer(content)]
            except re.error:
                return []
        else:
            query = pattern
            if not case_sensitive:
                query = query.lower()
                content_lower = content.lower()
            else:
                content_lower = content
            matches = []
            start = 0
            while True:
                pos = content_lower.find(query, start)
                if pos == -1:
                    break
                end = pos + len(query)
                matches.append((pos, end))
                start = end

        # Apply whole-word filtering if required
        if whole_word:
            filtered = []
            for start, end in matches:
                # Check boundaries
                before = content[start-1] if start > 0 else ''
                after = content[end] if end < len(content) else ''
                if (not before.isalnum()) and (not after.isalnum()):
                    filtered.append((start, end))
            return filtered
        return matches


# ---------------------------- View: Tab Panel ----------------------------
class TabbedPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self._views: List[ctk.CTkFrame] = []

        # Style the notebook
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background='#1a1a1a', borderwidth=0)
        style.configure('TNotebook.Tab', background='#242424', foreground='#a0a0a0', padding=[15,5], borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', '#333333')], foreground=[('selected', '#ffffff')])

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, event=None):
        current = self.get_current_tab()
        if isinstance(current, TextEditorView):
            current._schedule_redraw()

    def add_tab(self, view: ctk.CTkFrame, title: str):
        self._views.append(view)
        self.notebook.add(view, text=title)
        if isinstance(view, TextEditorView):
            view.tab_update_callback = lambda: self._update_tab_title(view)
        self.notebook.select(view)

    def remove_tab(self, view: ctk.CTkFrame):
        if view in self._views:
            try:
                idx = self.notebook.index(view)
            except tk.TclError:
                idx = None
            if idx is not None:
                self.notebook.forget(idx)
            self._views.remove(view)
            view.destroy()

    def get_current_tab(self):
        try:
            current_widget = self.notebook.select()
            if not current_widget:
                return None
            for view in self._views:
                if str(view) == current_widget:
                    return view
            return None
        except tk.TclError:
            return None

    def _update_tab_title(self, view: TextEditorView):
        try:
            title = view.document.filepath.name if view.document.filepath else "New Tab"
            if view.document.modified:
                title += " *"
            self.notebook.tab(view, text=title)
        except tk.TclError:
            pass


# ---------------------------- View: Settings Panel ----------------------------
class SettingsView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._setup_ui()

    def _setup_ui(self):
        inner = ctk.CTkFrame(self, corner_radius=10, fg_color="#242424")
        inner.pack(pady=40, padx=40, fill=tk.BOTH, expand=True)

        ctk.CTkLabel(inner, text="Font Family:", font=("Segoe UI", 14)).grid(row=0, column=0, sticky="w", padx=20, pady=(20,10))
        self.font_family_var = ctk.StringVar(value=AppConfig.font_family)
        ctk.CTkOptionMenu(inner, variable=self.font_family_var,
                          values=["Segoe UI", "Arial", "Courier New", "Times New Roman", "Consolas"]).grid(row=0, column=1, sticky="ew", padx=20, pady=(20,10))

        ctk.CTkLabel(inner, text="Font Size:", font=("Segoe UI", 14)).grid(row=1, column=0, sticky="w", padx=20, pady=10)
        self.font_size_var = ctk.StringVar(value=str(AppConfig.font_size))
        ctk.CTkOptionMenu(inner, variable=self.font_size_var,
                          values=["8","10","12","14","16","18","20","24","28","36"]).grid(row=1, column=1, sticky="ew", padx=20, pady=10)

        ctk.CTkLabel(inner, text="Theme:", font=("Segoe UI", 14)).grid(row=2, column=0, sticky="w", padx=20, pady=10)
        self.theme_var = ctk.StringVar(value=AppConfig.theme.capitalize())
        ctk.CTkOptionMenu(inner, variable=self.theme_var, values=["Dark", "Light"]).grid(row=2, column=1, sticky="ew", padx=20, pady=10)

        ctk.CTkButton(inner, text="Apply Settings", command=self._apply, height=35).grid(row=3, column=0, columnspan=2, pady=30)
        inner.columnconfigure(1, weight=1)

    def _apply(self):
        family = self.font_family_var.get()
        try:
            size = int(self.font_size_var.get())
            if size < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Font size must be a positive integer.")
            return
        theme = self.theme_var.get().lower()
        AppConfig.update_settings(family, size, theme)


# ---------------------------- View: About Panel ----------------------------
class AboutView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        inner = ctk.CTkFrame(self, corner_radius=10, fg_color="#242424")
        inner.pack(pady=40, padx=40, fill=tk.BOTH, expand=True)
        ctk.CTkLabel(inner, text="Modern Notepad", font=("Segoe UI", 24, "bold")).pack(pady=(30,10))
        ctk.CTkLabel(inner, text="Version 3.2\n\nA modern text editor with persistent settings,\nundo/redo, line numbers, and a clean architecture.\n\nBuilt with Python and CustomTkinter",
                     font=("Segoe UI", 14), justify="center").pack(pady=10)
        ctk.CTkLabel(inner, text="© 2026 M. Abdullah Wali", font=("Segoe UI", 12), text_color="gray").pack(pady=30)


# ---------------------------- View: Find/Replace Dialog ----------------------------
class FindReplaceDialog(ctk.CTkToplevel):
    """Modeless find/replace dialog with VS Code style features."""

    def __init__(self, master, editor: TextEditorView):
        super().__init__(master)
        self.editor = editor
        self.title("Find and Replace")
        self.geometry("500x200")
        self.resizable(False, False)
        self.transient(master)
        self.attributes('-topmost', True)
        if pywinstyles:
            try:
                pywinstyles.apply_style(self, "mica")
            except:
                pass

        self.case_sensitive = tk.BooleanVar(value=False)
        self.whole_word = tk.BooleanVar(value=False)
        self.use_regex = tk.BooleanVar(value=False)

        self._create_widgets()
        self._bind_shortcuts()
        self._update_highlights()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Find row
        find_label = ctk.CTkLabel(main_frame, text="Find:", font=("Segoe UI", 12))
        find_label.grid(row=0, column=0, sticky="w", padx=(0,5), pady=5)
        self.find_entry = ctk.CTkEntry(main_frame, width=300)
        self.find_entry.grid(row=0, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        self.find_entry.bind("<KeyRelease>", self._on_find_change)

        # Replace row
        replace_label = ctk.CTkLabel(main_frame, text="Replace:", font=("Segoe UI", 12))
        replace_label.grid(row=1, column=0, sticky="w", padx=(0,5), pady=5)
        self.replace_entry = ctk.CTkEntry(main_frame, width=300)
        self.replace_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        # Buttons row
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=4, pady=10, sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)
        btn_frame.columnconfigure(3, weight=1)

        ctk.CTkButton(btn_frame, text="Find Next", command=self._find_next, width=90).grid(row=0, column=0, padx=2)
        ctk.CTkButton(btn_frame, text="Find Prev", command=self._find_prev, width=90).grid(row=0, column=1, padx=2)
        ctk.CTkButton(btn_frame, text="Replace", command=self._replace, width=90).grid(row=0, column=2, padx=2)
        ctk.CTkButton(btn_frame, text="Replace All", command=self._replace_all, width=90).grid(row=0, column=3, padx=2)

        # Options row
        opt_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        opt_frame.grid(row=3, column=0, columnspan=4, pady=5, sticky="w")
        ctk.CTkCheckBox(opt_frame, text="Match Case", variable=self.case_sensitive, command=self._update_highlights).pack(side=tk.LEFT, padx=5)
        ctk.CTkCheckBox(opt_frame, text="Whole Word", variable=self.whole_word, command=self._update_highlights).pack(side=tk.LEFT, padx=5)
        ctk.CTkCheckBox(opt_frame, text="Regex", variable=self.use_regex, command=self._update_highlights).pack(side=tk.LEFT, padx=5)

        # Status label (match count)
        self.status_label = ctk.CTkLabel(main_frame, text="", font=("Segoe UI", 10))
        self.status_label.grid(row=4, column=0, columnspan=4, sticky="w", pady=2)

        # Configure column weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)

    def _bind_shortcuts(self):
        self.bind("<Return>", lambda e: self._find_next())
        self.bind("<Shift-Return>", lambda e: self._find_prev())
        self.find_entry.bind("<Control-a>", lambda e: self.find_entry.select_range(0, tk.END))
        self.replace_entry.bind("<Control-a>", lambda e: self.replace_entry.select_range(0, tk.END))

    def _on_find_change(self, event=None):
        self._update_highlights()

    def _update_highlights(self):
        """Update all highlights and status."""
        if not self.editor:
            return
        pattern = self.find_entry.get()
        if not pattern:
            self.editor.clear_find_highlights()
            self.status_label.configure(text="")
            return
        case = self.case_sensitive.get()
        whole = self.whole_word.get()
        regex = self.use_regex.get()
        count = self.editor.highlight_all(pattern, case, whole, regex)
        self.status_label.configure(text=f"{count} match(es)")

    def _find_next(self):
        if not self.editor:
            return
        pattern = self.find_entry.get()
        if not pattern:
            return
        case = self.case_sensitive.get()
        whole = self.whole_word.get()
        regex = self.use_regex.get()
        result = self.editor.find_next(pattern, case, whole, regex)
        if result is None:
            # Wrap around?
            # Go to start and try again
            self.editor._tk_text.mark_set(tk.INSERT, "1.0")
            result = self.editor.find_next(pattern, case, whole, regex)
            if result is None:
                self.status_label.configure(text="No more matches")
                return
        # Update status
        self._update_highlights()  # refresh count

    def _find_prev(self):
        if not self.editor:
            return
        pattern = self.find_entry.get()
        if not pattern:
            return
        case = self.case_sensitive.get()
        whole = self.whole_word.get()
        regex = self.use_regex.get()
        matches = self.editor._get_matches(pattern, case, whole, regex)
        if not matches:
            self.status_label.configure(text="No matches")
            return
        cursor = self.editor._tk_text.index(tk.INSERT)
        # Find the match with largest start < cursor
        selected_match = None
        for start, end in matches:
            tk_start = f"1.0+{start}c"
            if self.editor._tk_text.compare(tk_start, "<", cursor):
                selected_match = (start, end)
        if selected_match is None:
            # Wrap to end (take last match)
            if matches:
                selected_match = matches[-1]
        if selected_match:
            self.editor._select_and_highlight(selected_match[0], selected_match[1])
            self.editor._tk_text.mark_set(tk.INSERT, f"1.0+{selected_match[0]}c")
            self.editor._tk_text.see(tk.INSERT)
            self._update_highlights()

    def _replace(self):
        if not self.editor:
            return
        pattern = self.find_entry.get()
        if not pattern:
            return
        replacement = self.replace_entry.get()
        case = self.case_sensitive.get()
        whole = self.whole_word.get()
        regex = self.use_regex.get()

        # Check if there is a selection and it matches the current find pattern
        if self.editor._tk_text.tag_ranges(tk.SEL):
            sel_start = self.editor._tk_text.index(tk.SEL_FIRST)
            sel_end = self.editor._tk_text.index(tk.SEL_LAST)
            matches = self.editor._get_matches(pattern, case, whole, regex)
            for match_start, match_end in matches:
                tk_start = f"1.0+{match_start}c"
                tk_end = f"1.0+{match_end}c"
                if self.editor._tk_text.compare(tk_start, "==", sel_start) and self.editor._tk_text.compare(tk_end, "==", sel_end):
                    # Replace the selection
                    self.editor._tk_text.delete(tk.SEL_FIRST, tk.SEL_LAST)
                    self.editor._tk_text.insert(tk.INSERT, replacement)
                    # Sync document content
                    self.editor.document.content = self.editor._get_text()
                    self._update_highlights()
                    return
        # If no matching selection, do find next and then replace
        self._find_next()
        if self.editor._tk_text.tag_ranges(tk.SEL):
            self.editor._tk_text.delete(tk.SEL_FIRST, tk.SEL_LAST)
            self.editor._tk_text.insert(tk.INSERT, replacement)
            self.editor.document.content = self.editor._get_text()
            self._update_highlights()

    def _replace_all(self):
        if not self.editor:
            return
        pattern = self.find_entry.get()
        if not pattern:
            return
        replacement = self.replace_entry.get()
        case = self.case_sensitive.get()
        whole = self.whole_word.get()
        regex = self.use_regex.get()

        content = self.editor._get_text()
        if not content:
            return

        matches = self.editor._get_matches(pattern, case, whole, regex)
        if not matches:
            self.status_label.configure(text="No matches to replace")
            return

        # Replace from end to start to avoid offset shifting
        new_content = content
        offset = 0
        for start, end in matches:
            actual_start = start + offset
            actual_end = end + offset
            new_content = new_content[:actual_start] + replacement + new_content[actual_end:]
            offset += len(replacement) - (end - start)

        if new_content != content:
            self.editor.set_text(new_content)
            self._update_highlights()
            self.status_label.configure(text=f"Replaced {len(matches)} occurrence(s)")

    def _on_close(self):
        if self.editor:
            self.editor.clear_find_highlights()
        self.destroy()


# ---------------------------- Controller: ModernNotepad ----------------------------
class ModernNotepad:
    def __init__(self):
        AppConfig.load()

        self.root = ctk.CTk()
        self.root.title("Modern Notepad")
        width = AppConfig._settings_mgr.get('window_width', 900)
        height = AppConfig._settings_mgr.get('window_height', 650)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(600, 400)

        if pywinstyles:
            try:
                pywinstyles.apply_style(self.root, "mica")
            except Exception as e:
                logger.debug(f"Window style skipped: {e}")

        self.is_mac = sys.platform == "darwin"
        self.ctrl_cmd = "Cmd" if self.is_mac else "Ctrl"
        self.ctrl_key = "Command" if self.is_mac else "Control"

        # Status bar
        self.status_bar = ctk.CTkLabel(self.root, text="Ready", anchor="w", fg_color="#1a1a1a", height=25, padx=10)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Tab panel
        self.tab_panel = TabbedPanel(self.root)
        self.tab_panel.pack(fill=tk.BOTH, expand=True)

        # Create initial tab
        self._new_tab()

        # Build menu and toolbar
        self._create_menu()
        self._create_toolbar()
        self._bind_shortcuts()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._find_dialog = None  # reference to find dialog

    # ---------- UI Creation ----------
    def _create_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self._new_tab, accelerator=f"{self.ctrl_cmd}+N")
        file_menu.add_command(label="Open", command=self._open_file, accelerator=f"{self.ctrl_cmd}+O")
        file_menu.add_command(label="Save", command=self._save_file, accelerator=f"{self.ctrl_cmd}+S")
        file_menu.add_command(label="Save As...", command=self._save_as_file)
        file_menu.add_command(label="Close Tab", command=self._close_current_tab, accelerator=f"{self.ctrl_cmd}+W")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self._undo, accelerator=f"{self.ctrl_cmd}+Z")
        edit_menu.add_command(label="Redo", command=self._redo, accelerator=f"{self.ctrl_cmd}+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=self._cut, accelerator=f"{self.ctrl_cmd}+X")
        edit_menu.add_command(label="Copy", command=self._copy, accelerator=f"{self.ctrl_cmd}+C")
        edit_menu.add_command(label="Paste", command=self._paste, accelerator=f"{self.ctrl_cmd}+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Find/Replace", command=self._show_find_replace, accelerator=f"{self.ctrl_cmd}+F")
        edit_menu.add_command(label="Select All", command=self._select_all, accelerator=f"{self.ctrl_cmd}+A")
        edit_menu.add_command(label="Settings", command=self._open_settings_tab)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Zoom In", command=self._zoom_in, accelerator=f"{self.ctrl_cmd}++")
        view_menu.add_command(label="Zoom Out", command=self._zoom_out, accelerator=f"{self.ctrl_cmd}+-")
        view_menu.add_command(label="Reset Zoom", command=self._reset_zoom, accelerator=f"{self.ctrl_cmd}+0")
        menubar.add_cascade(label="View", menu=view_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Typing Speed Check", command=self._show_typing_speed)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _create_toolbar(self):
        toolbar = ctk.CTkFrame(self.root, height=45, corner_radius=0, fg_color="#1a1a1a")
        toolbar.pack(side=tk.TOP, fill=tk.X)

        btn_kwargs = {"width": 60, "height": 28, "fg_color": "transparent",
                      "hover_color": "#333333", "text_color": "#ffffff"}

        ctk.CTkButton(toolbar, text="New", command=self._new_tab, **btn_kwargs).pack(side=tk.LEFT, padx=(10,2), pady=5)
        ctk.CTkButton(toolbar, text="Open", command=self._open_file, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)
        ctk.CTkButton(toolbar, text="Save", command=self._save_file, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)

        ctk.CTkFrame(toolbar, width=2, height=20, fg_color="#333333").pack(side=tk.LEFT, padx=10, pady=10)
        ctk.CTkButton(toolbar, text="Cut", command=self._cut, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)
        ctk.CTkButton(toolbar, text="Copy", command=self._copy, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)
        ctk.CTkButton(toolbar, text="Paste", command=self._paste, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)

        ctk.CTkFrame(toolbar, width=2, height=20, fg_color="#333333").pack(side=tk.LEFT, padx=10, pady=10)
        ctk.CTkButton(toolbar, text="Find", command=self._show_find_replace, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)
        ctk.CTkButton(toolbar, text="Close Tab", command=self._close_current_tab, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)

    def _bind_shortcuts(self):
        bindings = {
            f"<{self.ctrl_key}-n>": self._new_tab,
            f"<{self.ctrl_key}-o>": self._open_file,
            f"<{self.ctrl_key}-s>": self._save_file,
            f"<{self.ctrl_key}-w>": self._close_current_tab,
            f"<{self.ctrl_key}-f>": self._show_find_replace,
            f"<{self.ctrl_key}-x>": self._cut,
            f"<{self.ctrl_key}-c>": self._copy,
            f"<{self.ctrl_key}-v>": self._paste,
            f"<{self.ctrl_key}-a>": self._select_all,
            f"<{self.ctrl_key}-z>": self._undo,
            f"<{self.ctrl_key}-y>": self._redo,
            f"<{self.ctrl_key}-plus>": self._zoom_in,
            f"<{self.ctrl_key}-equal>": self._zoom_in,
            f"<{self.ctrl_key}-minus>": self._zoom_out,
            f"<{self.ctrl_key}-0>": self._reset_zoom,
        }
        for event, func in bindings.items():
            self.root.bind(event, lambda e, f=func: f())

    # ---------- Helpers ----------
    def _get_current_editor(self) -> Optional[TextEditorView]:
        tab = self.tab_panel.get_current_tab()
        return tab if isinstance(tab, TextEditorView) else None

    def _update_status(self, msg: str):
        self.status_bar.configure(text=msg)

    # ---------- Tab Management ----------
    def _new_tab(self):
        doc = Document()
        editor = TextEditorView(self.tab_panel.notebook, doc)
        self.tab_panel.add_tab(editor, "New Tab")
        editor.focus()
        self._update_status("New tab created")
        return editor

    def _close_current_tab(self):
        tab = self.tab_panel.get_current_tab()
        if not tab:
            return
        if isinstance(tab, TextEditorView) and tab.document.modified:
            name = tab.document.filepath.name if tab.document.filepath else "New Tab"
            response = messagebox.askyesnocancel("Unsaved Changes", f"Save changes to {name}?")
            if response is True:
                if not self._save_file():
                    return
            elif response is None:
                return
        self.tab_panel.remove_tab(tab)
        self._update_status("Tab closed")
        if not any(isinstance(v, TextEditorView) for v in self.tab_panel._views):
            self._new_tab()

    def _on_closing(self):
        AppConfig._settings_mgr.set('window_width', self.root.winfo_width())
        AppConfig._settings_mgr.set('window_height', self.root.winfo_height())

        for view in self.tab_panel._views[:]:
            if isinstance(view, TextEditorView) and view.document.modified:
                self.tab_panel.notebook.select(view)
                name = view.document.filepath.name if view.document.filepath else "New Tab"
                response = messagebox.askyesnocancel("Unsaved Changes", f"Save changes to {name} before exiting?")
                if response is True:
                    if not view.save_to_file():
                        return
                elif response is None:
                    return
        self.root.destroy()

    # ---------- File Operations ----------
    def _open_file(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Open File"
        )
        if not filepath:
            return
        editor = self._new_tab()
        if editor.load_from_file(Path(filepath)):
            self._update_status(f"Opened {filepath}")
        else:
            self.tab_panel.remove_tab(editor)
            self._update_status("Open cancelled")

    def _save_file(self):
        editor = self._get_current_editor()
        if not editor:
            messagebox.showinfo("Info", "No editor tab active.")
            return False
        if editor.document.filepath:
            if editor.save_to_file():
                self._update_status(f"Saved {editor.document.filepath.name}")
                return True
        else:
            return self._save_as_file()
        return False

    def _save_as_file(self):
        editor = self._get_current_editor()
        if not editor:
            messagebox.showinfo("Info", "No editor tab active.")
            return False
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Save As"
        )
        if not filepath:
            return False
        if editor.save_to_file(Path(filepath)):
            self._update_status(f"Saved as {filepath}")
            return True
        return False

    # ---------- Edit Operations ----------
    def _cut(self):
        if ed := self._get_current_editor():
            ed._tk_text.event_generate("<<Cut>>")
            ed.document.modified = True

    def _copy(self):
        if ed := self._get_current_editor():
            ed._tk_text.event_generate("<<Copy>>")

    def _paste(self):
        if ed := self._get_current_editor():
            ed._tk_text.event_generate("<<Paste>>")
            ed.document.modified = True

    def _select_all(self):
        if ed := self._get_current_editor():
            ed._tk_text.tag_add(tk.SEL, "1.0", tk.END)
            ed._tk_text.mark_set(tk.INSERT, "1.0")
            ed._tk_text.see(tk.INSERT)

    def _undo(self):
        if ed := self._get_current_editor():
            try:
                ed._tk_text.edit_undo()
            except tk.TclError:
                pass

    def _redo(self):
        if ed := self._get_current_editor():
            try:
                ed._tk_text.edit_redo()
            except tk.TclError:
                pass

    # ---------- Zoom ----------
    def _zoom_in(self):
        AppConfig.update_settings(AppConfig.font_family, AppConfig.font_size + 1, AppConfig.theme)
        self._update_status(f"Zoom: {AppConfig.font_size}pt")

    def _zoom_out(self):
        AppConfig.update_settings(AppConfig.font_family, max(8, AppConfig.font_size - 1), AppConfig.theme)
        self._update_status(f"Zoom: {AppConfig.font_size}pt")

    def _reset_zoom(self):
        AppConfig.update_settings(AppConfig.font_family, 12, AppConfig.theme)
        self._update_status("Zoom reset to 12pt")

    # ---------- Find/Replace ----------
    def _show_find_replace(self):
        editor = self._get_current_editor()
        if not editor:
            messagebox.showinfo("Info", "Open an editor tab first.")
            return
        # If dialog already exists, bring it to front
        if self._find_dialog is not None and self._find_dialog.winfo_exists():
            self._find_dialog.lift()
            self._find_dialog.focus_force()
            return
        self._find_dialog = FindReplaceDialog(self.root, editor)
        self._find_dialog.focus_force()

    # ---------- Typing Speed Test ----------
    def _show_typing_speed(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Typing Speed Check")
        win.geometry("650x520")
        win.transient(self.root)
        win.attributes('-topmost', True)
        win.grab_set()
        win.focus_force()
        if pywinstyles:
            try:
                pywinstyles.apply_style(win, "mica")
            except:
                pass

        main = ctk.CTkFrame(win, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        ctk.CTkLabel(main, text="Typing Speed Check", font=("Segoe UI", 20, "bold")).pack(pady=(0,20))

        sample = ("The quick brown fox jumps over the lazy dog. "
                  "Writing clean, efficient, and well-documented code is essential "
                  "for modern software development. Practice consistently to improve "
                  "your speed and accuracy.")

        sample_color = "#dddddd" if AppConfig.theme == "dark" else "#333333"
        sample_disp = ctk.CTkTextbox(
            main,
            height=80,
            wrap=tk.WORD,
            font=("Segoe UI", 14),
            fg_color="transparent",
            text_color=sample_color
        )
        sample_disp.insert("1.0", sample)
        sample_disp.configure(state=tk.DISABLED)
        sample_disp.pack(fill=tk.X, pady=(0,15))

        stats = ctk.CTkFrame(main, fg_color="#242424", corner_radius=10)
        stats.pack(fill=tk.X, pady=(0,15), ipady=10)
        wpm_var = ctk.StringVar(value="WPM: 0")
        acc_var = ctk.StringVar(value="Accuracy: 100%")
        time_var = ctk.StringVar(value="Time: 0s")
        for var in (wpm_var, acc_var, time_var):
            ctk.CTkLabel(stats, textvariable=var, font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT, expand=True)

        input_area = ctk.CTkTextbox(main, height=80, wrap=tk.WORD, font=("Segoe UI", 14))
        input_area.pack(fill=tk.X)
        input_area.focus_set()

        state = {'start': None, 'running': False, 'timer_id': None}

        def update_timer():
            if state['running'] and state['start']:
                elapsed = int(time.time() - state['start'])
                time_var.set(f"Time: {elapsed}s")
                state['timer_id'] = win.after(1000, update_timer)

        def reset_stats():
            state['start'] = None
            state['running'] = False
            if state['timer_id']:
                win.after_cancel(state['timer_id'])
                state['timer_id'] = None
            wpm_var.set("WPM: 0")
            acc_var.set("Accuracy: 100%")
            time_var.set("Time: 0s")

        def on_type(event):
            if event.keysym in ("Shift_L","Shift_R","Control_L","Control_R","Alt_L","Alt_R",
                                "Caps_Lock","Tab","Up","Down","Left","Right"):
                return
            typed = input_area.get("1.0", "end-1c")
            typed_len = len(typed)

            if typed_len > len(sample):
                input_area.delete("end-2c", tk.END)
                return

            if not state['start'] and typed_len > 0:
                state['start'] = time.time()
                state['running'] = True
                update_timer()

            if typed_len == 0:
                reset_stats()
                return

            correct = sum(1 for i, c in enumerate(typed) if i < len(sample) and c == sample[i])
            acc = (correct / typed_len) * 100 if typed_len > 0 else 100
            acc_var.set(f"Accuracy: {int(acc)}%")

            if state['start']:
                elapsed = time.time() - state['start']
                if elapsed > 0:
                    minutes = elapsed / 60
                    wpm = (typed_len / 5) / minutes
                    wpm_var.set(f"WPM: {int(wpm)}")

            if typed_len >= len(sample):
                state['running'] = False
                if state['timer_id']:
                    win.after_cancel(state['timer_id'])
                    state['timer_id'] = None
                input_area.configure(state=tk.DISABLED)
                final_acc = (correct / len(sample)) * 100
                acc_var.set(f"Accuracy: {int(final_acc)}%")

        input_area._textbox.bind("<KeyRelease>", on_type)

        def reset_test():
            input_area.configure(state=tk.NORMAL)
            input_area.delete("1.0", tk.END)
            reset_stats()
            input_area.focus_set()

        ctk.CTkButton(main, text="Reset Test", command=reset_test, height=35).pack(pady=15)

    # ---------- Settings Tab ----------
    def _open_settings_tab(self):
        for view in self.tab_panel._views:
            if isinstance(view, SettingsView):
                self.tab_panel.notebook.select(view)
                return
        settings = SettingsView(self.tab_panel.notebook)
        self.tab_panel.add_tab(settings, "Settings")

    # ---------- About ----------
    def _show_about(self):
        win = ctk.CTkToplevel(self.root)
        win.title("About")
        win.geometry("400x320")
        win.resizable(False, False)
        win.transient(self.root)
        win.attributes('-topmost', True)
        win.grab_set()
        win.focus_force()
        if pywinstyles:
            try:
                pywinstyles.apply_style(win, "mica")
            except:
                pass
        about = AboutView(win)
        about.pack(fill=tk.BOTH, expand=True)
        ctk.CTkButton(win, text="Close", command=win.destroy, width=100).pack(pady=(0,20))

    def run(self):
        self.root.mainloop()


# ---------------------------- Entry Point ----------------------------
if __name__ == "__main__":
    app = ModernNotepad()
    app.run()
