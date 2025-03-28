import os
import shutil
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import platform
import sys
import json
import datetime
import math
import io
import base64

if platform.system() == "Windows":
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw, ImageTk, ImageFont
    import winreg
    import watchdog.observers
    import watchdog.events
else:  
    try:
        from pystray import Icon, Menu, MenuItem
        from PIL import Image, ImageDraw, ImageTk, ImageFont
        import watchdog.observers
        import watchdog.events
        if platform.system() == "Darwin":  
            import subprocess
            import plistlib
    except ImportError as e:
        print(f"Import error on non-Windows platform: {e}")
        pass

IS_STARTUP_MODE = "--startup" in sys.argv

CONFIG_FILE = os.path.join(os.path.expanduser("~"), "boft_config.json")
DEFAULT_CONFIG = {
    "auto_organize_folder": None,
    "autostart_enabled": False,
    "window_size": "700x500",
    "theme": "dark",
    "recent_activities": [],
    "stats": {
        "total_files_organized": 0,
        "space_saved": 0,
        "files_by_type": {},
        "last_organized": None
    },
    "file_categories": {
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".ico", ".heic", ".raw", ".cr2", ".nef", ".arw"],
        "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".md", ".epub", ".mobi", ".pages", ".numbers", ".key"],
        "Videos": [".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".webm", ".m4v", ".3gp", ".mpeg", ".mpg", ".ts", ".vob"],
        "Audio": [".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma", ".m4a", ".aiff", ".alac", ".mid", ".midi"],
        "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".dmg", ".pkg", ".deb", ".rpm"],
        "Executables": [".exe", ".msi", ".bat", ".cmd", ".ps1", ".sh", ".app", ".dmg", ".deb", ".rpm", ".apk", ".appimage", ".run", ".bin"],
        "Code": [".py", ".js", ".html", ".css", ".java", ".c", ".cpp", ".php", ".rb", ".go", ".ts", ".swift", ".json", ".xml", ".yaml", ".yml", ".toml", ".sql", ".sh", ".bash", ".zsh", ".ps1", ".r", ".dart", ".lua", ".rust", ".kt", ".scala", ".cs", ".vb"]
    },
    "custom_organization": {
        "tag_separator": "_",
        "min_tag_length": 3,
        "ignore_extensions": True,
        "min_occurrences": 2,
        "last_used_folder": None
    }
}

auto_organize_folder = None
auto_organize_running = False
tray_icon = None
observer = None
config = {}
status_history = []
recent_activities = []  
MAX_RECENT_ACTIVITIES = 100  
stats = {
    "total_files_organized": 0,
    "space_saved": 0,
    "files_by_type": {},
    "last_organized": None
}
file_categories = {}

def save_config():
    
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, default=str)
        return True
    except (PermissionError, OSError) as e:
        print(f"Error saving configuration: {e}")
        messagebox.showerror("Error", f"Could not save configuration: {e}")
        return False

def load_config():
    
    global config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                
            
            for key, value in DEFAULT_CONFIG.items():
                if key not in loaded_config:
                    loaded_config[key] = value
                elif isinstance(value, dict) and isinstance(loaded_config[key], dict):
                    
                    for sub_key, sub_value in value.items():
                        if sub_key not in loaded_config[key]:
                            loaded_config[key][sub_key] = sub_value
            
            config = loaded_config
        else:
            config = DEFAULT_CONFIG.copy()
            save_config()
    except (json.JSONDecodeError, PermissionError, OSError) as e:
        print(f"Error loading configuration: {e}")
        config = DEFAULT_CONFIG.copy()
        save_config()

def update_status(message):
    
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    status_text.config(text=f"Status: {message} [{timestamp}]")
    
    
    if 'status_history' not in globals():
        global status_history
        status_history = []
    
    status_history.append(f"[{timestamp}] {message}")
    
    
    if len(status_history) > 100:
        status_history = status_history[-100:]
    
    root.update_idletasks()

def count_files_in_directory(directory):
    
    count = 0
    for _, _, files in os.walk(directory):
        count += len(files)
    return count

def get_file_size(file_path):
    
    try:
        return os.path.getsize(file_path)
    except (OSError, FileNotFoundError) as e:
        print(f"Error getting file size for {file_path}: {e}")
        return 0

def get_file_extension(file_path):
    
    return os.path.splitext(file_path)[1].lower()

def organize_files_by_type(directory, silent=True):
    
    if not directory or not os.path.isdir(directory):
        if not silent:
            messagebox.showerror("Error", "Invalid directory")
        return False
    
    try:
        
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        
        if not files:
            if not silent:
                messagebox.showinfo("Info", "No files to organize")
            return False
        
        
        organized_count = 0
        space_saved = 0
        files_by_type = {}
        
        
        for file in files:
            file_path = os.path.join(directory, file)
            
            
            if (platform.system() == "Darwin" or platform.system() == "Linux") and file.startswith('.'):
                continue
                
            
            ext = get_file_extension(file_path)
            
            
            try:
                if os.path.samefile(file_path, os.path.abspath(sys.argv[0])):
                    continue
            except (AttributeError, OSError):
                
                if file_path == os.path.abspath(sys.argv[0]):
                    continue
            
           
            category = None
            for cat, extensions in config["file_categories"].items():
                if ext.lower() in extensions:
                    category = cat
                    break
            
            if not category:
                category = "Other"
            
            
            category_folder = os.path.join(directory, category)
            os.makedirs(category_folder, exist_ok=True)
            
            
            new_path = os.path.join(category_folder, file)
            
            
            if os.path.exists(new_path):
                base, ext = os.path.splitext(file)
                counter = 1
                while os.path.exists(new_path):
                    new_path = os.path.join(category_folder, f"{base}_{counter}{ext}")
                    counter += 1
            
            try:
                
                file_size = get_file_size(file_path)
                
                
                shutil.move(file_path, new_path)
                
                
                organized_count += 1
                space_saved += file_size
                files_by_type[category] = files_by_type.get(category, 0) + 1
            except (PermissionError, OSError) as e:
                print(f"Error moving {file}: {e}")
                continue
        
        
        config["stats"]["total_files_organized"] += organized_count
        config["stats"]["space_saved"] += space_saved
        
        
        for category, count in files_by_type.items():
            config["stats"]["files_by_type"][category] = config["stats"]["files_by_type"].get(category, 0) + count
        
       
        config["stats"]["last_organized"] = datetime.datetime.now().isoformat()
        
        
        save_config()
        
        if not silent:
            messagebox.showinfo("Success", f"Organized {organized_count} files into {len(files_by_type)} categories")
        
        
        add_recent_activity(f"Organized {organized_count} files in {os.path.basename(directory)}")
        
        
        update_stats_display()
        
        return True
    except Exception as e:
        error_msg = f"Error organizing files: {str(e)}"
        print(error_msg)
        if not silent:
            messagebox.showerror("Error", error_msg)
        return False

