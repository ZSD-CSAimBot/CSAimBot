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
    # Get the application directory (where this file is located)
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    MODEL_PATH = os.path.join(APP_DIR, 'detection_system', 'yolo', 'trained_model.engine')
    
    if not os.path.exists(MODEL_PATH):
        # Try to export from PT model if engine doesn't exist
        PT_MODEL_PATH = os.path.join(APP_DIR, 'detection_system', 'yolo', 'trained_model.pt')
        if os.path.exists(PT_MODEL_PATH):
            export_model_to_trt()
        else:
            print(f"ERROR: Model not found at {PT_MODEL_PATH}")

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

    # Send shutdown signals to worker processes
    gui_vision_conn.send({"cmd": "QUIT"})
    gui_comms_conn.send({"cmd": "QUIT"})
    gui_sim_conn.send({"cmd": "QUIT"})

    # Wait for worker shutdown after the GUI exits.
    vision_process.join(timeout=2)
    comms_process.join(timeout=2)
    sim_process.join(timeout=2)

    # Terminate any processes that didn't exit gracefully
    if vision_process.is_alive():
        vision_process.terminate()
    if comms_process.is_alive():
        comms_process.terminate()
    if sim_process.is_alive():
        sim_process.terminate()
