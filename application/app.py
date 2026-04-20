import multiprocessing as mp
import os

from comms.comms import SerialCommsModule
from comms.comms import KeyboardInputModule
from detection_system.aimbot import vision_worker
from detection_system.yolo.export import export_model_to_trt
from gui_design.gui import GUI

if __name__ == "__main__":
    mp.freeze_support()

    MODEL_PATH = os.path.abspath('application/detection_system/yolo/trained_model.engine')
    if not os.path.exists(MODEL_PATH):
        print("Trwa eksport modelu do TensorRT. Proszę czekać...")
        export_model_to_trt()

    gui_conn, vision_conn = mp.Pipe()

    # Uruchomienie procesu odpowiedzialnego za logikę (AimBot / Robot)
    vision_process = mp.Process(
        target=vision_worker,
        args=(vision_conn, MODEL_PATH, 60),
        daemon=True
    )
    vision_process.start()

    # Uruchomienie interfejsu w głównym wątku
    esp = SerialCommsModule()
    keyboard = KeyboardInputModule()

    app = GUI(gui_conn, esp, keyboard)
    app.run()

    # Bezpieczne zamknięcie
    vision_process.join()
