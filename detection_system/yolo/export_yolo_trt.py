from ultralytics import YOLO

def main():
    model = YOLO("./detection_system/yolo/yolo26n.pt")
    model.export(
        format="engine",
        imgsz=[736, 1280], 
        half=True, 
        dynamic=False, 
        device=0
    )

if __name__ == "__main__":
    main()