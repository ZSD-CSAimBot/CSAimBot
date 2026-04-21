import os
from ultralytics import YOLO

# This script trains a YOLO model using the specified dataset and configuration.
def main():
    project_path = os.path.abspath('application/detection_system/yolo/training')
    data_path = os.path.join(project_path, 'Beta_v4/Beta_v4_dataset/data.yaml')
    yolo26_path = os.path.join(project_path, 'yolo26n.pt')
    
    model = YOLO(yolo26_path) 
    results = model.train(
        data=data_path,
        epochs=300,
        patience=30,
        imgsz=1280,
        rect=True,
        device=0,
        batch=32,
        workers=8,
        half=True,
        project=project_path,
        name='Beta_v4',
        exist_ok=True,
        cache='disk'
    )

if __name__ == '__main__':
    main()