def browse_directory():
    
    directory = filedialog.askdirectory(title="Select Directory to Organize")
    if directory:
        show_progress("Analyzing directory...", 0.1)
        file_count = count_files_in_directory(directory)
        if file_count == 0:
            hide_progress()
            messagebox.showinfo("No Files", "No files found in the selected directory.")
            return
            
        show_progress(f"Found {file_count} files. Processing...", 0.2)
        organize_files_by_type(directory, silent=False)
        hide_progress()
        update_status(f"Organized {file_count} files in {directory}")

def set_auto_organize_folder():
    
    global auto_organize_folder
    folder = filedialog.askdirectory(title="Select Folder to Auto-Organize")
    if folder:
        auto_organize_folder = folder
        save_config()
        update_status(f"Auto-organize folder set to: {folder}")
        messagebox.showinfo("Success", f"Auto-organize folder set to: {auto_organize_folder}")

def start_auto_organize():
    
    global auto_organize_running, observer
    if auto_organize_folder:
        auto_organize_running = True
        
        start_file_watcher()
        
        threading.Thread(target=auto_organize_loop, daemon=True).start()
        update_status("Auto-organize started")
        messagebox.showinfo("Success", "Auto-organize started!")
    else:
        messagebox.showerror("Error", "No folder selected for auto-organize.")

def start_file_watcher():
    
    global observer, auto_organize_folder
    
    if not auto_organize_folder or not os.path.isdir(auto_organize_folder):
        update_status("Cannot start file watcher: No valid folder selected")
        return False
    
    try:
        
        observer = watchdog.observers.Observer()
        
        
        event_handler = FileChangeHandler()
        
        
        observer.schedule(event_handler, auto_organize_folder, recursive=False)
        
        
        observer.start()
        
        update_status(f"File watcher started for {auto_organize_folder}")
        return True
    except Exception as e:
        print(f"Error starting file watcher: {e}")
        update_status(f"Error starting file watcher: {e}")
        observer = None
        return False

def stop_file_watcher():
    
    global observer
    if observer is not None:
        observer.stop()
        observer.join()
        observer = None

def stop_auto_organize():
    
    global auto_organize_running
    auto_organize_running = False
    stop_file_watcher()
    update_status("Auto-organize stopped")
    messagebox.showinfo("Success", "Auto-organize stopped.")

def auto_organize_loop():
    
    while auto_organize_running:
        organize_files_by_type(auto_organize_folder, silent=True)
        time.sleep(60)  

class FileChangeHandler(watchdog.events.FileSystemEventHandler):
    
    def on_created(self, event):
        
        if not event.is_directory:
            update_status(f"New file detected: {os.path.basename(event.src_path)}")
            
            time.sleep(0.5)
            organize_files_by_type(auto_organize_folder, silent=True)

class CustomSwitch(tk.Canvas):
    
    def __init__(self, master, width=60, height=26, bg="#0A0A0A", 
                callback=None, is_on=False, label=""):
        super().__init__(master, width=width, height=height, bg=bg, bd=0, highlightthickness=0)
        self.master = master
        self.width = width
        self.height = height
        self.callback = callback
        self.is_on = is_on
        self.label = label
        
        
        self.track_off_color = "#D32F2F"  
        self.track_on_color = "#4CAF50"   
        self.knob_color = "#FFFFFF"       
        
        
        self.on_text = "ON"
        self.off_text = "OFF"
        
        
        self.track = self.create_rounded_rect(
            0, 0, width, height, height//2,
            fill=self.track_off_color if not is_on else self.track_on_color,
            outline=""
        )
        
        
        text_color = "#FFFFFF"  
        
        
        self.off_text_id = self.create_text(
            width // 4 * 3, 
            height // 2,
            text=self.off_text,
            fill=text_color,
            font=("Segoe UI", 8)  
        )
        
        
        self.on_text_id = self.create_text(
            width // 4, 
            height // 2,
            text=self.on_text,
            fill=text_color,
            font=("Segoe UI", 8)  
        )
        
        
        knob_diameter = height - 6  
        
        
        knob_x = 3 if not is_on else width - knob_diameter - 3
        knob_y = 3  
        
        
        self.knob = self.create_oval(
            knob_x, 
            knob_y,
            knob_x + knob_diameter,
            knob_y + knob_diameter,
            fill=self.knob_color,
            outline="#DDDDDD"
        )
        
        
        self.update_text_visibility()
        
       
        self.bind("<Button-1>", self.toggle)
    
    def update_text_visibility(self):
        
        if self.is_on:
            
            self.itemconfigure(self.on_text_id, state='normal')
            self.itemconfigure(self.off_text_id, state='hidden')
        else:
            
            self.itemconfigure(self.on_text_id, state='hidden')
            self.itemconfigure(self.off_text_id, state='normal')
    
    def create_rounded_rect(self, x1, y1, x2, y2, radius=15, **kwargs):
       
        points = []
        
       
        for i in range(0, 90):
            points.append(x1 + radius - (radius * math.cos(i * math.pi / 180)))
            points.append(y1 + radius - (radius * math.sin(i * math.pi / 180)))
            
        for i in range(90, 180):
            points.append(x2 - radius + (radius * math.cos(i * math.pi / 180)))
            points.append(y1 + radius - (radius * math.sin(i * math.pi / 180)))
            
        for i in range(180, 270):
            points.append(x2 - radius + (radius * math.cos(i * math.pi / 180)))
            points.append(y2 - radius + (radius * math.sin(i * math.pi / 180)))
            
        for i in range(270, 360):
            points.append(x1 + radius - (radius * math.cos(i * math.pi / 180)))
            points.append(y2 - radius + (radius * math.sin(i * math.pi / 180)))
            
        return self.create_polygon(points, **kwargs, smooth=True)
        
    def toggle(self, event=None):
        
        self.is_on = not self.is_on
        
        
        knob_diameter = self.height - 6
        
        
        self.itemconfig(
            self.track, 
            fill=self.track_off_color if not self.is_on else self.track_on_color
        )
        
        
        if self.is_on:
            for i in range(10):
                move_x = (self.width - knob_diameter - 6) / 10
                self.move(self.knob, move_x, 0)
                self.update()
                time.sleep(0.01)
        else:
            for i in range(10):
                move_x = -(self.width - knob_diameter - 6) / 10
                self.move(self.knob, move_x, 0)
                self.update()
                time.sleep(0.01)
        
        
        self.update_text_visibility()
        
        if self.callback:
            self.callback(self.is_on)
    
    def get(self):
        
        return self.is_on
    
    def set(self, state):
        
        if state != self.is_on:
            self.toggle()

