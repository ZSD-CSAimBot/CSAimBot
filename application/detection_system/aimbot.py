import time
import cv2
import torch
import numpy as np
from ultralytics import YOLO
from detection_system.camera import CameraProvider

class AimBot:
    """
    Real-time object detection system optimized for Zero-Copy on GPU.
    """
    def __init__(self, model_path):
        self.prepare_camera()
        self.prepare_model(model_path)
        self.allocate_variables()

    def prepare_camera(self):
        SCREEN_WIDTH = 2560
        SCREEN_HEIGHT = 1440
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
        self.best_target_position = (0.0, 0.0)
        self.head_class_id = [1, 7]
        self.body_class_id = [0, 6]

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

    def calculate_best_target_position(self, boxes_data_tensor):
        """
        Calculates the best target position on the GPU.
        """
        if boxes_data_tensor is None or boxes_data_tensor.shape[0] == 0:
            return None, None
        cls = boxes_data_tensor[:, 5]
        valid_classes = torch.tensor(self.head_class_id + self.body_class_id, device=boxes_data_tensor.device)
        mask = torch.isin(cls, valid_classes)
        valid_boxes = boxes_data_tensor[mask]

        if valid_boxes.shape[0] == 0:
            return None, None

        centers_x = (valid_boxes[:, 0] + valid_boxes[:, 2]) / 2.0
        centers_y = (valid_boxes[:, 1] + valid_boxes[:, 3]) / 2.0
        offsets_x = centers_x - (self.FOV_WIDTH / 2.0)
        offsets_y = centers_y - (self.FOV_HEIGHT / 2.0)
        distances_sq = (offsets_x ** 2) + (offsets_y ** 2)
        best_idx = torch.argmin(distances_sq)

        offset_x = int(round(offsets_x[best_idx].item()))
        offset_y = int(round(offsets_y[best_idx].item()))
        return offset_x, offset_y

    def display_results(self, boxes_data):
        if self.debug_frame is not None:
            if boxes_data is not None and len(boxes_data) > 0:
                xyxy = boxes_data[:, :4]
                cls = boxes_data[:, 5]
                valid_classes = self.head_class_id + self.body_class_id
                valid_targets_mask = np.isin(cls, valid_classes)
                valid_boxes = xyxy[valid_targets_mask]
                valid_cls = cls[valid_targets_mask]
                
                for i, box in enumerate(valid_boxes):
                    x1, y1, x2, y2 = map(int, box)
                    class_id = valid_cls[i]
                    if class_id in self.head_class_id:
                        color = (255, 0, 255, 255)
                    else:
                        color = (0, 255, 0, 255)
                    cv2.rectangle(self.debug_frame, (x1, y1), (x2, y2), color, 2)

            offset_x, offset_y = self.best_target_position
            if offset_x is not None and offset_y is not None:
                center_x = int(self.FOV_WIDTH / 2.0)
                center_y = int(self.FOV_HEIGHT / 2.0)
                target_x = int(center_x + offset_x)
                target_y = int(center_y + offset_y)
                cv2.line(self.debug_frame, (center_x, center_y), (target_x, target_y), (0, 0, 255, 255), 2)
                info_text = f"X: {float(offset_x):.1f}px | Y: {float(offset_y):.1f}px"
                cv2.putText(self.debug_frame, info_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255, 255), 2)
            
            cv2.imshow("Aimbot Vision (Debug)", self.debug_frame)
            cv2.waitKey(1)
        else:
            if cv2.getWindowProperty("Aimbot Vision (Debug)", cv2.WND_PROP_VISIBLE) >= 1:
                cv2.destroyWindow("Aimbot Vision (Debug)")
    
    def process_single_frame(self):
        if not self.capture_and_preprocess_frame():
            return

        results = self.model(self.model_tensor, verbose=False)
        torch.cuda.synchronize()

        if results[0].boxes is not None and len(results[0].boxes) > 0:
            result_tensor = results[0].boxes.data
            self.best_target_position = self.calculate_best_target_position(result_tensor)

            if self.show_debug_window:
                cpu_numpy_data = result_tensor.cpu().numpy()
                self.display_results(cpu_numpy_data)
        else:
            self.best_target_position = (None, None)
            if self.show_debug_window:
                self.display_results(None)
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
                elif msg["cmd"] == "SET_TARGET":
                    if msg["value"] == "TT":
                        aimbot.head_class_id = [7]
                        aimbot.body_class_id = [6]
                    elif msg["value"] == "CT":
                        aimbot.head_class_id = [1]
                        aimbot.body_class_id = [0]
                    elif msg["value"] == "ALL":
                        aimbot.head_class_id = [1, 7]
                        aimbot.body_class_id = [0, 6]
                elif msg["cmd"] == "QUIT":
                    break

            if is_running:
                start_time = time.perf_counter()
                aimbot.process_single_frame()
                elapsed_time = time.perf_counter() - start_time
                if elapsed_time < target_frame_time:
                    time.sleep(target_frame_time - elapsed_time)
            else:
                time.sleep(0.05)
                
    except KeyboardInterrupt:
        pass
    finally:
        aimbot.cleanup()