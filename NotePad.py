import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
import os
import sys
import time

try:
    import pywinstyles
except ImportError:
    pywinstyles = None

# Component Interface
class UIComponent:
    def render(self):
        pass

    def add(self, component):
        pass

    def remove(self, component):
        pass

    def get_child(self, index):
        pass

# Leaf Classes
class TextEditor(UIComponent):
    def __init__(self, parent, tabbed_panel=None, font_family="Segoe UI", font_size=12):
        self.parent = parent
        self.tabbed_panel = tabbed_panel
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        
        # Line Numbers Canvas
        self.line_numbers = tk.Canvas(self.frame, width=40, bg='#1a1a1a', highlightthickness=0)
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        
        # Text Area (Using CTkTextbox for modern scrollbars and look)
        self.text_area = ctk.CTkTextbox(
            self.frame,
            wrap=tk.WORD,
            font=(font_family, font_size),
            fg_color='#242424',
            text_color='#ffffff',
            undo=True,
            corner_radius=0
        )
        self.text_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Access the underlying tk.Text widget for specific features CTk hides
        self._tk_text = self.text_area._textbox
        self._tk_text.configure(insertbackground='white', selectbackground='#3e3e3e')
        
        self.current_file = None
        self.is_modified = False

        # Bind events for updates
        self._tk_text.bind("<KeyRelease>", self.on_key_release)
        self._tk_text.bind("<MouseWheel>", self.redraw_line_numbers)
        self._tk_text.bind("<Button-1>", self.redraw_line_numbers)
        self._tk_text.bind("<Configure>", self.redraw_line_numbers)

    def render(self):
        self.frame.pack(fill=tk.BOTH, expand=True)

    def on_key_release(self, event=None):
        self.redraw_line_numbers()
        # Ignore navigation keys for modification state
        if event and event.keysym not in ("Up", "Down", "Left", "Right", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock"):
            self.mark_modified()

    def redraw_line_numbers(self, event=None):
        self.line_numbers.delete("all")
        i = self._tk_text.index("@0,0")
        
        is_light = ctk.get_appearance_mode() == "Light"
        text_color = "#666666" if is_light else "#888888"

        while True:
            dline = self._tk_text.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            current_font = self.text_area.cget("font")
            self.line_numbers.create_text(35, y, anchor="ne", text=linenum, fill=text_color, font=current_font)
            i = self._tk_text.index("%s+1line" % i)

    def mark_modified(self):
        if not self.is_modified:
            self.is_modified = True
            self.update_tab_title()

    def mark_saved(self):
        self.is_modified = False
        self.update_tab_title()

    def update_tab_title(self):
        if not self.tabbed_panel: return
        try:
            index = self.tabbed_panel.children.index(self)
            title = os.path.basename(self.current_file) if self.current_file else "New Tab"
            if self.is_modified:
                title += " *"
            self.tabbed_panel.notebook.tab(index, text=title)
        except ValueError:
            pass

    def get_text(self):
        return self.text_area.get("1.0", tk.END)

    def set_text(self, text):
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", text)
        self.redraw_line_numbers()

    def clear(self):
        self.text_area.delete("1.0", tk.END)
        self.redraw_line_numbers()

    def save_to_file(self, filename=None):
        if filename is None:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
            )
            if not filename:
                return False
            self.current_file = filename

        try:
            text_content = self.text_area.get("1.0", "end-1c") 
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(text_content)
            self.mark_saved()
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")
            return False

    def open_file(self, filename=None):
        if filename is None:
            filename = filedialog.askopenfilename(
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
            )
            if not filename:
                return False
            self.current_file = filename

        try:
            with open(filename, 'r', encoding='utf-8') as file:
                self.set_text(file.read())
            self.mark_saved()
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")
            return False