class ImageLabel(tk.Label):
    
    def __init__(self, parent, image_path, **kwargs):
        super().__init__(parent, **kwargs)
        self.image_path = image_path
        self.image = None
        self.photo = None
        self.load_image()
        self.bind('<Configure>', self.resize_image)

    def load_image(self):
        
        try:
            self.image = Image.open(self.image_path)
            self.update_image()
        except Exception as e:
            print(f'Error loading image: {e}')
            self.config(text='BOFT ORGANIZER', font=("Segoe UI", 22, "bold"))

    def resize_image(self, event):
        
        if event.width > 1 and event.height > 1:
            self.update_image()

    def update_image(self):
        
        if self.image:
            
            width = self.winfo_width()
            height = self.winfo_height()
            
            
            if width > 1 and height > 1:
                
                img_width, img_height = self.image.size
                ratio = min(width/img_width, height/img_height)
                new_width = int(img_width * ratio)
                new_height = int(img_height * ratio)
                
                
                resized = self.image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(resized)
                self.config(image=self.photo)

def toggle_autostart(enabled=None):
    
    global config
    
    
    if enabled is None:
        enabled = not config.get("autostart_enabled", False)
    
    config["autostart_enabled"] = enabled
    

    script_path = os.path.abspath(sys.argv[0])
    
    try:
        if platform.system() == "Windows":
            
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
            )
            
            if enabled:
                
                winreg.SetValueEx(key, "BOFT Organizer", 0, winreg.REG_SZ, f'"{sys.executable}" "{script_path}" --startup')
                update_status("Added to Windows startup")
            else:
                
                try:
                    winreg.DeleteValue(key, "BOFT Organizer")
                    update_status("Removed from Windows startup")
                except FileNotFoundError:
                    
                    pass
            
            winreg.CloseKey(key)
        
        elif platform.system() == "Darwin":  
           
            launch_agent_dir = os.path.expanduser("~/Library/LaunchAgents")
            os.makedirs(launch_agent_dir, exist_ok=True)
            plist_path = os.path.join(launch_agent_dir, "com.boft.organizer.plist")
            
            if enabled:
                
                plist_content = {
                    'Label': 'com.boft.organizer',
                    'ProgramArguments': [sys.executable, script_path, '--startup'],
                    'RunAtLoad': True,
                    'KeepAlive': False,
                }
                
                with open(plist_path, 'wb') as f:
                    plistlib.dump(plist_content, f)
                
                
                try:
                    subprocess.run(['launchctl', 'load', plist_path], check=True)
                    update_status("Added to macOS startup")
                except subprocess.CalledProcessError as e:
                    messagebox.showerror("Error", f"Failed to add to startup: {e}")
            else:
                
                if os.path.exists(plist_path):
                    try:
                       
                        subprocess.run(['launchctl', 'unload', plist_path], check=True)
                    except subprocess.CalledProcessError:
                       
                        pass
                    
                    
                    os.remove(plist_path)
                    update_status("Removed from macOS startup")
        
        elif platform.system() == "Linux":
            autostart_dir = os.path.expanduser("~/.config/autostart")
            os.makedirs(autostart_dir, exist_ok=True)
            desktop_path = os.path.join(autostart_dir, "boft-organizer.desktop")
            
            if enabled:
                
                with open(desktop_path, 'w') as f:
                    f.write(f)
                update_status("Added to Linux startup")
            else:
                
                if os.path.exists(desktop_path):
                    os.remove(desktop_path)
                    update_status("Removed from Linux startup")
        
        
        save_config()
        
        
        if 'autostart_switch' in globals() and autostart_switch:
            autostart_switch.set(enabled)
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to {('add to' if enabled else 'remove from')} startup: {e}")
        print(f"Autostart error: {e}")
        return False
    
    return True

def exit_program(icon=None):
    
    global auto_organize_running, observer, tray_icon, root
    
    
    if auto_organize_running:
        stop_auto_organize()
    
    
    if observer is not None:
        stop_file_watcher()
    
    
    if root.winfo_viewable():  
        config["window_size"] = f"{root.winfo_width()}x{root.winfo_height()}"
        save_config()
    
    
    if tray_icon is not None:
        try:
            tray_icon.stop()
        except Exception as e:
            print(f"Error stopping tray icon: {e}")
    
    
    try:
        root.quit()
        root.destroy()
    except Exception as e:
        print(f"Error destroying root window: {e}")
    
    
    sys.exit(0)

