import os
from ultralytics import YOLO


# This script exports a YOLO model to TensorRT format for optimized inference.
def export_model_to_trt():
    model_path = os.path.abspath('application/detection_system/yolo/training/Beta_v3/weights/best.pt')
    if not os.path.exists(model_path):
        raise FileNotFoundError("Model file not found. Please ensure 'application/detection_system/yolo/training/Beta_v3/weights/best.pt' exists.")
    
    model = YOLO(model_path)
    model.export(
        format="engine",
        imgsz=[736, 1280], 
        half=True,
        dynamic=False, 
        device=0
    )