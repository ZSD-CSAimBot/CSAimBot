import os
import time
import bettercam
import cv2
import win32api

# Define the region of interest (ROI) for capturing the screen
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FOV_WIDTH = 1280
FOV_HEIGHT = 736

left = (SCREEN_WIDTH // 2) - (FOV_WIDTH // 2)
top = (SCREEN_HEIGHT // 2) - (FOV_HEIGHT // 2)
right = left + FOV_WIDTH
bottom = top + FOV_HEIGHT
REGION = (left, top, right, bottom)

OUTPUT_DIR = "./detection_system/dataset/images"

# Virtual-Key Codes: https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes 
LBUTTON = 0x01
Y = 0x59


# Main function to capture screenshots when the left mouse button is pressed
def main():
    camera = bettercam.create(output_color="BGR")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    while True:
        if win32api.GetAsyncKeyState(LBUTTON) < 0:
            frame = camera.grab(region=REGION)
            if frame is not None:
                timestamp = int(time.time() * 1000)
                filename = f"capture_{timestamp}.jpg"
                filepath = os.path.join(OUTPUT_DIR, filename)
                cv2.imwrite(filepath, frame)
                print(f"Screenshot: {filename}")
                time.sleep(0.5)

        if win32api.GetAsyncKeyState(Y) < 0: break
        time.sleep(0.005)

    camera.release()


if __name__ == "__main__":
    main()
