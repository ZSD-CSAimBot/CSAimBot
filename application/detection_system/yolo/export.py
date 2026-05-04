import os
from ultralytics import YOLO


def export_model_to_trt():
    """
    This function loads the trained YOLO model from the specified path and exports it as a TensorRT engine.
     - The exported engine will be saved in the same directory as the trained model with the name 'best.engine'.
     - The export process includes optimizations such as half-precision (FP16) and static input size for improved performance on NVIDIA GPUs.
    """
    print("Exporting YOLO model to TensorRT format...")
    model_path = os.path.abspath('application/detection_system/yolo/trained_model.pt')
    if not os.path.exists(model_path):
        raise FileNotFoundError("Model file not found. Please ensure 'application/detection_system/yolo/trained_model.pt' exists.")
    
    model = YOLO(model_path)
    model.export(
        format="engine",
        imgsz=[736, 1280], 
        half=True,
        dynamic=False, 
        device=0
    )
    print("Model exported successfully to TensorRT format.")