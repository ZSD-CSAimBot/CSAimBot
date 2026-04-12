import os
import multiprocessing as mp
from detection_system.yolo.export import export_model_to_trt
from detection_system.aimbot import vision_worker
from gui_design.gui import GUI


if __name__ == "__main__":
    mp.freeze_support()

    MODEL_PATH = os.path.abspath('application/detection_system/yolo/training/Beta_v3/weights/best.engine')
    if not os.path.exists(MODEL_PATH):
        export_model_to_trt()

    gui_conn, vision_conn = mp.Pipe()

    vision_process = mp.Process(
        target=vision_worker, 
        args=(vision_conn, MODEL_PATH, 60),
        daemon=True
    )
    vision_process.start()

    app = GUI(gui_conn)
    app.run()
    vision_process.join()