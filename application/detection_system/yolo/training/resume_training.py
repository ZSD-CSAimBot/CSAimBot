import os
from ultralytics import YOLO

def main():
    project_path = os.path.abspath('./detection_system/yolo/training')
    last_weights_path = os.path.join(project_path, './Beta_v3/weights/last.pt')
    model = YOLO(last_weights_path) 
    results = model.train(resume=True)

if __name__ == '__main__':
    main()