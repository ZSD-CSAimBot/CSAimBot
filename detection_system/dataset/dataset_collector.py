import os
import time
import cv2
import bettercam
import win32api

#Version for 1080p monitor

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FOV_WIDTH = 1280
FOV_HEIGHT = 736

#Version for 2k monitor
'''
SCREEN_WIDTH = 2560
SCREEN_HEIGHT = 1440
FOV_WIDTH = 1728
FOV_HEIGHT = 992
'''

left = (SCREEN_WIDTH // 2) - (FOV_WIDTH // 2)
top = (SCREEN_HEIGHT // 2) - (FOV_HEIGHT // 2)
right = left + FOV_WIDTH
bottom = top + FOV_HEIGHT
REGION = (left, top, right, bottom)

#https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
LBUTTON = 0x01
Y = 0x59

OUTPUT_DIR = "./detection_system/dataset/images_andrzej"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    camera = bettercam.create(output_color="BGR")

    while True:
        if win32api.GetAsyncKeyState(LBUTTON) < 0:
            frame = camera.grab(region=REGION)
            if frame is not None:
                timestamp = int(time.time() * 1000)
                filename = f"capture_{timestamp}.jpg"
                filepath = os.path.join(OUTPUT_DIR, filename)

                #Only for 2k monitor - for 1080p frame is already 1280x736
                #frame = cv2.resize(frame, (1280, 736))

                cv2.imwrite(filepath, frame)
                print(f"Screenshot: {filename}")
                time.sleep(0.5)

        if win32api.GetAsyncKeyState(Y) < 0:
            break

        time.sleep(0.005)

    camera.release()

if __name__ == "__main__":
    main()