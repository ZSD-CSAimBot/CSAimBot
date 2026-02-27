import bettercam
import time
from ultralytics import YOLO
import torch
import cupy as cp

SCREEN_WIDTH = 2560
SCREEN_HEIGHT = 1440
FOV_SIZE = 640

left = (SCREEN_WIDTH // 2) - (FOV_SIZE // 2)
top = (SCREEN_HEIGHT // 2) - (FOV_SIZE // 2)
right = left + FOV_SIZE
bottom = top + FOV_SIZE
REGION = (left, top, right, bottom)

def main():

    model = YOLO("./detection_system/yolo/yolov8n.engine", task='detect')
    camera = bettercam.create(output_color="BGRA", region=REGION, nvidia_gpu=True)

    for _ in range(5):
        frame = camera.grab()
        while frame is None:    
            frame = camera.grab()
        frame_tensor = torch.from_dlpack(frame)
        frame_tensor = frame_tensor[:,:,[2,1,0]].permute(2, 0, 1).unsqueeze(0).half().div_(255.0)
        _ = model(frame_tensor, verbose=False)
        
    torch.cuda.synchronize()

    times = []
    
    for _ in range(500):
        start = time.perf_counter()
        frame = camera.grab()
        while frame is None:    
            frame = camera.grab()
        frame_tensor = torch.from_dlpack(frame)
        grab = time.perf_counter()
        print (f"Grab time: {(grab - start) * 1000:.2f} ms")
        frame_tensor = frame_tensor[:,:,[2,1,0]].permute(2, 0, 1).unsqueeze(0).half().div_(255.0)
        tensor_time = time.perf_counter()
        print (f"Tensor conversion time: {(tensor_time - grab) * 1000:.2f} ms")
        _ = model(frame_tensor, verbose=False)
        torch.cuda.synchronize()
        end = time.perf_counter()
        print (f"Inference time: {(end - tensor_time) * 1000:.2f} ms")
        times.append((end - start) * 1000)

    mean = sum(times) / len(times)
    print(f"Average time: {mean:.2f} ms")
    print(f"Fastest loop: {min(times):.2f} ms")
    print(f"Slowest loop: {max(times):.2f} ms")

    camera.release()

if __name__ == "__main__":
    main()