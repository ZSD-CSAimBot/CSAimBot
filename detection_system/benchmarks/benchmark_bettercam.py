import bettercam
import time

SCREEN_WIDTH = 2560
SCREEN_HEIGHT = 1440
FOV_SIZE = 640 

left = (SCREEN_WIDTH // 2) - (FOV_SIZE // 2)
top = (SCREEN_HEIGHT // 2) - (FOV_SIZE // 2)
right = left + FOV_SIZE
bottom = top + FOV_SIZE
REGION = (left, top, right, bottom)

def main():
    
    camera = bettercam.create(output_color="BGRA", nvidia_gpu=True)

    for _ in range(5):
        camera.grab(region=REGION)
        
    times = []

    for _ in range(500):
        start = time.perf_counter()
        _ = camera.grab(region=REGION)  
        end = time.perf_counter()
        times.append((end - start) * 1000) 

    mean = sum(times) / len(times)
    print(f"Average time: {mean:.2f} ms")
    print(f"Fastest shot: {min(times):.2f} ms")
    print(f"Slowest shot: {max(times):.2f} ms")

    camera.release()

if __name__ == "__main__":
    main()