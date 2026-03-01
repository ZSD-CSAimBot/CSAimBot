import bettercam
import time
from ultralytics import YOLO
import torch

SCREEN_WIDTH = 2560
SCREEN_HEIGHT = 1440
FOV_WIDTH = 1280
FOV_HEIGHT = 736

left = (SCREEN_WIDTH // 2) - (FOV_WIDTH // 2)
top = (SCREEN_HEIGHT // 2) - (FOV_HEIGHT // 2)
right = left + FOV_WIDTH
bottom = top + FOV_HEIGHT
REGION = (left, top, right, bottom)


def main():
    model = YOLO("./detection_system/yolo/yolo26n.engine", task='detect')
    camera = bettercam.create(output_color="BGRA", region=REGION, nvidia_gpu=True)
    model_tensor = torch.empty((1, 3, FOV_HEIGHT, FOV_WIDTH), dtype=torch.float16, device="cuda")
    times = []
    sum_times = [0,0,0,0]

    for _ in range(5):
        frame = camera.grab()
        if frame is not None:
            gpu_tensor = torch.from_dlpack(frame)
            model_tensor[0, 0].copy_(gpu_tensor[:, :, 2])
            model_tensor[0, 1].copy_(gpu_tensor[:, :, 1])
            model_tensor[0, 2].copy_(gpu_tensor[:, :, 0])
            model_tensor.div_(255.0)
            _ = model(model_tensor, verbose=False)
            torch.cuda.synchronize()
        
    for _ in range(500):
        start = time.perf_counter()
        frame = camera.grab()
        grab = time.perf_counter()
        if frame is not None:
            gpu_tensor = torch.from_dlpack(frame)
            model_tensor[0, 0].copy_(gpu_tensor[:, :, 2])
            model_tensor[0, 1].copy_(gpu_tensor[:, :, 1])
            model_tensor[0, 2].copy_(gpu_tensor[:, :, 0])
            model_tensor.div_(255.0)
            tensor = time.perf_counter()
            _ = model(model_tensor, verbose=False)
            torch.cuda.synchronize()
            end = time.perf_counter()
            times.append((end - start, grab - start, tensor - grab, end - tensor))

    camera.release()
    
    for t in times:
        sum_times[0] += t[0]
        sum_times[1] += t[1]
        sum_times[2] += t[2]
        sum_times[3] += t[3]
    length = len(times)

    print(f"Average time: {sum_times[0] / length * 1000:.2f} ms")
    print(f"Fastest loop: {min(times)[0]*1000:.2f} ms")
    print(f"Slowest loop: {max(times)[0]*1000:.2f} ms")
    print(f"Average grab time: {sum_times[1] / length * 1000:.2f} ms")
    print(f"Average tensor conversion time: {sum_times[2] / length * 1000:.2f} ms")
    print(f"Average inference time: {sum_times[3] / length * 1000:.2f} ms")


if __name__ == "__main__":
    main()