def minimize_to_tray():
    
    global tray_icon, root
    
    
    root.withdraw()
    
    
    if tray_icon is None:
        
        icon_image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(icon_image)
        draw.ellipse((4, 4, 60, 60), fill='#4CAF50')  
        
        try:
            
            menu_items = (
                MenuItem('Open BOFT Organizer', restore_window),
                MenuItem('Exit', exit_program)
            )
            
            
            tray_menu = Menu(*menu_items)
            
            
            tray_icon = Icon("boft_organizer", icon_image, "BOFT Organizer", tray_menu)
            
            
            threading.Thread(target=tray_icon.run, daemon=True).start()
            
            update_status("Application minimized to tray")
        except Exception as e:
            print(f"Error creating tray icon: {e}")
            
            restore_window()
            messagebox.showwarning(
                "Tray Icon Error", 
                f"Could not create system tray icon. The application will run in window mode.\nError: {e}"
            )

def restore_window(icon=None):
    
    global root
    
    
    root.deiconify()
    
    
    root.lift()
    root.focus_force()
    
    
    if platform.system() == "Darwin":
        try:
            
            root.attributes("-topmost", True)
            root.attributes("-topmost", False)
        except Exception as e:
            print(f"Error bringing window to front on macOS: {e}")
    
    update_status("Application restored from tray")


load_config()


root = tk.Tk()
root.title("BOFT Organizer")
root.configure(bg="#0A0A0A")  


window_size = config.get("window_size", "700x500")
root.geometry(window_size)


root.minsize(600, 400)


if platform.system() == "Windows":
    try:
        
        icon_size = 64
        icon_img = Image.new('RGBA', (icon_size, icon_size), color=(0, 0, 0, 255))  
        draw = ImageDraw.Draw(icon_img)
        
        
        try:
            font = ImageFont.truetype("arial.ttf", 48)  
        except (IOError, ImportError):
            font = None
            
        
        text = "B"
        if font:
            
            try:
                
                left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
                text_width = right - left
                text_height = bottom - top
            except AttributeError:
                
                text_width, text_height = draw.textsize(text, font=font)
                
            
            position = ((icon_size - text_width) // 2, (icon_size - text_height) // 2)
            
            draw.text(position, text, fill=(255, 255, 255, 255), font=font)
        else:
            
            draw.text((20, 10), text, fill=(255, 255, 255, 255))
            
        icon_photo = ImageTk.PhotoImage(icon_img)
        root.iconphoto(True, icon_photo)
    except Exception as e:
        print(f"Error setting Windows icon: {e}")
elif platform.system() == "Darwin":  
    
    
    pass
else:  
    try:
        
        icon_size = 64
        icon_img = Image.new('RGBA', (icon_size, icon_size), color=(0, 0, 0, 255))  
        draw = ImageDraw.Draw(icon_img)
        
        
        try:
            font = ImageFont.truetype("arial.ttf", 48)  
        except (IOError, ImportError):
            font = None
            
        
        text = "B"
        if font:
            
            try:
                
                left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
                text_width = right - left
                text_height = bottom - top
            except AttributeError:
                
                text_width, text_height = draw.textsize(text, font=font)
                
            
            position = ((icon_size - text_width) // 2, (icon_size - text_height) // 2)
            
            draw.text(position, text, fill=(255, 255, 255, 255), font=font)
        else:
            
            draw.text((20, 10), text, fill=(255, 255, 255, 255))
            
        icon_photo = ImageTk.PhotoImage(icon_img)
        root.iconphoto(True, icon_photo)
    except Exception as e:
        print(f"Error setting Linux icon: {e}")


is_dark_mode = True


title_font = ("Segoe UI", 22, "bold")
subtitle_font = ("Segoe UI", 14)
label_font = ("Segoe UI", 10)
status_font = ("Segoe UI", 10, "italic")
button_font = ("Segoe UI", 11, "bold")  
footer_font = ("Segoe UI", 9, "italic")


main_container = tk.Frame(root, bg="#0A0A0A")
main_container.pack(fill="both", expand=True)


header_frame = tk.Frame(main_container, bg="#0A0A0A")
header_frame.pack(fill="x", pady=(10, 5))


autostart_frame = tk.Frame(header_frame, bg="#0A0A0A")
autostart_frame.pack(side="left", padx=10, pady=5, anchor="nw")

autostart_label = tk.Label(
    autostart_frame, 
    text="Start with System", 
    bg="#0A0A0A",
    fg="#E0E0E0",
    font=("Segoe UI", 8)  
)
autostart_label.pack(side="left", padx=(0, 5))


ios_switch = CustomSwitch(
    autostart_frame, 
    width=40,  
    height=20,  
    bg="#0A0A0A",
    callback=lambda x: toggle_autostart(),
    is_on=config.get("autostart_enabled", False),
    label="Autostart"
)
ios_switch.pack(side="left")


header_center = tk.Frame(header_frame, bg="#0A0A0A")
header_center.pack(side="top", fill="x")


title_container = tk.Frame(main_container, bg="#0A0A0A")
title_container.pack(fill="x", pady=(5, 10))


image_frame = tk.Frame(title_container, width=400, height=100, bg="#0A0A0A")
image_frame.pack(pady=10, side="top", anchor="center")
image_frame.pack_propagate(False)  


image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'BOFT.png')


if os.path.exists(image_path):
    image_label = ImageLabel(
        image_frame,
        image_path=image_path,
        bg="#0A0A0A"
    )
    image_label.pack(fill='both', expand=True)
else:
    
    title_label = tk.Label(
        image_frame, 
        text="BOFT ORGANIZER", 
        fg="#E0E0E0", 
        bg="#0A0A0A", 
        font=title_font
    )
    title_label.pack(fill='both', expand=True)


subtitle_label = tk.Label(
    main_container, 
    text="Simple File Organization System", 
    fg="#999999", 
    bg="#0A0A0A", 
    font=subtitle_font
)
subtitle_label.pack(pady=(0, 20))


status_text = tk.Label(
    main_container, 
    text="Status: Ready", 
    fg="#999999", 
    bg="#0A0A0A", 
    font=status_font
)
status_text.pack(pady=5, anchor="center")


button_frame = tk.Frame(
    main_container, 
    bg="#0A0A0A"
)
button_frame.pack(fill="both", expand=True, padx=20, pady=10)


left_column = tk.Frame(
    button_frame, 
    bg="#0A0A0A"
)
left_column.pack(side="left", fill="both", expand=True, padx=(0, 10))

right_column = tk.Frame(
    button_frame, 
    bg="#0A0A0A"
)
right_column.pack(side="right", fill="both", expand=True, padx=(10, 0))


def create_rounded_rectangle(canvas, x1, y1, x2, y2, radius=15, **kwargs):
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1
    ]
    return canvas.create_polygon(points, **kwargs, smooth=True)


