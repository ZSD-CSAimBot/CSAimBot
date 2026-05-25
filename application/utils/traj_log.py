import json
import os
import time
from datetime import datetime


class TrajectoryLogger:
    def __init__(self):
        # Automatically set path to /utils/telemetry/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(current_dir, "telemetry")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        self.current_data = None
        self.start_time = 0

    def start_recording(self, target_dx, target_dy, start_x, start_y):
        """Starts continuous trajectory recording."""
        self.start_time = time.time()
        self.current_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
            "target_pixel_offset": {"dx": target_dx, "dy": target_dy},
            "robot_start_pos_cm": {"x": start_x, "y": start_y},
            "path": []
        }

    def update_target(self, dx, dy):
        """Updates target offset if it wasn't visible when recording started."""
        if self.current_data and self.current_data["target_pixel_offset"] == {"dx": 0, "dy": 0}:
            self.current_data["target_pixel_offset"] = {"dx": dx, "dy": dy}

    def add_point(self, current_time, x, y):
        """Logs current robot position."""
        if self.current_data is not None:
            rel_time = current_time - self.start_time
            self.current_data["path"].append({
                "time": round(rel_time, 4),
                "x": round(x, 4),
                "y": round(y, 4)
            })

    def save_to_json(self):
        """Stops recording and dumps data to a JSON file."""
        if not self.current_data or not self.current_data["path"]:
            self.current_data = None
            return None

        last_point = self.current_data["path"][-1]
        self.current_data["robot_end_pos_cm"] = {"x": last_point["x"], "y": last_point["y"]}

        filename = f"trajectory_{self.current_data['timestamp']}.json"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w') as f:
            json.dump(self.current_data, f, indent=4)

        self.current_data = None
        return filepath