class SettingsPanel(UIComponent):
    def __init__(self, parent, tabbed_panel, font_family="Segoe UI", font_size=12):
        self.parent = parent
        self.tabbed_panel = tabbed_panel
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        
        inner_frame = ctk.CTkFrame(self.frame, corner_radius=10, fg_color="#242424")
        inner_frame.pack(pady=40, padx=40, fill=tk.BOTH, expand=True)

        # Font Family
        ctk.CTkLabel(inner_frame, text="Font Family:", font=("Segoe UI", 14)).grid(row=0, column=0, sticky=tk.W, padx=20, pady=(20,10))
        self.font_family_var = ctk.StringVar(value=font_family)
        self.font_family_combo = ctk.CTkOptionMenu(
            inner_frame,
            variable=self.font_family_var,
            values=["Segoe UI", "Arial", "Courier New", "Times New Roman", "Consolas"]
        )
        self.font_family_combo.grid(row=0, column=1, sticky=tk.EW, padx=20, pady=(20,10))
        
        # Font Size
        ctk.CTkLabel(inner_frame, text="Font Size:", font=("Segoe UI", 14)).grid(row=1, column=0, sticky=tk.W, padx=20, pady=10)
        self.font_size_var = ctk.StringVar(value=str(font_size))
        self.font_size_combo = ctk.CTkOptionMenu(
            inner_frame,
            variable=self.font_size_var,
            values=["8", "10", "12", "14", "16", "18", "20", "24", "28", "36"]
        )
        self.font_size_combo.grid(row=1, column=1, sticky=tk.EW, padx=20, pady=10)
        
        # Theme
        ctk.CTkLabel(inner_frame, text="Theme:", font=("Segoe UI", 14)).grid(row=2, column=0, sticky=tk.W, padx=20, pady=10)
        self.theme_var = ctk.StringVar(value="Dark")
        self.theme_combo = ctk.CTkOptionMenu(
            inner_frame,
            variable=self.theme_var,
            values=["Dark", "Light"]
        )
        self.theme_combo.grid(row=2, column=1, sticky=tk.EW, padx=20, pady=10)
        
        # Apply Button
        self.apply_btn = ctk.CTkButton(
            inner_frame,
            text="Apply Settings",
            command=self.apply_settings,
            height=35
        )
        self.apply_btn.grid(row=3, column=0, columnspan=2, pady=30)
        
        inner_frame.columnconfigure(1, weight=1)

    def render(self):
        self.frame.pack(fill=tk.BOTH, expand=True)

    def apply_settings(self):
        font_family = self.font_family_var.get()
        font_size = int(self.font_size_var.get())
        theme = self.theme_var.get()
        
        if theme == "Dark":
            ctk.set_appearance_mode("dark")
        elif theme == "Light":
            ctk.set_appearance_mode("light")

        # Apply settings to all active text editors dynamically
        for child in self.tabbed_panel.children:
            if isinstance(child, TextEditor):
                child.text_area.configure(font=(font_family, font_size))
                child.redraw_line_numbers()
                
                if theme == "Dark":
                    child.text_area.configure(fg_color='#242424', text_color='#ffffff')
                    child._tk_text.configure(insertbackground='white', selectbackground='#3e3e3e')
                    child.line_numbers.config(bg='#1a1a1a')
                elif theme == "Light":
                    child.text_area.configure(fg_color='#ffffff', text_color='#000000')
                    child._tk_text.configure(insertbackground='black', selectbackground='#d4d4d4')
                    child.line_numbers.config(bg='#f0f0f0')

