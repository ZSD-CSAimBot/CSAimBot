import os
import multiprocessing as mp
from detection_system import vision_worker
from gui import GUI


if __name__ == "__main__":
    mp.freeze_support()
    
    MODEL_PATH = os.path.abspath('./detection_system/yolo/training/Beta_v3/weights/best.engine')

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