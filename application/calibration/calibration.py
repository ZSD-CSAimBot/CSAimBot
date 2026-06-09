import cv2
import numpy as np
import pyautogui
import math
import time
import os
import glob
import re
import tkinter as tk
from tkinter import filedialog

# Force Windows to be DPI aware so pixel measurements are 100% accurate 
# regardless of Windows Display Scaling (125%, 150%, etc.)
try:
    import ctypes

    ctypes.windll.user32.SetProcessDPIAware()
except AttributeError:
    pass  # Ignore on non-Windows systems


class CalibrationRoutine:
    """Handles the automated calibration routine for skew angle and DPI."""

    def __init__(self, gui_instance):
        self.gui = gui_instance
        self.running = True
        self.is_cancelled = False

    def send_command(self, keys, override_speed=75):
        """Sends simulated key presses to the ESP32 via the comms pipe."""
        command = f"0,0,0,{keys},{override_speed},0,7,7"

        if self.gui.is_connected:
            self.gui.comms_pipe.send({"cmd": "SEND", "value": command})

    def get_csgo_sensitivity(self):
        """
        Attempts to automatically find the CS:GO sensitivity from local config files.
        Sorts by modified date to guarantee reading from the active Steam account.
        """
        possible_paths = [
            r"C:\Program Files (x86)\Steam\userdata\*\4465480\local\cfg\config.cfg",
            r"C:\Program Files\Steam\userdata\*\4465480\local\cfg\config.cfg",
            r"D:\Steam\userdata\*\4465480\local\cfg\config.cfg",
            r"E:\Steam\userdata\*\4465480\local\cfg\config.cfg"
        ]

        found_configs = []
        for path_pattern in possible_paths:
            found_configs.extend(glob.glob(path_pattern))

        if found_configs:
            # Sort files by Last Modified Date (newest first)
            found_configs.sort(key=os.path.getmtime, reverse=True)

            for match in found_configs:
                try:
                    with open(match, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        sens_match = re.search(r'(?i)(?m)^sensitivity\s+["\']?([0-9.]+)["\']?', content)
                        if sens_match:
                            self.gui.add_log(f"<Calibration> Auto-detected active config: {match}", color=[80, 255, 80])
                            return float(sens_match.group(1))
                except Exception:
                    continue

        # If auto-detection fails, ask the user
        self.gui.add_log("<Calibration> Config not found. Please select it manually.", color=[255, 255, 80])
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        file_path = filedialog.askopenfilename(
            title="Select CS:GO Config File (config.cfg)",
            filetypes=[("CS:GO Config", "*.cfg"), ("All Files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    sens_match = re.search(r'(?i)(?m)^sensitivity\s+["\']?([0-9.]+)["\']?', content)
                    if sens_match:
                        self.gui.add_log(f"<Calibration> Loaded config from: {file_path}", color=[80, 255, 80])
                        return float(sens_match.group(1))
            except Exception as e:
                self.gui.add_log(f"<Calibration> Error reading file: {e}", color=[255, 80, 80])

        self.gui.add_log("<Calibration> Warning: Using default sensitivity 1.5", color=[255, 80, 80])
        return 1.5

    def create_calibration_image(self):
        """Creates a black fullscreen image with red target squares."""
        screen_w, screen_h = pyautogui.size()
        img = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)

        cx, cy = screen_w // 2, screen_h // 2
        offset_x = int(screen_w * 0.3)
        offset_y = int(screen_h * 0.3)

        points = {
            "left": (cx - offset_x, cy),
            "right": (cx + offset_x, cy),
            "top": (cx, cy - offset_y),
            "bottom": (cx, cy + offset_y)
        }

        for name, pt in points.items():
            cv2.rectangle(img, (pt[0] - 15, pt[1] - 15), (pt[0] + 15, pt[1] + 15), (0, 0, 255), -1)

        return img, points

    def precise_drive(self, target_x, target_y, mode="both"):
        """
        Drives the robot to the target using slow, deliberate steps.
        Completely bypasses PID and acts at its own independent pace.
        """
        start_t = time.time()

        while self.running and time.time() - start_t < 30:
            if getattr(self, 'is_cancelled', False):
                self.send_command("-", 0)
                return False

            mx, my = pyautogui.position()
            dx = target_x - mx
            dy = target_y - my

            if mode == "x_only":
                dy = 0
            elif mode == "y_only":
                dx = 0

            dist = math.hypot(dx, dy)

            if mode == "both" and abs(dx) <= 2 and abs(dy) <= 2:
                break
            elif mode == "x_only" and abs(dx) <= 2:
                break
            elif mode == "y_only" and abs(dy) <= 2:
                break

            keys = ""
            if dx > 2:
                keys += "l"
            elif dx < -2:
                keys += "j"

            if dy > 2:
                keys += "k"
            elif dy < -2:
                keys += "i"

            if not keys:
                break

            # PULSE DRIVE - Slow, hard steps
            if dist > 150:
                self.send_command(keys, override_speed=35)
                time.sleep(0.02)
                self.send_command("-", 0)
                time.sleep(0.15)
            elif dist > 40:
                self.send_command(keys, override_speed=35)
                time.sleep(0.02)
                self.send_command("-", 0)
                time.sleep(0.15)
            else:
                self.send_command(keys, override_speed=10)
                time.sleep(0.02)
                self.send_command("-", 0)
                time.sleep(0.2)

        self.send_command("-", 0)
        time.sleep(0.5)
        return True

    def run(self):
        """Main execution flow for the calibration process."""
        csgo_sens = self.get_csgo_sensitivity()

        if self.gui.is_connected:
            self.gui.add_log("<Calibration> Resetting previous skew data on ESP32...", color=[255, 255, 80])
            self.gui.comms_pipe.send({"cmd": "SEND", "value": "CALIBRATION,1000,0.0,0.0"})
            time.sleep(0.5)

        img, points = self.create_calibration_image()
        window_name = "Calibration Routine"
        cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        self.gui.add_log("<Calibration> Window opened. Press '[' to start.", color=[255, 255, 80])

        while True:
            cv2.imshow(window_name, img)
            key = cv2.waitKey(10) & 0xFF
            if key == ord('[') and not getattr(self, 'is_cancelled', False):
                break
            elif key == 27 or getattr(self, 'is_cancelled', False):
                self.is_cancelled = True
                cv2.destroyWindow(window_name)
                self.gui.add_log("<Calibration> Canceled by user.", color=[255, 80, 80])
                return

        # ==========================================
        # STAGE 1: X-AXIS CALIBRATION
        # ==========================================
        self.gui.add_log("<Calibration> [X] Aligning to left square...", color=[80, 255, 80])
        if not self.precise_drive(points["left"][0], points["left"][1], mode="both"):
            cv2.destroyWindow(window_name)
            return
        time.sleep(1.5)

        start_mouse_x = pyautogui.position()
        start_phys_x = self.gui.pos_x

        self.gui.add_log("<Calibration> [X] Tracking to right square...", color=[80, 255, 80])
        if not self.precise_drive(points["right"][0], points["right"][1], mode="x_only"):
            cv2.destroyWindow(window_name)
            return
        time.sleep(1.5)

        end_mouse_x = pyautogui.position()
        end_phys_x = self.gui.pos_x

        # ==========================================
        # STAGE 2: Y-AXIS CALIBRATION
        # ==========================================
        self.gui.add_log("<Calibration> [Y] Aligning to top square...", color=[80, 255, 80])
        if not self.precise_drive(points["top"][0], points["top"][1], mode="both"):
            cv2.destroyWindow(window_name)
            return
        time.sleep(1.5)

        start_mouse_y = pyautogui.position()
        start_phys_y = self.gui.pos_y

        self.gui.add_log("<Calibration> [Y] Tracking down...", color=[80, 255, 80])
        if not self.precise_drive(points["bottom"][0], points["bottom"][1], mode="y_only"):
            cv2.destroyWindow(window_name)
            return
        time.sleep(1.5)

        end_mouse_y = pyautogui.position()
        end_phys_y = self.gui.pos_y

        cv2.destroyWindow(window_name)

        # ==========================================
        # STAGE 3: MATHEMATICS AND CALCULATIONS
        # ==========================================
        dx_mouse_x = end_mouse_x[0] - start_mouse_x[0]
        dy_mouse_x = end_mouse_x[1] - start_mouse_x[1]
        theta_x_rad = math.atan2(dy_mouse_x, dx_mouse_x)
        dx_phys_cm = abs(end_phys_x - start_phys_x)
        dpi_x = (math.hypot(dx_mouse_x, dy_mouse_x) / (dx_phys_cm / 2.54)) if dx_phys_cm > 0 else 0

        dx_mouse_y = end_mouse_y[0] - start_mouse_y[0]
        dy_mouse_y = end_mouse_y[1] - start_mouse_y[1]
        theta_y_rad = math.atan2(dy_mouse_y, dx_mouse_y) - (math.pi / 2)
        dy_phys_cm = abs(end_phys_y - start_phys_y)
        dpi_y = (math.hypot(dx_mouse_y, dy_mouse_y) / (dy_phys_cm / 2.54)) if dy_phys_cm > 0 else 0

        raw_dpi = (dpi_x + dpi_y) / 2
        if raw_dpi < 0: raw_dpi = 0

        # Rounding DPI to nearest 100 (e.g. 824 -> 800, 851 -> 900)
        rounded_dpi = int(round(raw_dpi / 100.0) * 100)
        if rounded_dpi == 0: rounded_dpi = 100  # Fallback safety

        # ==========================================
        # STAGE 4: EDPI CALCULATION AND SENDING
        # ==========================================
        edpi = rounded_dpi * csgo_sens

        self.gui.add_log(
            f"<Calibration> X Skew: {math.degrees(theta_x_rad):.2f}°, Y Skew: {math.degrees(theta_y_rad):.2f}°",
            color=[80, 255, 255])
        self.gui.add_log(f"<Calibration> Detected {raw_dpi:.0f} DPI -> Rounded to {rounded_dpi} DPI",
                         color=[255, 255, 80])
        self.gui.add_log(f"<Calibration> Base DPI: {rounded_dpi} | Sens: {csgo_sens} -> eDPI: {edpi:.0f}",
                         color=[255, 180, 80])

        # Save parameters
        self.gui.calibration_angle_x = theta_x_rad
        self.gui.calibration_angle_y = theta_x_rad
        self.gui.calibration_dpi = rounded_dpi

        if self.gui.is_connected:
            # Send 4 parameters with negative angles to invert the coordinate system vector
            command = f"CALIBRATION,{int(edpi)},{-theta_x_rad:.4f},{-theta_y_rad:.4f}"
            self.gui.comms_pipe.send({"cmd": "SEND", "value": command})
            self.gui.add_log("<Calibration> Data sent to ESP32! Calibration complete.", color=[80, 255, 80])
        else:
            self.gui.add_log("<Calibration> Not connected to ESP32! Data not sent.", color=[255, 80, 80])