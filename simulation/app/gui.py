import os
import subprocess
import sys
import threading
import roslibpy
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QGridLayout, QGroupBox)
from PyQt6.QtCore import pyqtSignal, QObject, Qt


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _is_process_running(process):
    return process is not None and process.poll() is None


def _send_sim_status(pipe, process, message=None):
    payload = {
        "type": "simulation_status",
        "status": "running" if _is_process_running(process) else "stopped"
    }
    if message:
        payload["message"] = message
    pipe.send(payload)


def _pythonw_executable():
    if sys.platform != "win32":
        return sys.executable

    pythonw_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return pythonw_path if os.path.exists(pythonw_path) else sys.executable


def _stop_sim_container():
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["wsl", "-d", "Ubuntu", "-e", "docker", "stop", "csaimbot_sim"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=15
            )
        elif sys.platform == "linux":
            subprocess.run(
                ["sudo", "docker", "stop", "csaimbot_sim"],
                timeout=15
            )
        return True
    except Exception:
        return False


def _start_sim_gui_process(pipe, process):
    if _is_process_running(process):
        _send_sim_status(pipe, process, "Simulation is already running.")
        return process

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    process = subprocess.Popen(
        [_pythonw_executable(), os.path.abspath(__file__)],
        cwd=_repo_root(),
        creationflags=creationflags
    )
    _send_sim_status(pipe, process, "Simulation started.")
    return process


def _stop_sim_gui_process(pipe, process):
    if not _is_process_running(process):
        _send_sim_status(pipe, None, "Simulation is not running.")
        return None

    try:
        _stop_sim_container()
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            process.terminate()
    finally:
        _send_sim_status(pipe, None, "Simulation stopped.")

    return None


def simulation_worker(pipe):
    process = None
    last_status = None
    running = True
    _send_sim_status(pipe, process)

    while running:
        while pipe.poll():
            msg = pipe.recv()
            cmd = msg.get("cmd")

            if cmd == "START":
                process = _start_sim_gui_process(pipe, process)
            elif cmd == "STOP":
                process = _stop_sim_gui_process(pipe, process)
            elif cmd == "STATUS":
                _send_sim_status(pipe, process)
            elif cmd == "QUIT":
                running = False
                break

        current_status = "running" if _is_process_running(process) else "stopped"
        if current_status != last_status:
            _send_sim_status(pipe, process)
            last_status = current_status

        threading.Event().wait(0.05)

    if _is_process_running(process):
        _stop_sim_gui_process(pipe, process)


class RosSignals(QObject):
    connected = pyqtSignal()
    error = pyqtSignal(str)
    position_updated = pyqtSignal(float, float)
    reached_target = pyqtSignal()

class CSAimBotGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simulation control pannel")
        self.setFixedSize(540, 760) 
        self.signals = RosSignals()

        self.current_x = 0.0
        self.current_y = 0.0
        self.target_x = 0.0
        self.target_y = 0.0
        self.waiting_for_target = False
        self.step_size = 0.01  
        self.sim_log_file = None

        self.sim_process = self.run_sim()

        self.ros = roslibpy.Ros(host='127.0.0.1', port=9090)
        self.delta_pub = roslibpy.Topic(self.ros, '/delta_distance', 'std_msgs/Float64MultiArray')
        self.click_left_pub = roslibpy.Topic(self.ros, '/click_left', 'std_msgs/Empty')
        self.click_right_pub = roslibpy.Topic(self.ros, '/click_right', 'std_msgs/Empty')
        self.gripper_srv = roslibpy.Service(self.ros, '/set_gripper_state', 'std_srvs/SetBool')
        self.z_axis_srv = roslibpy.Service(self.ros, '/set_z_axis_state', 'std_srvs/SetBool')
        self.joint_sub = roslibpy.Topic(self.ros, '/joint_states', 'sensor_msgs/JointState')

        self.build_ui()
        self.apply_styles()
        
        self.signals.connected.connect(self.on_connected)
        self.signals.error.connect(self.on_connection_error)
        self.signals.position_updated.connect(self.update_position_label)
        self.signals.reached_target.connect(self.execute_auto_click)

        threading.Thread(target=self.connect_to_ros, daemon=True).start()

    def apply_styles(self):
        style_sheet = """
            QMainWindow {
                background-color: #1a1a21;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                color: #e0e0e0;
            }
            QGroupBox {
                background-color: #141419;
                border: 1px solid #333344;
                border-radius: 4px;
                margin-top: 25px;
                padding: 15px 10px 10px 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0px 5px;
                background-color: transparent;
                color: #ffb800;
                font-size: 15px;
            }
            QPushButton {
                background-color: #3b4252;
                border: 1px solid #2e3440;
                border-radius: 4px;
                padding: 4px 2px;  
                margin: 2px;       
                min-height: 24px; 
                font-size: 13px;   
                font-weight: bold;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4c566a;
                border: 1px solid #ffb800;
            }
            QPushButton:pressed {
                background-color: #2e3440;
            }
            QLineEdit {
                background-color: #0f0f15;
                border: 1px solid #333344;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #ffb800;
            }
            QPushButton#btnShoot {
                background-color: #ffb800;
                color: #444444;
                font-size: 14px;
                border: none;
                margin: 0px; 
            }
            QPushButton#btnShoot:hover {
                background-color: #ffc21a;
            }
            QPushButton#btnShoot:pressed {
                background-color: #e6a600;
            }
        """
        self.setStyleSheet(style_sheet)

    def run_sim(self):

        log_path = os.path.abspath("simulation/docker_logs/docker.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        self.sim_log_file = open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)
        self.sim_log_file.write("\n\nCSAimBot Docker simulation start\n")
        self.sim_log_file.flush()

        if sys.platform == "win32":
            path = os.path.abspath("simulation/sim/run_sim.bat")

            env = os.environ.copy()
            env["CSAIMBOT_NO_PAUSE"] = "1"

            sim_process = subprocess.Popen(
                ["cmd.exe", "/c", path],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=self.sim_log_file,
                stderr=subprocess.STDOUT,
                env=env
            )
            
        elif sys.platform == "linux":
            path = os.path.abspath("simulation/sim/run_sim.sh")
            
            sim_process = subprocess.Popen(
                ["bash", path],
                stdout=self.sim_log_file,
                stderr=subprocess.DEVNULL
            )
        else:
            sim_process = None

        return sim_process
    
    def stop_sim(self):
        print("Shutting down docker container(csaimbot_sim)...")
        try:
            _stop_sim_container()
            print("Container succesfully closed.")
        except Exception as e:
            print(f"Error during shutting down docker container: {e}")

        if self.sim_process:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.sim_process.pid)],
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )

                elif sys.platform == "linux":
                    self.sim_process.terminate()
                print("Sim windows has closed.")
            except Exception as e:
                pass

        if self.sim_log_file:
            self.sim_log_file.write("CSAimBot Docker simulation stop\n")
            self.sim_log_file.close()
            self.sim_log_file = None

    def build_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        self.label_status = QLabel("Waiting for connection...")
        self.label_status.setStyleSheet("color: #ffb800; font-size: 16px;")
        main_layout.addWidget(self.label_status)

        self.label_pos = QLabel("Current position: X=0.000, Y=0.000")
        self.label_pos.setStyleSheet("font-size: 15px; margin-bottom: 5px;")
        main_layout.addWidget(self.label_pos)

        dpad_group = QGroupBox("Platform control")
        dpad_layout = QGridLayout()
        dpad_layout.setSpacing(8)
        
        self.btn_nw = QPushButton("↖ (Q)")
        self.btn_n = QPushButton("↑ (W)")
        self.btn_ne = QPushButton("↗ (E)")
        self.btn_w = QPushButton("← (A)")
        self.btn_center = QPushButton("Center")
        self.btn_e = QPushButton("→ (D)")
        self.btn_sw = QPushButton("↙ (Z)")
        self.btn_s = QPushButton("↓ (S)")
        self.btn_se = QPushButton("↘ (C)")
        
        self.btn_nw.clicked.connect(lambda: self.move_platform(-self.step_size, -self.step_size))
        self.btn_n.clicked.connect(lambda:  self.move_platform(0, -self.step_size))
        self.btn_ne.clicked.connect(lambda: self.move_platform(self.step_size, -self.step_size))
        self.btn_w.clicked.connect(lambda:  self.move_platform(-self.step_size, 0))
        self.btn_center.clicked.connect(lambda: self.move_platform(-self.current_x, -self.current_y))
        self.btn_e.clicked.connect(lambda:  self.move_platform(self.step_size, 0))
        self.btn_sw.clicked.connect(lambda: self.move_platform(-self.step_size, self.step_size))
        self.btn_s.clicked.connect(lambda:  self.move_platform(0, self.step_size))
        self.btn_se.clicked.connect(lambda: self.move_platform(self.step_size, self.step_size))
                                                       
        dpad_layout.addWidget(self.btn_nw, 0, 0); dpad_layout.addWidget(self.btn_n, 0, 1); dpad_layout.addWidget(self.btn_ne, 0, 2)
        dpad_layout.addWidget(self.btn_w, 1, 0); dpad_layout.addWidget(self.btn_center, 1, 1); dpad_layout.addWidget(self.btn_e, 1, 2)
        dpad_layout.addWidget(self.btn_sw, 2, 0); dpad_layout.addWidget(self.btn_s, 2, 1); dpad_layout.addWidget(self.btn_se, 2, 2)
        dpad_group.setLayout(dpad_layout)
        main_layout.addWidget(dpad_group)

        z_axis_group = QGroupBox("Z axis")
        z_axis_layout = QHBoxLayout()
        btn_z_up = QPushButton("Pick up mouse")
        btn_z_up.clicked.connect(lambda: self.send_z_command(True))
        btn_z_down = QPushButton("Put down mouse")
        btn_z_down.clicked.connect(lambda: self.send_z_command(False))
        z_axis_layout.addWidget(btn_z_up)
        z_axis_layout.addWidget(btn_z_down)
        z_axis_group.setLayout(z_axis_layout)
        main_layout.addWidget(z_axis_group)

        gripper_group = QGroupBox("Gripper")
        gripper_layout = QHBoxLayout()
        btn_grip_open = QPushButton("Gripper open")
        btn_grip_open.clicked.connect(lambda: self.send_gripper(False))
        btn_grip_close = QPushButton("Gripper close")
        btn_grip_close.clicked.connect(lambda: self.send_gripper(True))
        gripper_layout.addWidget(btn_grip_open)
        gripper_layout.addWidget(btn_grip_close)
        gripper_group.setLayout(gripper_layout)
        main_layout.addWidget(gripper_group)
        
        mouse_group = QGroupBox("Mouse control")
        mouse_layout = QHBoxLayout()
        
        btn_left_click = QPushButton("Left click")
        btn_left_click.clicked.connect(self.send_left_click)
        btn_right_click = QPushButton("Right click")
        btn_right_click.clicked.connect(self.send_right_click)
        
        mouse_layout.addWidget(btn_left_click); mouse_layout.addWidget(btn_right_click)
        mouse_group.setLayout(mouse_layout)
        main_layout.addWidget(mouse_group)

        target_group = QGroupBox("Set target position")
        target_layout = QHBoxLayout()
        
        self.entry_x = QLineEdit()
        self.entry_x.setPlaceholderText("0.00")
        self.entry_y = QLineEdit()
        self.entry_y.setPlaceholderText("0.00")
        
        btn_go_click = QPushButton("Go and shoot")
        btn_go_click.setObjectName("btnShoot")
        btn_go_click.clicked.connect(self.go_and_click)

        target_layout.addWidget(QLabel("X:"))
        target_layout.addWidget(self.entry_x)
        target_layout.addWidget(QLabel("Y:"))
        target_layout.addWidget(self.entry_y)
        target_layout.addWidget(btn_go_click)
        target_group.setLayout(target_layout)
        main_layout.addWidget(target_group)

    def connect_to_ros(self):
        try:
            self.ros.run(timeout=999999)
            if self.ros.is_connected:
                self.signals.connected.emit()
                self.joint_sub.subscribe(self.joint_states_callback)
        except Exception as e:
            self.signals.error.emit(str(e))

    def on_connected(self):
        self.label_status.setText("Connected.")
        self.label_status.setStyleSheet("color: #00ff00; font-size: 16px;")

    def on_connection_error(self, err_msg):
        self.label_status.setText(f"Connection error: {err_msg}")
        self.label_status.setStyleSheet("color: #cc0000; font-size: 16px;")

    def joint_states_callback(self, msg):
        names = msg['name']
        positions = msg['position']
        if 'x_axis_joint' in names and 'y_axis_joint' in names:
            idx_x = names.index('x_axis_joint')
            idx_y = names.index('y_axis_joint')
            
            self.current_x = positions[idx_y]
            self.current_y = positions[idx_x]
            
            self.signals.position_updated.emit(self.current_x, self.current_y)

            if self.waiting_for_target:
                diff_x = abs(self.current_x - self.target_x)
                diff_y = abs(self.current_y - self.target_y)
                if diff_x < 0.008 and diff_y < 0.008:
                    self.waiting_for_target = False
                    self.signals.reached_target.emit()

    def update_position_label(self, x, y):
        self.label_pos.setText(f"Current position:  X = {x:.4f}  |  Y = {y:.4f}")

    def move_platform(self, dx, dy):
        if not self.ros.is_connected: return
        msg = roslibpy.Message({'data': [dy, dx]})
        self.delta_pub.publish(msg)

    def send_z_command(self, is_up):
        if not self.ros.is_connected: return
        req = roslibpy.ServiceRequest({'data': is_up})
        self.z_axis_srv.call(req, lambda res: print(f"Z-Axis: {res.get('message', '')}"))

    def send_gripper(self, close_gripper):
        if not self.ros.is_connected: return
        req = roslibpy.ServiceRequest({'data': close_gripper})
        self.gripper_srv.call(req, lambda res: print(f"Gripper: {res.get('message', '')}"))

    def send_left_click(self):
        if not self.ros.is_connected: return
        msg = roslibpy.Message({})
        self.click_left_pub.publish(msg)

    def send_right_click(self):
        if not self.ros.is_connected: return
        msg = roslibpy.Message({})
        self.click_right_pub.publish(msg)

    def go_and_click(self):
        try:
            self.target_x = float(self.entry_x.text())
            self.target_y = float(self.entry_y.text())
            
            dx = self.target_x - self.current_x
            dy = self.target_y - self.current_y
            
            msg = roslibpy.Message({'data': [dy, dx]})
            self.delta_pub.publish(msg)
            
            self.waiting_for_target = True
        except ValueError:
            pass

    def execute_auto_click(self):
        msg = roslibpy.Message({})
        self.click_left_pub.publish(msg)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
            
        key = event.key()
        if key == Qt.Key.Key_W:
            self.move_platform(0, -self.step_size)
        elif key == Qt.Key.Key_S:
            self.move_platform(0, self.step_size)
        elif key == Qt.Key.Key_A:
            self.move_platform(-self.step_size, 0)
        elif key == Qt.Key.Key_D:
            self.move_platform(self.step_size, 0)
        elif key == Qt.Key.Key_Q:
            self.move_platform(-self.step_size, -self.step_size)
        elif key == Qt.Key.Key_E:
            self.move_platform(self.step_size, -self.step_size)
        elif key == Qt.Key.Key_Z:
            self.move_platform(-self.step_size, self.step_size)
        elif key == Qt.Key.Key_C:
            self.move_platform(self.step_size, self.step_size)
            
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.stop_sim()
        if self.ros.is_connected:
            self.ros.terminate()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CSAimBotGUI()
    window.show()
    sys.exit(app.exec())
