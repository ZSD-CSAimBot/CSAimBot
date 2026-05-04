"""Application entrypoint for CSAimBot."""

import multiprocessing as mp
import os
import sys

from comms.comms import comms_worker
from detection_system.aimbot import vision_worker
from detection_system.yolo.export import export_model_to_trt
from gui_design.gui import GUI

# Ensure local application packages are importable when launched directly.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulation.app.gui import simulation_worker

if __name__ == "__main__":
    mp.freeze_support()

    # Prepare the trained TensorRT model used by the vision worker.
    MODEL_PATH = os.path.abspath('application/detection_system/yolo/trained_model.engine')
    if not os.path.exists(MODEL_PATH):
        export_model_to_trt()

    # Create the inter-process communication channels.
    gui_vision_conn, vision_worker_conn = mp.Pipe()
    gui_comms_conn, comms_worker_conn = mp.Pipe()
    gui_sim_conn, sim_worker_conn = mp.Pipe()
    
    # Start the worker processes before opening the GUI.
    vision_process = mp.Process(
        target=vision_worker,
        args=(vision_worker_conn, MODEL_PATH, 60),
        daemon=True
    )
    vision_process.start()

    comms_process = mp.Process(
        target=comms_worker,
        args=(comms_worker_conn,),
        daemon=True
    )
    comms_process.start()

    sim_process = mp.Process(
        target=simulation_worker,
        args=(sim_worker_conn,),
        daemon=True
    )
    sim_process.start()

    # Launch the main GUI loop.
    app = GUI(gui_vision_conn, gui_comms_conn, gui_sim_conn)
    app.run()

    # Wait for worker shutdown after the GUI exits.
    vision_process.join()
    comms_process.join()
    sim_process.join()