def create_rounded_button_in_frame(parent_frame, text, command, tooltip_text=None):
    btn_canvas = tk.Canvas(
        parent_frame, 
        width=260, 
        height=42, 
        bg="#0A0A0A", 
        highlightthickness=0
    )
    btn_canvas.pack(pady=8, anchor="center")
    
    
    btn_id = create_rounded_rectangle(
        btn_canvas, 5, 5, 255, 37, 
        radius=15, 
        fill="#1A1A1A", 
        outline="#353535"  
    )
    btn_canvas.addtag_withtag("button", btn_id)
    
    
    btn_text = btn_canvas.create_text(
        130, 21, 
        text=text, 
        fill="#E0E0E0", 
        font=button_font
    )
    btn_canvas.addtag_withtag("text", btn_text)
    
    def on_click(event):
        
        original_fill = "#1A1A1A"
        highlight_fill = "#353535"
        
        btn_canvas.itemconfig(btn_id, fill=highlight_fill)
        btn_canvas.update()
        btn_canvas.after(100, lambda: btn_canvas.itemconfig(btn_id, fill=original_fill))
        command()
    
    def on_hover(event):
        
        btn_canvas.itemconfig(
            btn_id, 
            fill="#252525"
        )
        
        btn_canvas.itemconfig(
            btn_text,
            fill="#FFFFFF"
        )
        
        if tooltip_text:
            show_tooltip(event.widget, tooltip_text)
    
    def on_leave(event):
        btn_canvas.itemconfig(
            btn_id, 
            fill="#1A1A1A"
        )
        
        btn_canvas.itemconfig(
            btn_text,
            fill="#E0E0E0"
        )
        
        if tooltip_text:
            hide_tooltip()
    
    btn_canvas.bind("<Button-1>", on_click)
    btn_canvas.bind("<Enter>", on_hover)
    btn_canvas.bind("<Leave>", on_leave)
    
    return btn_canvas


tooltip = None
def show_tooltip(widget, text):
    global tooltip
    
    
    x = widget.winfo_pointerx() + 15
    y = widget.winfo_pointery() + 10
    
    
    hide_tooltip()
    
    
    tooltip = tk.Toplevel()
    tooltip.wm_overrideredirect(True)  
    tooltip.wm_geometry(f"+{x}+{y}")
    
    
    frame = tk.Frame(tooltip, borderwidth=1, relief="solid", 
                     bg="#353535")
    frame.pack(fill="both", expand=True)
    
    
    label = tk.Label(frame, text=text, justify=tk.LEFT, padx=5, pady=3,
                    bg="#353535",
                    fg="#E0E0E0",
                    wraplength=250)
    label.pack()
    
    def on_close(event):
        hide_tooltip()
    
    tooltip.bind("<Button-1>", on_close)

def hide_tooltip():
    global tooltip
    if tooltip:
        tooltip.destroy()
        tooltip = None


def show_progress(text, progress=None):
    global progress_frame, progress_bar, progress_label
    
    if 'progress_frame' not in globals() or not progress_frame.winfo_exists():
        
        progress_frame = tk.Frame(main_container, bg="#0A0A0A")
        progress_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        progress_label = tk.Label(
            progress_frame, 
            text=text,
            bg="#0A0A0A",
            fg="#E0E0E0",
            font=label_font
        )
        progress_label.pack(anchor="w", pady=(0, 5))
        
        progress_bar = tk.Canvas(
            progress_frame, 
            width=660, 
            height=10, 
            bg="#222222",
            highlightthickness=0
        )
        progress_bar.pack(fill="x", pady=(0, 5))
        
        
        progress_bar.create_rectangle(
            0, 0, 0, 10, 
            fill="#4CAF50", 
            outline="",
            tags="progress_fill"
        )
    else:
        
        progress_label.config(text=text)
        if progress is not None:
            
            width = progress_bar.winfo_width()
            fill_width = int(width * progress)
            progress_bar.coords("progress_fill", 0, 0, fill_width, 10)
    
    
    root.update()

def hide_progress():
    global progress_frame
    if 'progress_frame' in globals() and progress_frame.winfo_exists():
        progress_frame.destroy()


def log_activity(action, source_path, destination_path=None, file_type=None):
    global recent_activities, stats
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    activity = {
        "timestamp": timestamp,
        "action": action,
        "source": source_path,
        "destination": destination_path,
        "file_type": file_type
    }
    
    recent_activities.append(activity)
    
    if len(recent_activities) > MAX_RECENT_ACTIVITIES:
        recent_activities = recent_activities[-MAX_RECENT_ACTIVITIES:]
    
    
    if action == "Organized":
        
        stats["total_files_organized"] += 1
        
        
        stats["last_organized"] = timestamp
        
        
        if file_type:
            
            if file_type.startswith('.'):
                file_type = file_type[1:]
            file_type = file_type.lower()
            
            if file_type in stats["files_by_type"]:
                stats["files_by_type"][file_type] += 1
            else:
                stats["files_by_type"][file_type] = 1
        
        
        try:
            if source_path and destination_path:
                source_drive = os.path.splitdrive(source_path)[0]
                dest_drive = os.path.splitdrive(destination_path)[0]
                
                if source_drive != dest_drive and os.path.exists(destination_path):
                    file_size = os.path.getsize(destination_path)
                    stats["space_saved"] += file_size
        except OSError as e:
            print(f"Error calculating space saved: {e}")
    
    
    save_config()


