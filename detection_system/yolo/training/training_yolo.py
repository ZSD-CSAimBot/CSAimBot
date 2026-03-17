import os
from ultralytics import YOLO


# This script trains a YOLO model using the specified dataset and configuration.
def main():
    project_path = os.path.abspath('./detection_system/yolo/training')
    data_path = os.path.join(project_path, 'Beta_v2_dataset/data.yaml')
    yolo26_path = os.path.join(project_path, 'yolo26n.pt')
    
    model = YOLO(yolo26_path) 
    results = model.train(
        data=data_path,
        epochs=100,
        imgsz=[736, 1280],
        rect=True,
        device=0,
        batch=8,
        workers=8,
        project=project_path,
        name='Beta_v2',
        exist_ok=True,
        cache='disk'
    )

if __name__ == '__main__':
    main()