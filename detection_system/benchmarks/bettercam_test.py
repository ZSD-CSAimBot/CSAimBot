import bettercam
import time
import torch

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FOV_WIDTH = 1280
FOV_HEIGHT = 720

left = (SCREEN_WIDTH // 2) - (FOV_WIDTH // 2)
top = (SCREEN_HEIGHT // 2) - (FOV_HEIGHT // 2)
right = left + FOV_WIDTH
bottom = top + FOV_HEIGHT
REGION = (left, top, right, bottom)


camera = bettercam.create(region=REGION, output_color="BGRA", nvidia_gpu=True)
frame = torch.as_tensor(camera.grab(), device="cuda")
start = time.perf_counter()
frame = torch.as_tensor(camera.grab(), device="cuda")
end = time.perf_counter()
print(f"Grabbed frame in {(end - start) * 1000:.2f} ms")
camera.release()