from ultralytics import YOLO


# This script exports a YOLO model to TensorRT format for optimized inference.
def main():
    model = YOLO("./detection_system/yolo/training/Beta_v2/weights/best.pt")
    model.export(
        format="engine",
        imgsz=[736, 1280], 
        half=True, 
        dynamic=False, 
        device=0
    )

if __name__ == "__main__":
    main()