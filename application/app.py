import multiprocessing as mp
import os

from comms.comms import comms_worker
from detection_system.aimbot import vision_worker
from detection_system.yolo.export import export_model_to_trt
from gui_design.gui import GUI

if __name__ == "__main__":
    mp.freeze_support()

    MODEL_PATH = os.path.abspath('application/detection_system/yolo/trained_model.engine')
    if not os.path.exists(MODEL_PATH):
        print("Trwa eksport modelu do TensorRT. Proszę czekać...")
        export_model_to_trt()

    gui_vision_conn, vision_worker_conn = mp.Pipe()
    gui_comms_conn, comms_worker_conn = mp.Pipe()
    # Uruchomienie procesu odpowiedzialnego za logikę (AimBot / Robot)
    vision_process = mp.Process(
        target=vision_worker,
        args=(vision_worker_conn, MODEL_PATH, 60),
        daemon=True
    )
    vision_process.start()
    # Uruchomienie procesu odpowiedzialnego za komunikację
    comms_process = mp.Process(
        target=comms_worker,
        args=(comms_worker_conn,),
        daemon=True
    )
    comms_process.start()

    app = GUI(gui_vision_conn, gui_comms_conn)
    app.run()

    # Bezpieczne zamknięcie
    vision_process.join()
    comms_process.join()
