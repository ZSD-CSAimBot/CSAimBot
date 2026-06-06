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
            r"C:\Program Files (x86)\Steam\userdata\*\730\local\cfg\config.cfg",
            r"C:\Program Files\Steam\userdata\*\730\local\cfg\config.cfg",
            r"D:\Steam\userdata\*\730\local\cfg\config.cfg",
            r"E:\Steam\userdata\*\730\local\cfg\config.cfg"
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
                        sens_match = re.search(r'(?m)^sensitivity\s+"([0-9.]+)"', content)
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
                    sens_match = re.search(r'(?m)^sensitivity\s+"([0-9.]+)"', content)
                    if sens_match:
                        self.gui.add_log(f"<Calibration> Loaded config from: {file_path}", color=[80, 255, 80])
                        return float(sens_match.group(1))
            except Exception as e:
                self.gui.add_log(f"<Calibration> Error reading file: {e}", color=[255, 80, 80])

        self.gui.add_log("<Calibration> Warning: Using default sensitivity 1.5", color=[255, 80, 80])
        return 1.5

    def create_calibration_image(self):
        """Generates a fullscreen calibration image dynamically."""
        # Get current screen resolution
        screen_w, screen_h = pyautogui.size()

        # Create a black background
        img = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)

        cx, cy = screen_w // 2, screen_h // 2

        # Draw white grid lines
        cv2.line(img, (0, cy), (screen_w, cy), (255, 255, 255), 2)
        cv2.line(img, (cx, 0), (cx, screen_h), (255, 255, 255), 2)

        # Calculate distance of points from the center (40% of the smaller dimension)
        offset = int(min(screen_w, screen_h) * 0.4)

        # Define exact mathematical coordinates
        points = {
            "center": (cx, cy),
            "left": (cx - offset, cy),
            "right": (cx + offset, cy),
            "top": (cx, cy - offset),
            "bottom": (cx, cy + offset)
        }

        # Draw red squares (BGR in OpenCV)
        sz = 8
        for name, (px, py) in points.items():
            cv2.rectangle(img, (px - sz, py - sz), (px + sz, py + sz), (0, 0, 255), -1)

        return img, points

    def precise_drive(self, target_x, target_y, mode="both"):
        """
        Drives the robot to the target with high precision.
        mode can be: "both" (X and Y), "x_only" (horizontal track), "y_only" (vertical track)
        """
        start_t = time.time()

        # Increased timeout to 30 seconds due to slower precision creeping
        while self.running and time.time() - start_t < 30:
            mx, my = pyautogui.position()
            dx = target_x - mx
            dy = target_y - my

            # Force ignoring the other axis when testing a specific vector
            if mode == "x_only":
                dy = 0
            elif mode == "y_only":
                dx = 0

            dist = math.hypot(dx, dy)

            # Deadzone of 2 pixels for absolute precision
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

            # Adaptive speed and micro-pulsing algorithm
            if dist > 150:
                self.send_command(keys, override_speed=65)
                time.sleep(0.05)
            elif dist > 40:
                self.send_command(keys, override_speed=35)
                time.sleep(0.05)
            else:
                # Precision mode (Creeping / Pulsing) - eliminates inertia and jitter
                self.send_command(keys, override_speed=15)
                time.sleep(0.02)  # Short movement pulse
                self.send_command("-", 0)  # Hit the "brakes"
                time.sleep(0.15)  # Wait for COMPLETE mechanical stabilization before next frame check

        self.send_command("-", 0)
        time.sleep(0.5)  # Final platform stabilization after movement ends

    def run(self):
        """Main execution flow for the calibration process."""

        # Step 0: Read sensitivity from game files
        #csgo_sens = self.get_csgo_sensitivity()
        csgo_sens = 2.5

        if self.gui.is_connected:
            self.gui.add_log("<Calibration> Resetting previous skew data on ESP32...", color=[255, 255, 80])
            self.gui.comms_pipe.send({"cm111111111111111111112d": "SEND", "value": "CALIBRATION,1000,0.0"})
            time.sleep(0.5)

        # Generate image and coordinates
        img, points = self.create_calibration_image()

        window_name = "Calibration Routine"
        cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        self.gui.add_log("<Calibration> Window opened. Press '[' to start.", color=[255, 255, 80])

        while True:
            cv2.imshow(window_name, img)
            key = cv2.waitKey(10) & 0xFF
            if key == ord('['):
                break
            elif key == 27:
                cv2.destroyWindow(window_name)
                self.gui.add_log("<Calibration> Canceled by user.", color=[255, 80, 80])
                return

        # ==========================================
        # STAGE 1: X-AXIS CALIBRATION
        # ==========================================
        self.gui.add_log("<Calibration> [X] Aligning to left square...", color=[80, 255, 80])
        self.precise_drive(points["left"][0], points["left"][1], mode="both")
        time.sleep(1.5)  # Extended wait to ensure ESP32 serial data catches up fully

        start_mouse_x = pyautogui.position()
        start_phys_x = self.gui.pos_x

        self.gui.add_log("<Calibration> [X] Tracking to right square...", color=[80, 255, 80])
        self.precise_drive(points["right"][0], points["right"][1], mode="x_only")
        time.sleep(1.5)

        end_mouse_x = pyautogui.position()
        end_phys_x = self.gui.pos_x

        # ==========================================
        # STAGE 2: Y-AXIS CALIBRATION
        # ==========================================
        self.gui.add_log("<Calibration> [Y] Aligning to top square...", color=[80, 255, 80])
        self.precise_drive(points["top"][0], points["top"][1], mode="both")
        time.sleep(1.5)

        start_mouse_y = pyautogui.position()
        start_phys_y = self.gui.pos_y

        self.gui.add_log("<Calibration> [Y] Tracking down...", color=[80, 255, 80])
        self.precise_drive(points["bottom"][0], points["bottom"][1], mode="y_only")
        time.sleep(1.5)

        end_mouse_y = pyautogui.position()
        end_phys_y = self.gui.pos_y

        cv2.destroyWindow(window_name)

        # ==========================================
        # STAGE 3: MATHEMATICS AND CALCULATIONS
        # ==========================================

        # 1. X-axis analysis
        dx_mouse_x = end_mouse_x[0] - start_mouse_x[0]
        dy_mouse_x = end_mouse_x[1] - start_mouse_x[1]

        theta_x_rad = math.atan2(dy_mouse_x, dx_mouse_x)

        dx_phys_cm = abs(end_phys_x - start_phys_x)
        dpi_x = (math.hypot(dx_mouse_x, dy_mouse_x) / (dx_phys_cm / 2.54)) if dx_phys_cm > 0 else 0

        # 2. Y-axis analysis
        dx_mouse_y = end_mouse_y[0] - start_mouse_y[0]
        dy_mouse_y = end_mouse_y[1] - start_mouse_y[1]

        # Ideal Y vector is (0, 1), its angle is 90 degrees (pi/2). The difference is the skew.
        theta_y_rad = math.atan2(dy_mouse_y, dx_mouse_y) - (math.pi / 2)

        dy_phys_cm = abs(end_phys_y - start_phys_y)
        dpi_y = (math.hypot(dx_mouse_y, dy_mouse_y) / (dy_phys_cm / 2.54)) if dy_phys_cm > 0 else 0

        # 3. Averaging
        avg_theta_rad = (theta_x_rad + theta_y_rad) / 2
        avg_dpi = (dpi_x + dpi_y) / 2

        if avg_dpi < 0: avg_dpi = 0

        # ==========================================
        # 4. EDPI CALCULATION AND SENDING TO ESP32
        # ==========================================

        edpi = avg_dpi * csgo_sens

        self.gui.add_log(
            f"<Calibration> X Skew: {math.degrees(theta_x_rad):.2f}°, Y Skew: {math.degrees(theta_y_rad):.2f}°",
            color=[80, 255, 255])
        self.gui.add_log(f"<Calibration> Avg Skew Angle: {math.degrees(avg_theta_rad):.2f}°", color=[255, 255, 80])
        self.gui.add_log(f"<Calibration> Base DPI: {avg_dpi:.0f} | Sens: {csgo_sens} -> eDPI: {edpi:.0f}",
                         color=[255, 180, 80])

        # Save parameters to memory
        self.gui.calibration_angle = avg_theta_rad
        self.gui.calibration_dpi = avg_dpi

        # Send command to ESP32 in format: CALIBRATION,eDPI,skewAngle
        if self.gui.is_connected:
            command = f"CALIBRATION,{int(edpi)},{avg_theta_rad:.4f}"
            self.gui.comms_pipe.send({"cmd": "SEND", "value": command})
            self.gui.add_log("<Calibration> Data sent to ESP32! Calibration complete.", color=[80, 255, 80])
        else:
            self.gui.add_log("<Calibration> Not connected to ESP32! Data not sent.", color=[255, 80, 80])