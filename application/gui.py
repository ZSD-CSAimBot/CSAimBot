import threading
import tkinter as tk
from tkinter import ttk


class GUI:
    """
    Graphical User Interface for controlling the AimBot.
    """
    def __init__(self, root, aimbot):
        self.root = root
        self.aimbot = aimbot
        self.bot_thread = None

        self.root.title("CSAimBot Control Panel")
        self.root.geometry("300x160")
        self.root.resizable(False, False)

        style = ttk.Style()
        style.theme_use('vista')

        self.create_widgets()

    def create_widgets(self):
        frame_controls = ttk.LabelFrame(self.root, text="Kontrola Detekcji", padding=(10, 10))
        frame_controls.pack(fill="x", padx=10, pady=10)

        self.btn_start = ttk.Button(frame_controls, text="START", command=self.start_aimbot)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=5)

        self.btn_stop = ttk.Button(frame_controls, text="STOP", command=self.stop_aimbot, state="disabled")
        self.btn_stop.pack(side="right", expand=True, fill="x", padx=5)

        frame_vision = ttk.LabelFrame(self.root, text="Wizualizacja", padding=(10, 10))
        frame_vision.pack(fill="x", padx=10, pady=5)

        self.var_vision = tk.BooleanVar(value=True)
        self.chk_vision = ttk.Checkbutton(frame_vision, text="Pokaż okienko OpenCV (Debug)", variable=self.var_vision, command=self.update_settings)
        self.chk_vision.pack(anchor="w")

    def update_settings(self):
        self.aimbot.show_debug_window = self.var_vision.get()

    def start_aimbot(self):
        if not self.aimbot.is_running:
            self.aimbot.is_running = True
            self.update_settings()
            self.aimbot_thread = threading.Thread(target=self.aimbot.run, daemon=True)
            self.aimbot_thread.start()
            
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")

    def stop_aimbot(self):
        if self.aimbot.is_running:
            self.aimbot.is_running = False
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")

    def on_closing(self):
        self.stop_aimbot()
        self.root.destroy()
        self.aimbot.cleanup()