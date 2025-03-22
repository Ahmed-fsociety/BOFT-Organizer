import os
import shutil
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw


auto_organize_folder = None
auto_organize_running = False
tray_icon = None

def organize_files_by_type(directory):
    if not os.path.exists(directory):
        messagebox.showerror("Error", "The specified directory does not exist.")
        return

    os.chdir(directory)

    for filename in os.listdir(directory):
        full_path = os.path.join(directory, filename)

        if os.path.isdir(full_path):
            continue

        _, file_extension = os.path.splitext(filename)
        file_extension = file_extension[1:]

        if not file_extension:
            file_extension = "misc"

        folder_name = f"{file_extension.lower()}_files"

        if not os.path.exists(folder_name):
            os.mkdir(folder_name)

        dest_path = os.path.join(folder_name, filename)
        counter = 1
        while os.path.exists(dest_path):
            name, ext = os.path.splitext(filename)
            dest_path = os.path.join(folder_name, f"{name}_{counter}{ext}")
            counter += 1

        shutil.move(full_path, dest_path)

    messagebox.showinfo("Success", "Files have been organized successfully!")

def browse_directory():
    directory = filedialog.askdirectory(title="Select Directory to Organize")
    if directory:
        organize_files_by_type(directory)

def set_auto_organize_folder():
    global auto_organize_folder
    folder = filedialog.askdirectory(title="Select Folder to Auto-Organize")
    if folder:
        auto_organize_folder = folder
        messagebox.showinfo("Success", f"Auto-organize folder set to: {auto_organize_folder}")

def start_auto_organize():
    global auto_organize_running
    if auto_organize_folder:
        auto_organize_running = True
        threading.Thread(target=auto_organize_loop, daemon=True).start()
        messagebox.showinfo("Success", "Auto-organize started!")
    else:
        messagebox.showerror("Error", "No folder selected for auto-organize.")

def stop_auto_organize():
    global auto_organize_running
    auto_organize_running = False
    messagebox.showinfo("Success", "Auto-organize stopped.")

def auto_organize_loop():
    while auto_organize_running:
        organize_files_by_type(auto_organize_folder)
        time.sleep(60)

def exit_program(icon):
    global auto_organize_running
    auto_organize_running = False
    icon.stop()
    root.destroy()

def minimize_to_tray():
    root.withdraw()

def restore_window():
    if tray_icon:
        tray_icon.stop()
    root.deiconify()


root = tk.Tk()
root.title("BOFT Organizer")
root.geometry("500x450") 
root.configure(bg="#121212")



font_style = ("OCR A Extended", 12, "bold")


title_label = tk.Label(root, text="BOFT ORGANIZER", fg="white", bg="#121212", font=("OCR A Extended", 16, "bold"))
title_label.pack(pady=(20, 5))  

subtitle_label = tk.Label(root, text="Select a directory to organize:", fg="#bbbbbb", bg="#121212", font=font_style)
subtitle_label.pack(pady=(0, 20))

def create_rounded_rectangle(canvas, x1, y1, x2, y2, radius=15, **kwargs):
    points = [
        x1 + radius, y1,
        x1 + radius, y1,
        x2 - radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1 + radius,
        x1, y1
    ]
    return canvas.create_polygon(points, **kwargs, smooth=True)


def create_rounded_button(text, command):
    btn_canvas = tk.Canvas(root, width=260, height=42, bg="#121212", highlightthickness=0)
    btn_canvas.pack(pady=8)  

    btn_id = create_rounded_rectangle(btn_canvas, 5, 5, 255, 37, radius=15, fill="#1E1E1E", outline="#1E1E1E")
    btn_text = btn_canvas.create_text(130, 21, text=text, fill="white", font=font_style)

    def on_click(event):
        command()

    def on_hover(event):
        btn_canvas.itemconfig(btn_id, fill="#333333")  
    def on_leave(event):
        btn_canvas.itemconfig(btn_id, fill="#1E1E1E")  

    btn_canvas.tag_bind(btn_id, "<Button-1>", on_click)
    btn_canvas.tag_bind(btn_text, "<Button-1>", on_click)
    btn_canvas.tag_bind(btn_id, "<Enter>", on_hover)
    btn_canvas.tag_bind(btn_text, "<Enter>", on_hover)
    btn_canvas.tag_bind(btn_id, "<Leave>", on_leave)
    btn_canvas.tag_bind(btn_text, "<Leave>", on_leave)


create_rounded_button("ðﾟﾓﾂ Start Manual-Organize", browse_directory)
create_rounded_button("⚙️ Set Auto-Organize", set_auto_organize_folder)
create_rounded_button("▶ Start Auto-Organize", start_auto_organize)
create_rounded_button("⏹ Stop Auto-Organize", stop_auto_organize)


root.protocol("WM_DELETE_WINDOW", minimize_to_tray)


footer_label = tk.Label(root, text="Made by Ahmed Elbaroudy", fg="#777777", bg="#121212", font=("OCR A Extended", 10))
footer_label.pack(pady=(20, 10))  


root.mainloop()
