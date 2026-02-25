from ultralytics import YOLO

def main():
    model = YOLO("./detection_system/yolo/yolov8n.pt")
    model.export(format="engine", half=True, workspace=4, device=0, imgsz=640)

if __name__ == "__main__":
    main()