def show_custom_organization():
    custom_org_window = tk.Toplevel(root)
    custom_org_window.title("Custom Organization Tool")
    custom_org_window.geometry("400x200")
    custom_org_window.configure(bg="#0A0A0A")
    
    
    header = tk.Label(
        custom_org_window, 
        text="Custom File Organization", 
        font=title_font,
        bg="#0A0A0A",
        fg="#E0E0E0"
    )
    header.pack(pady=10)
    
    
    main_frame = tk.Frame(custom_org_window, bg="#0A0A0A")
    main_frame.pack(fill="both", expand=True, padx=20, pady=10)
    
    
    tag_label = tk.Label(
        main_frame,
        text="Enter Name Tag:",
        font=("Segoe UI", 10),
        bg="#0A0A0A",
        fg="#E0E0E0",
        anchor="w"
    )
    tag_label.pack(anchor="w", pady=(0, 5))
    
    tag_var = tk.StringVar()
    tag_entry = tk.Entry(
        main_frame,
        textvariable=tag_var,
        width=40,
        bg="#1A1A1A",
        fg="#E0E0E0",
        insertbackground="#E0E0E0"
    )
    tag_entry.pack(fill="x", pady=5)
    
    
    organize_by_tags_button = tk.Button(
        main_frame,
        text="Organize by Tag",
        command=lambda: organize_by_name_tags(tag_var.get()),
        bg="#1E88E5",
        fg="#FFFFFF",
        relief="flat",
        padx=15,
        pady=5
    )
    organize_by_tags_button.pack(pady=15)
    
    
    folder_frame = tk.Frame(custom_org_window, bg="#1A1A1A", padx=15, pady=15)
    folder_frame.pack(fill="x", padx=20, pady=10)
    
    folder_label = tk.Label(
        folder_frame,
        text="Target Folder:",
        font=("Segoe UI", 10, "bold"),
        bg="#1A1A1A",
        fg="#E0E0E0"
    )
    folder_label.pack(side="left", padx=(0, 10))
    
    folder_path_var = tk.StringVar()
    if auto_organize_folder:
        folder_path_var.set(auto_organize_folder)
    
    folder_entry = tk.Entry(
        folder_frame,
        textvariable=folder_path_var,
        width=40,
        bg="#0A0A0A",
        fg="#E0E0E0",
        insertbackground="#E0E0E0"
    )
    folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    
    browse_button = tk.Button(
        folder_frame,
        text="Browse",
        command=lambda: folder_path_var.set(filedialog.askdirectory()),
        bg="#333333",
        fg="#FFFFFF",
        relief="flat"
    )
    browse_button.pack(side="left")
    
    
    close_button = tk.Button(
        custom_org_window, 
        text="Close", 
        command=custom_org_window.destroy,
        bg="#1A1A1A",
        fg="#E0E0E0",
        relief="flat",
        padx=20
    )
    close_button.pack(pady=10)

def organize_by_name_tags(tag):
    folder_path = folder_path_var.get()
    if not folder_path:
        messagebox.showerror("Error", "Please select a target folder")
        return
    
    if not os.path.exists(folder_path):
        messagebox.showerror("Error", "Selected folder does not exist")
        return
    
    update_status(f"Starting tag-based organization of {folder_path}")
    
    
    files = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            files.append(file_path)
    
    total_files = len(files)
    if total_files == 0:
        update_status("No files to organize")
        return
    
    update_status(f"Found {total_files} files to organize by tags")
    
    
    tag_files = []
    for file_path in files:
        filename = os.path.basename(file_path)
        name_part = os.path.splitext(filename)[0]
        
        if tag in name_part:
            tag_files.append(file_path)
    
    if not tag_files:
        messagebox.showinfo("No Files Found", f"No files with the tag '{tag}' were found")
        return
    
    
    tag_folder = os.path.join(folder_path, f"Tag_{tag}")
    if not os.path.exists(tag_folder):
        os.makedirs(tag_folder)
    
    organized_count = 0
    
    for file_path in tag_files:
        filename = os.path.basename(file_path)
        destination_file = os.path.join(tag_folder, filename)
        
        
        if "BOFT.pyw" in file_path:
            continue
        
        
        try:
            shutil.move(file_path, destination_file)
            log_activity("Tag Organized", file_path, destination_file)
            organized_count += 1
        except Exception as e:
            update_status(f"Error moving {filename}: {str(e)}")
    
    update_status(f"Tag organization complete. Organized {organized_count} files into the '{tag}' tag folder.")
    messagebox.showinfo("Organization Complete", f"Organized {organized_count} files into the '{tag}' tag folder.")


