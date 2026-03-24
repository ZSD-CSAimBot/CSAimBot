import os
import tkinter as tk

from detecion_system import AimBot
from gui import GUI


class App:
    """
    Main Application wrapper to initialize dependencies and start the UI loop.
    """
    def __init__(self, model_path):
        self.root = tk.Tk()
        self.aimbot = AimBot(model_path=model_path)
        self.gui = GUI(self.root, self.aimbot)
        self.root.protocol("WM_DELETE_WINDOW", self.gui.on_closing)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
        MODEL_PATH = os.path.abspath('./detection_system/yolo/training/Beta_v3/weights/best.engine')
        app = App(model_path=MODEL_PATH)
        app.run()