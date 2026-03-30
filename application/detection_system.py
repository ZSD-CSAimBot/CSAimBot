import time
import cv2
import torch
from ultralytics import YOLO
from camera import CameraProvider

class AimBot:
    """
    Real-time object detection system optimized for Zero-Copy on GPU.
    """
    def __init__(self, model_path):
        self.prepare_camera()
        self.prepare_model(model_path)
        self.allocate_variables()

    def prepare_camera(self):
        SCREEN_WIDTH = 1920
        SCREEN_HEIGHT = 1080
        self.FOV_WIDTH = 1280
        self.FOV_HEIGHT = 736

        LEFT = (SCREEN_WIDTH // 2) - (self.FOV_WIDTH // 2)
        RIGHT = LEFT + self.FOV_WIDTH
        TOP = (SCREEN_HEIGHT // 2) - (self.FOV_HEIGHT // 2)
        BOTTOM = TOP + self.FOV_HEIGHT
        self.REGION = (LEFT, TOP, RIGHT, BOTTOM)

        self.camera = CameraProvider(self.REGION)
        self.debug_frame = None
    
    def prepare_model(self, model_path):
        self.model = YOLO(model_path, task='detect')
        warmup_input = torch.zeros((1, 3, self.FOV_HEIGHT, self.FOV_WIDTH), dtype=torch.float16, device="cuda")
        self.model(warmup_input, verbose=False)

    def allocate_variables(self):
        self.show_debug_window = True
        self.model_tensor = torch.empty((1, 3, self.FOV_HEIGHT, self.FOV_WIDTH), dtype=torch.float16, device="cuda")

    def capture_and_preprocess_frame(self):
        dl_tensor = self.camera.grab_gpu_tensor()
        if dl_tensor is not None:
            if self.show_debug_window:
                self.debug_frame = dl_tensor.cpu().numpy() 
            self.model_tensor[0, 0].copy_(dl_tensor[:, :, 2]) # R
            self.model_tensor[0, 1].copy_(dl_tensor[:, :, 1]) # G
            self.model_tensor[0, 2].copy_(dl_tensor[:, :, 0]) # B
            self.model_tensor.div_(255.0)
            return True
        return False

    def display_results(self, results):
        if self.show_debug_window and self.debug_frame is not None:
            if results[0].boxes is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box)
                    cv2.rectangle(self.debug_frame, (x1, y1), (x2, y2), (0, 255, 0, 255), 2)
            
            cv2.imshow("Aimbot Vision (Debug)", self.debug_frame)
            cv2.waitKey(1)
        else:
            if cv2.getWindowProperty("Aimbot Vision (Debug)", cv2.WND_PROP_VISIBLE) >= 1:
                cv2.destroyWindow("Aimbot Vision (Debug)")

    def process_single_frame(self):
        """ Processing single frame: capture, preprocess, inference, display (if debug) """
        if not self.capture_and_preprocess_frame():
            return

        results = self.model(self.model_tensor, verbose=False)
        torch.cuda.synchronize()

        if self.show_debug_window:
            self.display_results(results)

    def cleanup(self):
        self.camera.release()
        cv2.destroyAllWindows()


def vision_worker(pipe_conn, model_path, target_fps):
    """
    Worker function for the vision process. Listens for commands and processes frames accordingly.
    """
    aimbot = AimBot(model_path)
    is_running = False
    target_frame_time = 1.0 / target_fps

    try:
        while True:
            if pipe_conn.poll():
                msg = pipe_conn.recv()
                if msg["cmd"] == "START":
                    is_running = True
                elif msg["cmd"] == "STOP":
                    is_running = False
                    cv2.destroyAllWindows()
                elif msg["cmd"] == "DEBUG":
                    aimbot.show_debug_window = msg["value"]
                    if not msg["value"]:
                        cv2.destroyAllWindows()
                elif msg["cmd"] == "QUIT":
                    break

            if is_running:
                start_time = time.perf_counter()
                aimbot.process_single_frame()
                elapsed_time = time.perf_counter() - start_time
                print(elapsed_time)
                if elapsed_time < target_frame_time:
                    time.sleep(target_frame_time - elapsed_time)
            else:
                time.sleep(0.05)
                
    except KeyboardInterrupt:
        pass
    finally:
        aimbot.cleanup()