class AboutPanel(UIComponent):
    def __init__(self, parent):
        self.parent = parent
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        
        inner_frame = ctk.CTkFrame(self.frame, corner_radius=10, fg_color="#242424")
        inner_frame.pack(pady=40, padx=40, fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(inner_frame, text="Modern Notepad", font=("Segoe UI", 24, "bold")).pack(pady=(30, 10))
        ctk.CTkLabel(
            inner_frame,
            text="Version 2.0\n\nA modern notepad application with multiple tabs,\nline numbers, find/replace, and a beautiful UI.\n\nBuilt with Python and CustomTkinter",
            font=("Segoe UI", 14),
            justify="center"
        ).pack(pady=10)
        ctk.CTkLabel(inner_frame, text="© 2026 M. Abdullah Wali", font=("Segoe UI", 12), text_color="gray").pack(pady=30)

    def render(self):
        self.frame.pack(fill=tk.BOTH, expand=True)

# Composite Class
class TabbedPanel(UIComponent):
    def __init__(self, parent):
        self.parent = parent
        self.notebook = ttk.Notebook(parent)
        self.children = []
        
        # Create default tabs
        self.add(TextEditor(self.notebook, tabbed_panel=self))
        self.add(SettingsPanel(self.notebook, self))
        self.add(AboutPanel(self.notebook))
        
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.notebook.tab(0, text="New Tab")
        self.notebook.tab(1, text="Settings")
        self.notebook.tab(2, text="About")
        
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

    def render(self):
        self.notebook.pack(fill=tk.BOTH, expand=True)

    def on_tab_change(self, event=None):
        current = self.get_current_tab()
        if isinstance(current, TextEditor):
            current.redraw_line_numbers()

    def add(self, component):
        self.children.append(component)
        if isinstance(component, TextEditor):
            component.tabbed_panel = self
            self.notebook.add(component.frame, text="New Tab")
        elif hasattr(component, 'frame'):
            title = "New Tab"
            if isinstance(component, SettingsPanel): title = "Settings"
            elif isinstance(component, AboutPanel): title = "About"
            self.notebook.add(component.frame, text=title)
        else:
            self.notebook.add(component, text="New Tab")

    def remove(self, component):
        if component in self.children:
            index = self.children.index(component)
            self.notebook.forget(index)
            self.children.remove(component)

    def get_child(self, index):
        if 0 <= index < len(self.children):
            return self.children[index]
        return None

    def get_current_tab(self):
        current_index = self.notebook.index("current")
        return self.get_child(current_index)

# Application Class
class ModernNotepad:
    def __init__(self):
        # Configure CTk Appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Modern Notepad")
        self.root.geometry("900x650")
        
        # Apply Window Blur Effect if available
        if pywinstyles:
            try:
                pywinstyles.apply_style(self.root, "mica")
            except Exception as e:
                print(f"Could not apply window style: {e}")
        
        # Cross Platform Command/Control key setup
        self.is_mac = sys.platform == "darwin"
        self.ctrl_cmd = "Cmd" if self.is_mac else "Ctrl"
        self.ctrl_key = "Command" if self.is_mac else "Control"
        
        # Restyle standard ttk.Notebook to blend seamlessly with CustomTkinter
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TNotebook', background='#1a1a1a', borderwidth=0)
        self.style.configure('TNotebook.Tab', background='#242424', foreground='#a0a0a0', padding=[15, 5], borderwidth=0)
        self.style.map('TNotebook.Tab', 
                       background=[('selected', '#333333')],
                       foreground=[('selected', '#ffffff')])
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.create_menu_bar()
        self.create_toolbar()
        
        self.status_bar = ctk.CTkLabel(self.root, text="Ready", anchor="w", fg_color="#1a1a1a", height=25, padx=10)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tabbed_panel = TabbedPanel(self.root)
        self.tabbed_panel.render()
        
        self.bind_events()

    def create_menu_bar(self):
        menubar = tk.Menu(self.root)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self.new_file, accelerator=f"{self.ctrl_cmd}+N")
        file_menu.add_command(label="Open", command=self.open_file, accelerator=f"{self.ctrl_cmd}+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator=f"{self.ctrl_cmd}+S")
        file_menu.add_command(label="Save As...", command=self.save_as_file)
        file_menu.add_command(label="Close Tab", command=self.close_current_tab, accelerator=f"{self.ctrl_cmd}+W")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Edit Menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Cut", command=self.cut_text, accelerator=f"{self.ctrl_cmd}+X")
        edit_menu.add_command(label="Copy", command=self.copy_text, accelerator=f"{self.ctrl_cmd}+C")
        edit_menu.add_command(label="Paste", command=self.paste_text, accelerator=f"{self.ctrl_cmd}+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Find/Replace", command=self.show_find_replace, accelerator=f"{self.ctrl_cmd}+F")
        edit_menu.add_command(label="Select All", command=self.select_all, accelerator=f"{self.ctrl_cmd}+A")
        edit_menu.add_command(label="Settings", command=self.open_settings_tab)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # View Menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Zoom In", command=self.zoom_in, accelerator=f"{self.ctrl_cmd}++")
        view_menu.add_command(label="Zoom Out", command=self.zoom_out, accelerator=f"{self.ctrl_cmd}+-")
        view_menu.add_command(label="Reset Zoom", command=self.reset_zoom, accelerator=f"{self.ctrl_cmd}+0")
        menubar.add_cascade(label="View", menu=view_menu)
        
        # Tools Menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Typing Speed Check", command=self.show_typing_speed_check)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)

    def create_toolbar(self):
        toolbar = ctk.CTkFrame(self.root, height=45, corner_radius=0, fg_color="#1a1a1a")
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # Using CTkButtons for a modern look
        btn_kwargs = {"width": 60, "height": 28, "fg_color": "transparent", "hover_color": "#333333", "text_color": "#ffffff"}
        
        ctk.CTkButton(toolbar, text="New", command=self.new_file, **btn_kwargs).pack(side=tk.LEFT, padx=(10, 2), pady=5)
        ctk.CTkButton(toolbar, text="Open", command=self.open_file, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)
        ctk.CTkButton(toolbar, text="Save", command=self.save_file, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)
        
        ctk.CTkFrame(toolbar, width=2, height=20, fg_color="#333333").pack(side=tk.LEFT, padx=10, pady=10) # Separator
        
        ctk.CTkButton(toolbar, text="Cut", command=self.cut_text, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)
        ctk.CTkButton(toolbar, text="Copy", command=self.copy_text, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)
        ctk.CTkButton(toolbar, text="Paste", command=self.paste_text, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)
        
        ctk.CTkFrame(toolbar, width=2, height=20, fg_color="#333333").pack(side=tk.LEFT, padx=10, pady=10) # Separator
        
        ctk.CTkButton(toolbar, text="Find", command=self.show_find_replace, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)
        ctk.CTkButton(toolbar, text="Close Tab", command=self.close_current_tab, **btn_kwargs).pack(side=tk.LEFT, padx=2, pady=5)

    def bind_events(self):
        self.root.bind(f"<{self.ctrl_key}-n>", lambda e: self.new_file())
        self.root.bind(f"<{self.ctrl_key}-o>", lambda e: self.open_file())
        self.root.bind(f"<{self.ctrl_key}-s>", lambda e: self.save_file())
        self.root.bind(f"<{self.ctrl_key}-w>", lambda e: self.close_current_tab())
        self.root.bind(f"<{self.ctrl_key}-f>", lambda e: self.show_find_replace())
        self.root.bind(f"<{self.ctrl_key}-x>", lambda e: self.cut_text())
        self.root.bind(f"<{self.ctrl_key}-c>", lambda e: self.copy_text())
        self.root.bind(f"<{self.ctrl_key}-v>", lambda e: self.paste_text())
        self.root.bind(f"<{self.ctrl_key}-a>", lambda e: self.select_all())
        self.root.bind(f"<{self.ctrl_key}-plus>", lambda e: self.zoom_in())
        self.root.bind(f"<{self.ctrl_key}-equal>", lambda e: self.zoom_in())
        self.root.bind(f"<{self.ctrl_key}-minus>", lambda e: self.zoom_out())
        self.root.bind(f"<{self.ctrl_key}-0>", lambda e: self.reset_zoom())

    def get_current_editor(self):
        current_tab = self.tabbed_panel.get_current_tab()
        if isinstance(current_tab, TextEditor):
            return current_tab
        return None

    def new_file(self):
        editor = TextEditor(self.tabbed_panel.notebook, tabbed_panel=self.tabbed_panel)
        self.tabbed_panel.add(editor)
        self.tabbed_panel.notebook.select(len(self.tabbed_panel.children) - 1)
        self.update_status("New file created")

    def open_file(self):
        editor = self.get_current_editor()
        if editor:
            content = editor.get_text().strip()
            # Prevent overwriting unsaved work or current files
            if content or editor.is_modified or editor.current_file:
                self.new_file()
                editor = self.get_current_editor()
            
            if editor and editor.open_file():
                self.update_status(f"Opened file: {editor.current_file}")
        else:
            self.new_file()
            self.open_file()

    def save_file(self):
        editor = self.get_current_editor()
        if editor:
            if editor.current_file:
                if editor.save_to_file(editor.current_file):
                    self.update_status(f"Saved to {editor.current_file}")
                    return True
            else:
                return self.save_as_file()
        else:
            messagebox.showinfo("Info", "Please select an editor tab to save a file")
        return False

    def save_as_file(self):
        editor = self.get_current_editor()
        if editor:
            if editor.save_to_file():
                self.update_status(f"Saved to {editor.current_file}")
                return True
        else:
            messagebox.showinfo("Info", "Please select an editor tab to save a file")
        return False

    def close_current_tab(self):
        current_tab = self.tabbed_panel.get_current_tab()
        if isinstance(current_tab, TextEditor) and current_tab.is_modified:
            resp = messagebox.askyesnocancel(
                "Unsaved Changes", 
                f"Do you want to save changes to {current_tab.current_file or 'New Tab'}?"
            )
            if resp is True:
                if current_tab.current_file:
                    if not current_tab.save_to_file(current_tab.current_file): return
                else:
                    if not current_tab.save_to_file(): return
            elif resp is None:
                return 

        if current_tab:
            self.tabbed_panel.remove(current_tab)
            if len(self.tabbed_panel.children) == 0:
                self.new_file()

    def open_settings_tab(self):
        for index, child in enumerate(self.tabbed_panel.children):
            if isinstance(child, SettingsPanel):
                self.tabbed_panel.notebook.select(index)
                return
        
        settings_tab = SettingsPanel(self.tabbed_panel.notebook, self.tabbed_panel)
        self.tabbed_panel.add(settings_tab)
        
        new_tab_index = len(self.tabbed_panel.children) - 1
        self.tabbed_panel.notebook.tab(new_tab_index, text="Settings")
        self.tabbed_panel.notebook.select(new_tab_index)

    def on_closing(self):
        # Capture modified editors safely to prevent state changing during iteration
        editors = [child for child in self.tabbed_panel.children if isinstance(child, TextEditor) and child.is_modified]
        
        for child in editors:
            self.tabbed_panel.notebook.select(self.tabbed_panel.children.index(child))
            self.root.update()
            resp = messagebox.askyesnocancel(
                "Unsaved Changes", 
                f"Do you want to save changes to {child.current_file or 'New Tab'} before exiting?"
            )
            if resp is True:
                if child.current_file:
                    saved = child.save_to_file(child.current_file)
                else:
                    saved = child.save_to_file()
                    
                if not saved: return
            elif resp is None:
                return
        self.root.destroy()

    def show_find_replace(self):
        editor = self.get_current_editor()
        if not editor:
            messagebox.showinfo("Info", "Please select an editor tab first")
            return

        fr_window = ctk.CTkToplevel(self.root)
        fr_window.title("Find and Replace")
        fr_window.geometry("380x180")
        fr_window.transient(self.root)
        fr_window.attributes('-topmost', True) # Ensures it stays above the main window
        fr_window.grab_set()
        fr_window.focus_force()
        
        if pywinstyles:
            try: pywinstyles.apply_style(fr_window, "mica")
            except: pass

        ctk.CTkLabel(fr_window, text="Find:").grid(row=0, column=0, padx=20, pady=(20,10), sticky="w")
        find_entry = ctk.CTkEntry(fr_window, width=200)
        find_entry.grid(row=0, column=1, padx=10, pady=(20,10))

        ctk.CTkLabel(fr_window, text="Replace:").grid(row=1, column=0, padx=20, pady=10, sticky="w")
        replace_entry = ctk.CTkEntry(fr_window, width=200)
        replace_entry.grid(row=1, column=1, padx=10, pady=10)

        def find_next():
            # Dynamically fetch the editor to allow searching across tabs
            active_editor = self.get_current_editor()
            if not active_editor: return
            
            query = find_entry.get()
            if query:
                start = active_editor._tk_text.index(tk.INSERT)
                if active_editor._tk_text.tag_ranges(tk.SEL):
                    start = tk.SEL_LAST
                pos = active_editor._tk_text.search(query, start, stopindex=tk.END)
                if pos:
                    end_pos = f"{pos}+{len(query)}c"
                    active_editor._tk_text.tag_remove(tk.SEL, "1.0", tk.END)
                    active_editor._tk_text.tag_add(tk.SEL, pos, end_pos)
                    active_editor._tk_text.mark_set(tk.INSERT, end_pos)
                    active_editor._tk_text.see(tk.INSERT)
                    active_editor.text_area.focus_set()

        def replace_all():
            active_editor = self.get_current_editor()
            if not active_editor: return
            
            query = find_entry.get()
            replacement = replace_entry.get()
            if query:
                content = active_editor.get_text()
                new_content = content.replace(query, replacement)
                if content != new_content:
                    active_editor.set_text(new_content)
                    active_editor.mark_modified()

        btn_frame = ctk.CTkFrame(fr_window, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ctk.CTkButton(btn_frame, text="Find Next", width=100, command=find_next).pack(side=tk.LEFT, padx=10)
        ctk.CTkButton(btn_frame, text="Replace All", width=100, command=replace_all).pack(side=tk.LEFT, padx=10)
        
        find_entry.focus_set()

    def show_typing_speed_check(self):
        test_window = ctk.CTkToplevel(self.root)
        test_window.title("Typing Speed Check")
        test_window.geometry("600x480")
        test_window.transient(self.root)
        test_window.attributes('-topmost', True)
        test_window.grab_set()
        test_window.focus_force()
        
        if pywinstyles:
            try: pywinstyles.apply_style(test_window, "mica")
            except: pass

        main_frame = ctk.CTkFrame(test_window, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        ctk.CTkLabel(main_frame, text="Typing Speed Check", font=("Segoe UI", 20, "bold")).pack(pady=(0, 20))

        sample_text = "The quick brown fox jumps over the lazy dog. Writing clean, efficient, and well-documented code is essential for modern software development. Practice consistently to improve your speed and accuracy."

        # Display sample text
        sample_display = ctk.CTkTextbox(main_frame, height=90, wrap=tk.WORD, font=("Segoe UI", 14), text_color="#a0a0a0")
        sample_display.insert("1.0", sample_text)
        sample_display.configure(state=tk.DISABLED)
        sample_display.pack(fill=tk.X, pady=(0, 20))

        # Stats frame
        stats_frame = ctk.CTkFrame(main_frame, fg_color="#242424", corner_radius=10)
        stats_frame.pack(fill=tk.X, pady=(0, 20), ipady=10)

        wpm_var = ctk.StringVar(value="WPM: 0")
        acc_var = ctk.StringVar(value="Accuracy: 100%")
        time_var = ctk.StringVar(value="Time: 0s")

        ctk.CTkLabel(stats_frame, textvariable=wpm_var, font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT, expand=True)
        ctk.CTkLabel(stats_frame, textvariable=acc_var, font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT, expand=True)
        ctk.CTkLabel(stats_frame, textvariable=time_var, font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT, expand=True)

        # Input area
        input_area = ctk.CTkTextbox(main_frame, height=90, wrap=tk.WORD, font=("Segoe UI", 14))
        input_area.pack(fill=tk.X)
        input_area.focus_set()

        state = {
            'start_time': None,
            'is_running': False
        }

        def on_type(event):
            if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock", "Tab", "Up", "Down", "Left", "Right"):
                return

            typed_text = input_area.get("1.0", "end-1c")

            if not state['start_time'] and len(typed_text) > 0:
                state['start_time'] = time.time()
                state['is_running'] = True
                update_timer()

            if len(typed_text) == 0:
                reset_stats()
                return

            correct_chars = 0
            for i, c in enumerate(typed_text):
                if i < len(sample_text) and c == sample_text[i]:
                    correct_chars += 1

            accuracy = (correct_chars / len(typed_text)) * 100 if len(typed_text) > 0 else 100
            acc_var.set(f"Accuracy: {int(accuracy)}%")

            if state['start_time']:
                elapsed = time.time() - state['start_time']
                if elapsed > 0:
                    minutes = elapsed / 60
                    wpm = (len(typed_text) / 5) / minutes
                    wpm_var.set(f"WPM: {int(wpm)}")

            if len(typed_text) >= len(sample_text):
                state['is_running'] = False
                input_area.configure(state=tk.DISABLED)

        def update_timer():
            if state['is_running'] and state['start_time']:
                elapsed = int(time.time() - state['start_time'])
                time_var.set(f"Time: {elapsed}s")
                test_window.after(1000, update_timer)

        def reset_stats():
            state['start_time'] = None
            state['is_running'] = False
            wpm_var.set("WPM: 0")
            acc_var.set("Accuracy: 100%")
            time_var.set("Time: 0s")

        def reset_test():
            input_area.configure(state=tk.NORMAL)
            input_area.delete("1.0", tk.END)
            reset_stats()
            input_area.focus_set()

        input_area._textbox.bind("<KeyRelease>", on_type)
        
        ctk.CTkButton(main_frame, text="Reset Test", command=reset_test, height=35).pack(pady=20)

    def cut_text(self):
        editor = self.get_current_editor()
        if editor:
            editor._tk_text.event_generate("<<Cut>>")
            self.update_status("Text cut to clipboard")
            editor.mark_modified()

    def copy_text(self):
        editor = self.get_current_editor()
        if editor:
            editor._tk_text.event_generate("<<Copy>>")
            self.update_status("Text copied to clipboard")

    def paste_text(self):
        editor = self.get_current_editor()
        if editor:
            editor._tk_text.event_generate("<<Paste>>")
            self.update_status("Text pasted from clipboard")
            editor.mark_modified()

    def select_all(self):
        editor = self.get_current_editor()
        if editor:
            editor._tk_text.tag_add(tk.SEL, "1.0", tk.END)
            editor._tk_text.mark_set(tk.INSERT, "1.0")
            editor._tk_text.see(tk.INSERT)
            self.update_status("All text selected")

    def zoom_in(self):
        editor = self.get_current_editor()
        if editor:
            current_font = tkfont.Font(font=editor.text_area.cget("font"))
            font_family = current_font.actual('family')
            font_size = current_font.actual('size')
            new_size = font_size + 1
            editor.text_area.configure(font=(font_family, new_size))
            editor.redraw_line_numbers()
            self.update_status(f"Zoom: {new_size}pt")

    def zoom_out(self):
        editor = self.get_current_editor()
        if editor:
            current_font = tkfont.Font(font=editor.text_area.cget("font"))
            font_family = current_font.actual('family')
            font_size = current_font.actual('size')
            new_size = max(8, font_size - 1)
            editor.text_area.configure(font=(font_family, new_size))
            editor.redraw_line_numbers()
            self.update_status(f"Zoom: {new_size}pt")

    def reset_zoom(self):
        editor = self.get_current_editor()
        if editor:
            current_font = tkfont.Font(font=editor.text_area.cget("font"))
            font_family = current_font.actual('family')
            editor.text_area.configure(font=(font_family, 12))
            editor.redraw_line_numbers()
            self.update_status("Zoom reset to 12pt")

    def show_about(self):
        about_window = ctk.CTkToplevel(self.root)
        about_window.title("About")
        about_window.geometry("400x320")
        about_window.resizable(False, False)
        
        # Ensures window spawns visible and locked to front
        about_window.transient(self.root)
        about_window.attributes('-topmost', True)
        about_window.grab_set()
        about_window.focus_force()
        
        if pywinstyles:
            try: pywinstyles.apply_style(about_window, "mica")
            except: pass
        
        main_frame = ctk.CTkFrame(about_window, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)
        
        ctk.CTkLabel(main_frame, text="Modern Notepad", font=("Segoe UI", 22, "bold")).pack(pady=(0, 5))
        ctk.CTkLabel(main_frame, text="Version 2.0", font=("Segoe UI", 12), text_color="#888888").pack(pady=(0, 20))
        
        desc = "A modern notepad application with multiple tabs\nand a sleek, minimalist interface."
        ctk.CTkLabel(main_frame, text=desc, justify="center", font=("Segoe UI", 12)).pack(pady=10)
        
        ctk.CTkLabel(main_frame, text="Built with Python & CustomTkinter", font=("Segoe UI", 12)).pack(pady=5)
        
        ctk.CTkFrame(main_frame, height=1, fg_color="#333333").pack(fill="x", pady=20)
        
        ctk.CTkLabel(main_frame, text="© 2026 M. Abdullah Wali", font=("Segoe UI", 12), text_color="#888888").pack(pady=(0, 15))
        
        ctk.CTkButton(main_frame, text="Close", command=about_window.destroy, width=100).pack()

    def update_status(self, message):
        self.status_bar.configure(text=message)

if __name__ == "__main__":
    app = ModernNotepad()
    app.root.mainloop()