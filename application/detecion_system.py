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
        self.prepare_camera()
        self.prepare_model(model_path)
        self.allocate_variables(target_fps=60)

    def prepare_camera(self):
        """
        Initializes the camera and verifies it is ready.
        """
        SCREEN_WIDTH = 1920
        SCREEN_HEIGHT = 1080
        self.FOV_WIDTH = 1280
        self.FOV_HEIGHT = 736

        LEFT = (SCREEN_WIDTH // 2) - (self.FOV_WIDTH // 2)
        RIGHT = LEFT + self.FOV_WIDTH
        TOP = (SCREEN_HEIGHT // 2) - (self.FOV_HEIGHT // 2)
        BOTTOM = TOP + self.FOV_HEIGHT
        REGION = (LEFT, TOP, RIGHT, BOTTOM)

        self.camera = bettercam.create(output_color="BGRA", region=REGION)
        self.captured_frame = None
    
    def prepare_model(self, model_path):
        """
        Loads the YOLO model and warms it up.
        """
        self.model = YOLO(model_path, task='detect')
        warmup_input = torch.zeros((1, 3, self.FOV_HEIGHT, self.FOV_WIDTH), dtype=torch.float16, device="cuda")
        self.model(warmup_input, verbose=False)

    def allocate_variables(self, target_fps):
        """
        Allocates necessary tensors and variables for processing.
        """
        self.is_running = False
        self.show_debug_window = True
        self.target_frame_time = 1.0 / target_fps
        self.cpu_pinned_tensor = torch.empty((self.FOV_HEIGHT, self.FOV_WIDTH, 4), dtype=torch.uint8, device="cpu", pin_memory=True)
        self.gpu_tensor = torch.empty((self.FOV_HEIGHT, self.FOV_WIDTH, 4), dtype=torch.uint8, device="cuda")
        self.model_tensor = torch.empty((1, 3, self.FOV_HEIGHT, self.FOV_WIDTH), dtype=torch.float16, device="cuda")
  
    def capture_frame(self):
        self.captured_frame = self.camera.grab()
        return self.captured_frame is not None
    
    def preprocess_frame(self, frame):
        """
        Converts BGRA frame to normalized NCHW tensor.
        """
        self.cpu_pinned_tensor.copy_(torch.from_numpy(frame))
        self.gpu_tensor.copy_(self.cpu_pinned_tensor, non_blocking=True)
        
        self.model_tensor[0, 0].copy_(self.gpu_tensor[:, :, 2]) # R
        self.model_tensor[0, 1].copy_(self.gpu_tensor[:, :, 1]) # G
        self.model_tensor[0, 2].copy_(self.gpu_tensor[:, :, 0]) # B
        
        self.model_tensor.div_(255.0)

    def display_results(self, results):
        """
        Draws bounding boxes and handles FPS capping.
        """
        if self.show_debug_window:
            if results[0].boxes is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box)
                    cv2.rectangle(self.captured_frame, (x1, y1), (x2, y2), (0, 255, 0, 255), 2)
            
            cv2.imshow("Aimbot Vision (Debug)", self.captured_frame)
            cv2.waitKey(1)
        else:
            if cv2.getWindowProperty("Aimbot Vision (Debug)", cv2.WND_PROP_VISIBLE) >= 1:
                cv2.destroyWindow("Aimbot Vision (Debug)")

    def run(self):
        """
        Main loop for capturing and processing frames.
        """
        try:
            while self.is_running:
                start_time = time.perf_counter()

                if not self.capture_frame():
                    continue

                self.preprocess_frame(self.captured_frame)

                results = self.model(self.model_tensor, verbose=False)
                torch.cuda.synchronize()

                if self.show_debug_window:
                    self.display_results(results)
                
                elapsed_time = time.perf_counter() - start_time
                if elapsed_time < self.target_frame_time:
                    time.sleep(self.target_frame_time - elapsed_time)

        except Exception as e:
            print(f"Error in loop: {e}")

        finally:
            cv2.destroyAllWindows()

    def cleanup(self):
        """
        Releases hardware resources.
        """
        self.camera.release()
        cv2.destroyAllWindows()
        self.cpu_pinned_tensor = None
        self.gpu_tensor = None
        self.model_tensor = None