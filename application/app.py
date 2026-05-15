"""Application entrypoint for CSAimBot."""

import multiprocessing as mp
import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from comms.comms import comms_worker
from gui_design.gui import GUI

# Ensure local application packages are importable when launched directly.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulation.sim_worker import simulation_worker


def run_vision_worker(pipe_conn, model_path, target_fps):
    if getattr(sys, "frozen", False):
        import ultralytics.utils.checks as ultralytics_checks

        ultralytics_checks.check_requirements = lambda *args, **kwargs: None

    from detection_system.aimbot import vision_worker

    vision_worker(pipe_conn, model_path, target_fps)


def run_export_worker(pt_path):
    if getattr(sys, "frozen", False):
        import ultralytics.utils.checks as ultralytics_checks

        ultralytics_checks.check_requirements = lambda *args, **kwargs: None

    from detection_system.yolo.export import export_model_to_trt

    export_model_to_trt(pt_path)


if __name__ == "__main__":
    mp.freeze_support()

    if getattr(sys, "frozen", False):
        import ultralytics.utils.checks as ultralytics_checks

        ultralytics_checks.check_requirements = lambda *args, **kwargs: None

    if "--export-only" in sys.argv:
        if getattr(sys, "frozen", False):
            base_dir = os.path.join(getattr(sys, "_MEIPASS"), "application")
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        PT_MODEL_PATH = os.path.join(
            base_dir,
            "detection_system",
            "yolo",
            "trained_model.pt",
        )
        if os.path.exists(PT_MODEL_PATH):
            print("Exporting model to TensorRT...")
            export_proc = mp.Process(target=run_export_worker, args=(PT_MODEL_PATH,))
            export_proc.start()
            export_proc.join()
        else:
            print(f"ERROR: Model not found at {PT_MODEL_PATH}")
        sys.exit(0)

    # Prepare the trained TensorRT model used by the vision worker.
    if getattr(sys, "frozen", False):
        APP_DIR = os.path.join(getattr(sys, "_MEIPASS"), "application")
    else:
        APP_DIR = os.path.dirname(os.path.abspath(__file__))

    MODEL_PATH = os.path.join(
        APP_DIR, "detection_system", "yolo", "trained_model.engine"
    )

    gui_vision_conn, vision_worker_conn = mp.Pipe()
    gui_comms_conn, comms_worker_conn = mp.Pipe()
    gui_sim_conn, sim_worker_conn = mp.Pipe()

    vision_process = mp.Process(
        target=run_vision_worker, args=(vision_worker_conn, MODEL_PATH, 60), daemon=True
    )
    vision_process.start()

    comms_process = mp.Process(
        target=comms_worker, args=(comms_worker_conn,), daemon=True
    )
    comms_process.start()

    sim_process = mp.Process(
        target=simulation_worker, args=(sim_worker_conn,), daemon=True
    )
    sim_process.start()

    try:
        app = GUI(gui_vision_conn, gui_comms_conn, gui_sim_conn)
        app.run()
    except Exception as e:
        import traceback

        traceback.print_exc()
    finally:
        try:
            gui_vision_conn.send({"cmd": "QUIT"})
            gui_comms_conn.send({"cmd": "QUIT"})
            gui_sim_conn.send({"cmd": "QUIT"})
        except Exception:
            pass
        vision_process.join(timeout=2)
        comms_process.join(timeout=2)
        sim_process.join(timeout=2)

        if vision_process.is_alive():
            vision_process.terminate()
        if comms_process.is_alive():
            comms_process.terminate()
        if sim_process.is_alive():
            sim_process.terminate()