def show_recent_activities():
    activities_window = tk.Toplevel(root)
    activities_window.title("Recent Activities")
    activities_window.geometry("700x500")
    activities_window.configure(bg="#0A0A0A")
    
    
    header = tk.Label(
        activities_window, 
        text="Recent File Organization Activities", 
        font=title_font,
        bg="#0A0A0A",
        fg="#E0E0E0"
    )
    header.pack(pady=10)
    
    
    frame = tk.Frame(activities_window, bg="#0A0A0A")
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")
    
    
    columns = ("Time", "Action", "Source", "Destination", "Type")
    
    
    tree = ttk.Treeview(
        frame, 
        columns=columns,
        show="headings",
        yscrollcommand=scrollbar.set
    )
    
    
    tree.column("Time", width=120, anchor="w")
    tree.column("Action", width=100, anchor="w")
    tree.column("Source", width=150, anchor="w")
    tree.column("Destination", width=150, anchor="w")
    tree.column("Type", width=80, anchor="w")
    
    for col in columns:
        tree.heading(col, text=col)
    
    
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview", 
                    background="#121212", 
                    foreground="#E0E0E0", 
                    fieldbackground="#121212",
                    borderwidth=0)
    style.configure("Treeview.Heading", 
                    background="#1A1A1A", 
                    foreground="#E0E0E0",
                    borderwidth=1)
    style.map('Treeview', background=[('selected', '#353535')])
    
    
    for i, activity in enumerate(reversed(recent_activities)):
        source = os.path.basename(activity["source"]) if activity["source"] else "N/A"
        destination = os.path.basename(activity["destination"]) if activity["destination"] else "N/A"
        file_type = activity["file_type"] if activity["file_type"] else "N/A"
        
        tree.insert("", "end", values=(
            activity["timestamp"],
            activity["action"],
            source,
            destination,
            file_type
        ))
    
    tree.pack(fill="both", expand=True)
    scrollbar.config(command=tree.yview)
    
    
    close_button = tk.Button(
        activities_window, 
        text="Close", 
        command=activities_window.destroy,
        bg="#1A1A1A",
        fg="#E0E0E0",
        relief="flat",
        padx=20
    )
    close_button.pack(pady=10)


def show_status_history():
    if 'status_history' not in globals() or not status_history:
        messagebox.showinfo("Status History", "No status history available.")
        return
        
    history_window = tk.Toplevel(root)
    history_window.title("Status History")
    history_window.geometry("500x400")
    history_window.configure(bg="#0A0A0A")
    
    
    header = tk.Label(
        history_window, 
        text="Status History", 
        font=title_font,
        bg="#0A0A0A",
        fg="#E0E0E0"
    )
    header.pack(pady=10)
    
    
    frame = tk.Frame(history_window, bg="#0A0A0A")
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")
    
    
    history_text = tk.Text(
        frame, 
        wrap="word", 
        bg="#121212",
        fg="#E0E0E0",
        height=20,
        yscrollcommand=scrollbar.set
    )
    history_text.pack(fill="both", expand=True)
    scrollbar.config(command=history_text.yview)
    
    
    for entry in status_history:
        history_text.insert("end", entry + "\n")
    
    
    history_text.config(state="disabled")
    
    
    close_btn = tk.Button(
        history_window, 
        text="Close", 
        command=history_window.destroy,
        bg="#1A1A1A",
        fg="#E0E0E0",
        relief="flat",
        padx=20
    )
    close_btn.pack(pady=10)


all_buttons = []


def edit_file_categories():
    categories_window = tk.Toplevel(root)
    categories_window.title("File Type Categories")
    categories_window.geometry("700x600")
    categories_window.configure(bg="#0A0A0A")
    
    
    header = tk.Label(
        categories_window, 
        text="Customize File Type Categories", 
        font=title_font,
        bg="#0A0A0A",
        fg="#E0E0E0"
    )
    header.pack(pady=10)
    
    
    main_frame = tk.Frame(categories_window, bg="#0A0A0A")
    main_frame.pack(fill="both", expand=True, padx=20, pady=10)
    
    
    canvas = tk.Canvas(main_frame, bg="#0A0A0A", highlightthickness=0)
    scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="#0A0A0A")
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    
    category_entries = {}
    
    
    def add_new_category():
        new_category_name = new_category_entry.get().strip()
        if not new_category_name:
            messagebox.showerror("Error", "Please enter a category name")
            return
        
        if new_category_name in file_categories:
            messagebox.showerror("Error", f"Category '{new_category_name}' already exists")
            return
        
        
        file_categories[new_category_name] = []
        
        
        new_category_entry.delete(0, tk.END)
        
        
        categories_window.destroy()
        edit_file_categories()
    
    
    def delete_category(category):
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the '{category}' category?"):
            del file_categories[category]
            save_config()
            
            categories_window.destroy()
            edit_file_categories()
    
    
    def save_changes():
        
        for category, entry in category_entries.items():
            extensions_text = entry.get("1.0", tk.END).strip()
            extensions = [ext.strip() for ext in extensions_text.split(",") if ext.strip()]
            
            
            extensions = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]
            
            file_categories[category] = extensions
        
        save_config()
        update_status("File type categories saved")
        categories_window.destroy()
    
    
    def reset_to_defaults():
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to reset all categories to default values?"):
            global file_categories
            file_categories = DEFAULT_CONFIG["file_categories"].copy()
            save_config()
            
            categories_window.destroy()
            edit_file_categories()
    
    
    row = 0
    for category, extensions in sorted(file_categories.items()):
        
        category_frame = tk.Frame(scrollable_frame, bg="#121212", padx=10, pady=10, bd=1, relief="solid")
        category_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
        
        
        header_frame = tk.Frame(category_frame, bg="#121212")
        header_frame.pack(fill="x", expand=True)
        
        category_label = tk.Label(
            header_frame,
            text=category,
            font=("Segoe UI", 12, "bold"),
            bg="#121212",
            fg="#E0E0E0",
            anchor="w"
        )
        category_label.pack(side="left", pady=5)
        
        delete_button = tk.Button(
            header_frame,
            text="Delete",
            command=lambda cat=category: delete_category(cat),
            bg="#8B0000",
            fg="#FFFFFF",
            relief="flat",
            padx=10
        )
        delete_button.pack(side="right", pady=5)
        
        
        extensions_label = tk.Label(
            category_frame,
            text="File Extensions (comma-separated):",
            font=("Segoe UI", 10),
            bg="#121212",
            fg="#E0E0E0",
            anchor="w"
        )
        extensions_label.pack(anchor="w", pady=(10, 5))
        
        extensions_text = tk.Text(
            category_frame,
            height=3,
            width=60,
            bg="#1A1A1A",
            fg="#E0E0E0",
            insertbackground="#E0E0E0"
        )
        extensions_text.pack(fill="x", pady=5)
        
        
        extensions_text.insert("1.0", ", ".join(extensions))
        
        
        category_entries[category] = extensions_text
        
        row += 1
    
    
    new_category_frame = tk.Frame(scrollable_frame, bg="#121212", padx=10, pady=10, bd=1, relief="solid")
    new_category_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
    
    new_category_label = tk.Label(
        new_category_frame,
        text="Add New Category:",
        font=("Segoe UI", 12, "bold"),
        bg="#121212",
        fg="#E0E0E0",
        anchor="w"
    )
    new_category_label.pack(anchor="w", pady=5)
    
    entry_frame = tk.Frame(new_category_frame, bg="#121212")
    entry_frame.pack(fill="x", expand=True, pady=5)
    
    new_category_entry = tk.Entry(
        entry_frame,
        bg="#1A1A1A",
        fg="#E0E0E0",
        insertbackground="#E0E0E0",
        width=40
    )
    new_category_entry.pack(side="left", padx=(0, 10))
    
    add_button = tk.Button(
        entry_frame,
        text="Add Category",
        command=add_new_category,
        bg="#1A1A1A",
        fg="#E0E0E0",
        relief="flat",
        padx=10
    )
    add_button.pack(side="left")
    
    
    scrollable_frame.grid_columnconfigure(0, weight=1)
    
    
    buttons_frame = tk.Frame(categories_window, bg="#0A0A0A")
    buttons_frame.pack(fill="x", pady=10)
    
    
    reset_button = tk.Button(
        buttons_frame,
        text="Reset to Defaults",
        command=reset_to_defaults,
        bg="#8B0000",
        fg="#FFFFFF",
        relief="flat",
        padx=15
    )
    reset_button.pack(side="left", padx=20)
    
    
    save_button = tk.Button(
        buttons_frame,
        text="Save Changes",
        command=save_changes,
        bg="#006400",
        fg="#FFFFFF",
        relief="flat",
        padx=15
    )
    save_button.pack(side="right", padx=20)


