# Remember to install the required dependencies from requirements.txt before running this script.
# Remember to export model to .engine format using the export.py script.

import os
import time
import bettercam
import cv2
from ultralytics import YOLO
import torch


class AimBot:
    """
    Real-time object detection system using screen capture and YOLO.
    """
    def __init__(self, model_path):
        """
        Initializes the screen capture region, YOLO model, and pre-allocates memory.

        Args:
            model_path (str): Path to the YOLO model weights (e.g., .pt or .engine).
        """
        self.SCREEN_WIDTH = 1920
        self.SCREEN_HEIGHT = 1080
        self.FOV_WIDTH = 1280
        self.FOV_HEIGHT = 736

        # Calculate center screen region for capture
        left = (self.SCREEN_WIDTH // 2) - (self.FOV_WIDTH // 2)
        right = left + self.FOV_WIDTH
        top = (self.SCREEN_HEIGHT // 2) - (self.FOV_HEIGHT // 2)
        bottom = top + self.FOV_HEIGHT

        self.REGION = (left, top, right, bottom)

        self.model = YOLO(model_path, task='detect')
        self.camera = bettercam.create(output_color="BGRA", region=self.REGION)

        self.cv2_frame = None
        self.target_fps = 60
        self.frame_time = 1.0 / self.target_fps

        self.prepare_tensors()


    def cleanup(self):
        """Releases hardware resources and clears memory allocations."""
        self.camera.release()
        print("Camera released!")

        cv2.destroyAllWindows()
        print("All OpenCV windows destroyed!")

        self.cpu_pinned_tensor = None
        self.gpu_tensor = None
        self.model_tensor = None
        print("Tensors cleared!")


    def prepare_tensors(self):
        """
        Pre-allocates pinned memory and GPU tensors to optimize frame transfer times.
        """
        self.cpu_pinned_tensor = torch.empty((self.FOV_HEIGHT, self.FOV_WIDTH, 4), dtype=torch.uint8, device="cpu", pin_memory=True)
        self.gpu_tensor = torch.empty((self.FOV_HEIGHT, self.FOV_WIDTH, 4), dtype=torch.uint8, device="cuda")
        self.model_tensor = torch.empty((1, 3, self.FOV_HEIGHT, self.FOV_WIDTH), dtype=torch.float16, device="cuda")


    def capture_frame(self):
        """Captures a single frame from the defined screen region."""
        frame = self.camera.grab()

        if frame is None:
            return False

        self.cv2_frame = frame.copy()

        return True
    
    def preprocess_frame(self, frame):
        """
        Converts a BGRA frame to a normalized NCHW tensor suitable for YOLO input.

        Args:
            frame (numpy.ndarray): Input frame in BGRA format.
        """
        # Transfer frame to GPU and convert BGRA to RGB format
        self.cpu_pinned_tensor.copy_(torch.from_numpy(frame))
        self.gpu_tensor.copy_(self.cpu_pinned_tensor, non_blocking=True)
        
        self.model_tensor[0, 0].copy_(self.gpu_tensor[:, :, 2]) # R
        self.model_tensor[0, 1].copy_(self.gpu_tensor[:, :, 1]) # G
        self.model_tensor[0, 2].copy_(self.gpu_tensor[:, :, 0]) # B
        
        # Normalize pixel values to [0, 1]
        self.model_tensor.div_(255.0)


    def display_results(self, results):
        """
        Draws bounding boxes on the captured frame for debugging purposes.

        Args:
            results (list): Output results from the YOLO model.
        """
        if self.cv2_frame is None or results[0].boxes is None:
            return
        
        boxes = results[0].boxes.xyxy.cpu().numpy()
        
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(self.cv2_frame, (x1, y1), (x2, y2), (0, 255, 0, 255), 2)
            
        cv2.imshow("Aimbot Vision (Debug)", self.cv2_frame)
        cv2.waitKey(1)


    def run(self):
        """Main execution loop for capturing, processing, and displaying frames."""
        try:
            while True:
                start_time = time.perf_counter()

                if not self.capture_frame():
                    continue

                self.preprocess_frame(self.cv2_frame)

                results = self.model(self.model_tensor, verbose=False)
                torch.cuda.synchronize()

                self.display_results(results)

                # Cap the framerate to prevent unnecessary CPU/GPU usage
                elapsed_time = time.perf_counter() - start_time
                sleep_time = self.frame_time - elapsed_time
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("Exiting due to keyboard interrupt...")
        finally:
            self.cleanup()
            print("Exited from the loop!")


if __name__ == "__main__":
    MODEL_PATH = os.path.abspath('./detection_system/yolo/training/Beta_v2/weights/best.engine')
    aimbot = AimBot(model_path=MODEL_PATH)
    aimbot.run()