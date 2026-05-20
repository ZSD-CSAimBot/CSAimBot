"""GPU-based vision pipeline used by the detection worker process."""

import time
import cv2
import torch
import numpy as np
from ultralytics import YOLO
from screeninfo import get_monitors

from detection_system.camera import CameraProvider


class AimBot:
    """
    Real-time object detection system optimized for GPU execution.
    """

    def __init__(self, model_path):
        """
        Initialize the vision pipeline.

        Args:
            model_path: Path to the YOLO model weights.
        """
        self.prepare_camera()
        self.prepare_model(model_path)
        self.allocate_variables()

    def prepare_camera(self):
        """Configure the capture region and camera provider."""
        monitor = next(m for m in get_monitors() if m.is_primary)

        SCREEN_WIDTH = monitor.width
        SCREEN_HEIGHT = monitor.height
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
        """
        Load the YOLO model and run a CUDA warm-up pass.

        Args:
            model_path: Path to the YOLO model weights.
        """
        self.model = YOLO(model_path, task="detect")
        warmup_input = torch.zeros(
            (1, 3, self.FOV_HEIGHT, self.FOV_WIDTH), dtype=torch.float16, device="cuda"
        )
        self.model(warmup_input, verbose=False)

    def allocate_variables(self):
        """Initialize runtime state used during inference and display."""
        self.show_debug_window = True
        self.model_tensor = torch.empty(
            (1, 3, self.FOV_HEIGHT, self.FOV_WIDTH), dtype=torch.float16, device="cuda"
        )
        self.best_target_position = (0, 0)
        self.shoot_threshold = 2
        self.recoil_strength = 0
        self.recoil_control = False
        self.is_holding_sniper = False
        self.head_class_id = [1, 7]
        self.body_class_id = [0, 6]

    def capture_and_preprocess_frame(self):
        """Grab a frame from the camera and copy it into the model tensor."""
        dl_tensor = self.camera.grab_gpu_tensor()
        if dl_tensor is not None:
            if self.show_debug_window:
                self.debug_frame = dl_tensor.cpu().numpy()
            self.model_tensor[0, 0].copy_(dl_tensor[:, :, 2])  # R
            self.model_tensor[0, 1].copy_(dl_tensor[:, :, 1])  # G
            self.model_tensor[0, 2].copy_(dl_tensor[:, :, 0])  # B
            self.model_tensor.div_(255.0)
            return True
        return False

    def recoil_compensation(self, offset_x, offset_y):
        """
        Apply a small vertical correction while recoil control is enabled.

        Args:
            offset_x: Horizontal offset from screen center.
            offset_y: Vertical offset from screen center.

        Returns:
            A tuple containing the adjusted x and y offsets.
        """
        if self.recoil_control:
            if (
                abs(offset_x) < self.shoot_threshold
                and abs(offset_y) < self.shoot_threshold
            ):
                offset_y += self.recoil_strength
        return offset_x, offset_y

    def update_params_state(self, boxes_data_tensor):
        """
        Check if the current detections include the rifle class to determine if recoil control should be active.

        Args:
            boxes_data_tensor: Tensor of detections in xyxy format with class ids.
        """
        if boxes_data_tensor is None or boxes_data_tensor.shape[0] == 0:
            return False, False     

        cls = boxes_data_tensor[:, 5]
        rifle_class_id = 3
        sniper_class_id = 5
        return (cls == rifle_class_id).any().item(), (cls == sniper_class_id).any().item()

    def calculate_best_target_position(self, boxes_data_tensor):
        """
        Select target with priority:
        1. Head classes first
        2. Body classes only if no head is detected
        3. Within selected group, choose the closest to screen center
        """
        if boxes_data_tensor is None or boxes_data_tensor.shape[0] == 0:
            return None, None

        cls = boxes_data_tensor[:, 5]

        head_classes = torch.tensor(
            self.head_class_id,
            device=boxes_data_tensor.device
        )

        body_classes = torch.tensor(
            self.body_class_id,
            device=boxes_data_tensor.device
        )

        head_mask = torch.isin(cls, head_classes)
        body_mask = torch.isin(cls, body_classes)

        head_boxes = boxes_data_tensor[head_mask]
        body_boxes = boxes_data_tensor[body_mask]

        # Priority: head first, body only if no head exists
        if head_boxes.shape[0] > 0:
            selected_boxes = head_boxes
            target_type = "HEAD"
        elif body_boxes.shape[0] > 0:
            selected_boxes = body_boxes
            target_type = "BODY"
        else:
            return None, None

        centers_x = (selected_boxes[:, 0] + selected_boxes[:, 2]) / 2.0
        centers_y = (selected_boxes[:, 1] + selected_boxes[:, 3]) / 2.0

        offsets_x = centers_x - (self.FOV_WIDTH / 2.0)
        offsets_y = centers_y - (self.FOV_HEIGHT / 2.0)

        distances_sq = (offsets_x ** 2) + (offsets_y ** 2)
        best_idx = torch.argmin(distances_sq)

        offset_x = int(round(offsets_x[best_idx].item()))
        offset_y = int(round(offsets_y[best_idx].item()))

        print(
            f"<TARGET_SELECT> type={target_type} x={offset_x} y={offset_y}",
            flush=True
        )

        return self.recoil_compensation(offset_x, offset_y)

    def display_results(self, boxes_data):
        """Render debug overlays for the current frame when enabled."""
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
            if offset_x != "-" and offset_y != "-":
                center_x = int(self.FOV_WIDTH / 2.0)
                center_y = int(self.FOV_HEIGHT / 2.0)

                target_x = int(center_x + offset_x)
                target_y = int(center_y + offset_y)
                cv2.line(
                    self.debug_frame,
                    (center_x, center_y),
                    (target_x, target_y),
                    (0, 0, 255, 255),
                    2,
                )
                info_text = f"X: {float(offset_x):.1f}px | Y: {float(offset_y):.1f}px"
                cv2.putText(
                    self.debug_frame,
                    info_text,
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 255, 255),
                    2,
                )

            cv2.imshow("Aimbot Vision (Debug)", self.debug_frame)
            cv2.waitKey(1)
        else:
            if (
                cv2.getWindowProperty("Aimbot Vision (Debug)", cv2.WND_PROP_VISIBLE)
                >= 1
            ):
                cv2.destroyWindow("Aimbot Vision (Debug)")

    def process_single_frame(self):
        """Run one full capture, inference, and display cycle."""
        if not self.capture_and_preprocess_frame():
            return

        results = self.model(self.model_tensor,conf=0.35, verbose=False)
        torch.cuda.synchronize()

        if results[0].boxes is not None and len(results[0].boxes) > 0:
            result_tensor = results[0].boxes.data
            num_detections = len(results[0].boxes)

            self.recoil_control, self.is_holding_sniper = self.update_params_state(result_tensor)
            result = self.calculate_best_target_position(result_tensor)
            self.best_target_position = result if result[0] is not None else ("-", "-")

            if self.show_debug_window:
                cpu_numpy_data = result_tensor.cpu().numpy()
                self.display_results(cpu_numpy_data)
        else:
            self.recoil_control = False
            self.best_target_position = ("-", "-")
            if self.show_debug_window:
                self.display_results(None)

    def cleanup(self):
        """Release camera resources and close OpenCV windows."""
        self.camera.release()
        cv2.destroyAllWindows()


def vision_worker(pipe_conn, model_path, target_fps):
    """
    Vision worker process entry point.

    Receives control commands from the parent process, runs inference when active,
    and publishes the latest target offsets back through the pipe.

    Args:
        pipe_conn: Multiprocessing pipe connection used for IPC.
        model_path: Path to the YOLO model weights.
        target_fps: Target processing rate for the vision loop.
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
                try:
                    offset_x = aimbot.best_target_position[0]
                    offset_y = aimbot.best_target_position[1]
                    pipe_conn.send({"type": "offsets", "x": offset_x, "y": offset_y, "sniper": aimbot.is_holding_sniper})
                except Exception as e:
                    print(e)
                    pass
            else:
                time.sleep(0.05)

    except KeyboardInterrupt:
        pass
    finally:
        aimbot.cleanup()
