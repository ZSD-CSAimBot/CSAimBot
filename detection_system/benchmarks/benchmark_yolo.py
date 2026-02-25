import bettercam
import time
from ultralytics import YOLO
import torch

SCREEN_WIDTH = 2560
SCREEN_HEIGHT = 1440
FOV_SIZE = 640

left = (SCREEN_WIDTH // 2) - (FOV_SIZE // 2)
top = (SCREEN_HEIGHT // 2) - (FOV_SIZE // 2)
right = left + FOV_SIZE
bottom = top + FOV_SIZE
REGION = (left, top, right, bottom)

def main():

    model = YOLO("./detection_system/yolo/yolov8n.pt")
    model.to('cuda')
    
    camera = bettercam.create(output_color="BGRA", nvidia_gpu=True)

    for _ in range(5):
        frame = camera.grab(region=REGION)
        while frame is None:
            frame = camera.grab(region=REGION)
        frame_tensor = torch.as_tensor(frame, device="cuda")
        frame_tensor = frame_tensor[:, :, [2, 1, 0]].permute(2, 0, 1).unsqueeze(0).half().div(255.0)
        _ = model(frame_tensor, verbose=False)
        
    torch.cuda.synchronize()

    times = []
    
    for _ in range(500):
        start = time.perf_counter()
        frame = camera.grab(region=REGION)
        while frame is None:
            frame = camera.grab(region=REGION)
        frame_tensor = torch.as_tensor(frame, device="cuda")
        frame_tensor = frame_tensor[:, :, [2, 1, 0]].permute(2, 0, 1).unsqueeze(0).half().div(255.0)
        _ = model(frame_tensor, verbose=False)
        torch.cuda.synchronize()
        end = time.perf_counter()
        times.append((end - start) * 1000)

    mean = sum(times) / len(times)
    print(f"Average time: {mean} ms")
    print(f"Fastest loop: {min(times)} ms")
    print(f"Slowest loop: {max(times)} ms")

    camera.release()

if __name__ == "__main__":
    main()