all_buttons.append(create_rounded_button_in_frame(
    left_column, 
    "Start Manual-Organize", 
    browse_directory,
    "Select a folder to organize its files into categories\nlike Images, Documents, Videos, etc."
))

all_buttons.append(create_rounded_button_in_frame(
    left_column, 
    "Set Auto-Organize Folder", 
    set_auto_organize_folder,
    "Choose a folder to be automatically organized\nwhenever new files are added."
))

all_buttons.append(create_rounded_button_in_frame(
    left_column, 
    "View Recent Activities", 
    show_recent_activities,
    "View a log of recently organized files\nwith timestamps and destinations."
))

all_buttons.append(create_rounded_button_in_frame(
    right_column, 
    "Start Auto-Organize", 
    start_auto_organize,
    "Begin monitoring the selected folder for changes\nand automatically organize new files."
))

all_buttons.append(create_rounded_button_in_frame(
    right_column, 
    "Stop Auto-Organize", 
    stop_auto_organize,
    "Stop the automatic folder monitoring\nand organization process."
))

all_buttons.append(create_rounded_button_in_frame(
    right_column, 
    "Custom Organization", 
    show_custom_organization,
    "Use custom organization options like organizing by name tags."
))


if auto_organize_folder:
    update_status(f"Auto-organize folder: {auto_organize_folder}")
else:
    update_status("No auto-organize folder set")


if config.get("run_on_startup", False) and auto_organize_folder:
    root.after(1000, start_auto_organize)  


if IS_STARTUP_MODE:
    root.after(500, minimize_to_tray)  


def on_closing():
    
    try:
        
        root.deiconify()
        root.lift()
        root.focus_force()
    except Exception as e:
        print(f"Error restoring window: {e}")
    minimize_to_tray()
    return "break"

root.protocol("WM_DELETE_WINDOW", on_closing)


footer_label = tk.Label(
    main_container, 
    text="Made by Ahmed Elbaroudy", 
    fg="#666666", 
    bg="#0A0A0A", 
    font=footer_font
)
footer_label.pack(pady=(20, 10), anchor="center")  

def apply_dark_theme():
    dark_colors = {
        "bg": "#0A0A0A",
        "text": "#E0E0E0",
        "subtext": "#999999",
        "button": "#1A1A1A",
        "button_hover": "#252525",
        "button_outline": "#252525",
        "track_off_color": "#D32F2F",  
        "track_on_color": "#4CAF50",   
        "footer": "#666666",
    }
    
    colors = dark_colors
    
    
    root.configure(bg=colors["bg"])
    main_container.configure(bg=colors["bg"])
    header_frame.configure(bg=colors["bg"])
    autostart_frame.configure(bg=colors["bg"])
    autostart_label.configure(bg=colors["bg"], fg=colors["text"])
    title_container.configure(bg=colors["bg"])
    image_frame.configure(bg=colors["bg"])
    
    
    if 'image_label' in globals():
        image_label.configure(bg=colors["bg"])
    if 'title_label' in globals():
        title_label.configure(bg=colors["bg"], fg=colors["text"])
        
    subtitle_label.configure(bg=colors["bg"], fg=colors["subtext"])
    status_text.configure(bg=colors["bg"], fg=colors["subtext"])
    button_frame.configure(bg=colors["bg"])
    left_column.configure(bg=colors["bg"])
    right_column.configure(bg=colors["bg"])
    
    
    for btn in all_buttons:
        btn.configure(bg=colors["bg"])
        btn.itemconfig("button", fill=colors["button"], outline=colors["button_outline"])
        btn.itemconfig("text", fill=colors["text"])
    
    
    ios_switch.track_on_color = colors["track_on_color"]
    ios_switch.track_off_color = colors["track_off_color"]
    ios_switch.itemconfig(ios_switch.track, fill=ios_switch.track_on_color if ios_switch.is_on else ios_switch.track_off_color)
    
    
    footer_label.configure(bg=colors["bg"], fg=colors["footer"])

apply_dark_theme()

if __name__ == "__main__":
    
    if 'Icon' in globals() and IS_STARTUP_MODE:
        root.after(500, minimize_to_tray)  
    root.mainloop()
