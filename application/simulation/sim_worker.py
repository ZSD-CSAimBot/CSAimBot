"""Simulation control worker and ROS bridge."""

import os
import subprocess
import sys
import threading
import time
import roslibpy


def _repo_root():
    """Get the absolute path to the project root."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _is_process_running(process):
    """Check if a subprocess is actively running."""
    return process is not None and process.poll() is None


def _send_sim_status(pipe, process, message=None):
    """Send simulation status through the IPC pipe.

    Args:
        pipe: Pipe connection to the parent process.
        process: The simulation subprocess or None.
        message: Optional status message to include.
    """
    payload = {
        "type": "simulation_status",
        "status": "running" if _is_process_running(process) else "stopped",
    }
    if message:
        payload["message"] = message
    pipe.send(payload)


def _stop_sim_container():
    """Stop the Docker simulation container."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["wsl", "-d", "Ubuntu", "-e", "docker", "stop", "csaimbot_sim"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=15,
            )
        elif sys.platform == "linux":
            subprocess.run(["sudo", "docker", "stop", "csaimbot_sim"], timeout=15)
        return True
    except Exception:
        return False


class SimulationController:
    """Headless simulation controller that manages Docker and ROS connections."""

    def __init__(self, pipe_conn):
        self.pipe = pipe_conn
        self.current_x = 0.0
        self.current_y = 0.0
        self.target_x = 0.0
        self.target_y = 0.0
        self.waiting_for_target = False
        self.step_size = 0.01
        self.sim_log_file = None

        self.ros = roslibpy.Ros(host="127.0.0.1", port=9090)
        self.delta_pub = roslibpy.Topic(
            self.ros, "/delta_distance", "std_msgs/Float64MultiArray"
        )
        self.click_left_pub = roslibpy.Topic(self.ros, "/click_left", "std_msgs/Empty")
        self.click_right_pub = roslibpy.Topic(
            self.ros, "/click_right", "std_msgs/Empty"
        )
        self.gripper_srv = roslibpy.Service(
            self.ros, "/set_gripper_state", "std_srvs/SetBool"
        )
        self.z_axis_srv = roslibpy.Service(
            self.ros, "/set_z_axis_state", "std_srvs/SetBool"
        )
        self.joint_sub = roslibpy.Topic(
            self.ros, "/joint_states", "sensor_msgs/JointState"
        )

        self.sim_process = self.run_sim()
        threading.Thread(target=self.connect_to_ros, daemon=True).start()

    def run_sim(self):
        """Launch the Docker-based simulator in a subprocess.

        Returns:
            The simulator subprocess handle.
        """
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            log_path = os.path.join(exe_dir, "docker_logs", "docker.log")
        else:
            log_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "docker_logs", "docker.log"
            )

        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        self.sim_log_file = open(
            log_path, "a", encoding="utf-8", errors="replace", buffering=1
        )
        self.sim_log_file.write("\n\nCSAimBot Docker simulation start\n")
        self.sim_log_file.flush()

        if sys.platform == "win32":
            if getattr(sys, "frozen", False):
                path = os.path.join(
                    getattr(sys, "_MEIPASS"), "application", "simulation", "run_sim.bat"
                )
            else:
                path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "run_sim.bat"
                )

            env = os.environ.copy()
            env["CSAIMBOT_NO_PAUSE"] = "1"

            sim_process = subprocess.Popen(
                ["cmd.exe", "/c", path],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=self.sim_log_file,
                stderr=subprocess.STDOUT,
                env=env,
            )

        elif sys.platform.startswith("linux"):
            if getattr(sys, "frozen", False):
                path = os.path.join(
                    getattr(sys, "_MEIPASS"), "application", "simulation", "run_sim.sh"
                )
            else:
                path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "run_sim.sh"
                )

            sim_process = subprocess.Popen(
                ["bash", path], stdout=self.sim_log_file, stderr=subprocess.STDOUT
            )
        else:
            sim_process = None

        return sim_process

    def stop_sim(self):
        """Shut down the Docker container and simulation process."""
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
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                elif sys.platform.startswith("linux"):
                    self.sim_process.terminate()
                print("Sim windows has closed.")
            except Exception as e:
                pass

        if self.sim_log_file:
            self.sim_log_file.write("CSAimBot Docker simulation stop\n")
            self.sim_log_file.close()
            self.sim_log_file = None

        if self.ros.is_connected:
            self.ros.terminate()

    def connect_to_ros(self):
        """Establish connection to ROS and subscribe to joint state updates."""
        try:
            self.ros.run(timeout=999999)
            if self.ros.is_connected:
                _send_sim_status(self.pipe, self.sim_process, "Connected.")
                self.joint_sub.subscribe(self.joint_states_callback)
        except Exception as e:
            _send_sim_status(self.pipe, self.sim_process, f"Connection error: {e}")

    def joint_states_callback(self, msg):
        """Handle ROS joint state messages and check for target reached."""
        names = msg["name"]
        positions = msg["position"]
        if "x_axis_joint" in names and "y_axis_joint" in names:
            idx_x = names.index("x_axis_joint")
            idx_y = names.index("y_axis_joint")

            self.current_x = positions[idx_y]
            self.current_y = positions[idx_x]

            # Send position back to GUI
            self.pipe.send(
                {
                    "type": "sim_position_updated",
                    "x": self.current_x,
                    "y": self.current_y,
                }
            )

            if self.waiting_for_target:
                diff_x = abs(self.current_x - self.target_x)
                diff_y = abs(self.current_y - self.target_y)
                if diff_x < 0.008 and diff_y < 0.008:
                    self.waiting_for_target = False
                    self.execute_auto_click()

    def move_platform(self, dx, dy):
        """Send a delta movement command to the platform."""
        if not self.ros.is_connected:
            return
        msg = roslibpy.Message({"data": [dy, dx]})
        self.delta_pub.publish(msg)

    def send_z_command(self, is_up):
        """Control the Z-axis (vertical) movement."""
        if not self.ros.is_connected:
            return
        req = roslibpy.ServiceRequest({"data": is_up})
        self.z_axis_srv.call(
            req, lambda res: print(f"Z-Axis: {res.get('message', '')}")
        )

    def send_gripper(self, close_gripper):
        """Control the gripper open/close state."""
        if not self.ros.is_connected:
            return
        req = roslibpy.ServiceRequest({"data": close_gripper})
        self.gripper_srv.call(
            req, lambda res: print(f"Gripper: {res.get('message', '')}")
        )

    def send_left_click(self):
        """Publish a left mouse click event."""
        if not self.ros.is_connected:
            return
        msg = roslibpy.Message({})
        self.click_left_pub.publish(msg)

    def send_right_click(self):
        """Publish a right mouse click event."""
        if not self.ros.is_connected:
            return
        msg = roslibpy.Message({})
        self.click_right_pub.publish(msg)

    def go_and_click(self, target_x, target_y):
        """Move to the target coordinates and fire a left click."""
        try:
            self.target_x = float(target_x)
            self.target_y = float(target_y)

            dx = self.target_x - self.current_x
            dy = self.target_y - self.current_y

            msg = roslibpy.Message({"data": [dy, dx]})
            self.delta_pub.publish(msg)

            self.waiting_for_target = True
        except ValueError:
            pass

    def execute_auto_click(self):
        """Fire a left click when target position is reached."""
        msg = roslibpy.Message({})
        self.click_left_pub.publish(msg)


def simulation_worker(pipe):
    """Main worker loop for managing simulation lifecycle."""
    controller = None
    last_status = None
    running = True

    # Initial status
    _send_sim_status(pipe, None)

    while running:
        while pipe.poll():
            msg = pipe.recv()
            cmd = msg.get("cmd")

            if cmd == "START_SIM":
                if controller is None:
                    _send_sim_status(pipe, None, "Starting simulation...")
                    controller = SimulationController(pipe)
                else:
                    _send_sim_status(
                        pipe, controller.sim_process, "Simulation is already running."
                    )
            elif cmd == "STOP_SIM":
                if controller:
                    controller.stop_sim()
                    controller = None
                    _send_sim_status(pipe, None, "Simulation stopped.")
            elif cmd == "STATUS":
                _send_sim_status(pipe, controller.sim_process if controller else None)

            # Platform control commands
            elif cmd == "SIM_MOVE":
                if controller:
                    controller.move_platform(msg.get("dx", 0.0), msg.get("dy", 0.0))
            elif cmd == "SIM_CENTER":
                if controller:
                    controller.move_platform(
                        -controller.current_x, -controller.current_y
                    )
            elif cmd == "SIM_Z_AXIS":
                if controller:
                    controller.send_z_command(msg.get("is_up", False))
            elif cmd == "SIM_GRIPPER":
                if controller:
                    controller.send_gripper(msg.get("close", False))
            elif cmd == "SIM_LEFT_CLICK":
                if controller:
                    controller.send_left_click()
            elif cmd == "SIM_RIGHT_CLICK":
                if controller:
                    controller.send_right_click()
            elif cmd == "SIM_GO_AND_CLICK":
                if controller:
                    controller.go_and_click(msg.get("x", 0.0), msg.get("y", 0.0))

            elif cmd == "QUIT":
                running = False
                break

        current_process = controller.sim_process if controller else None
        current_status = (
            "running" if _is_process_running(current_process) else "stopped"
        )

        if current_status != last_status:
            _send_sim_status(pipe, current_process)
            last_status = current_status

        time.sleep(0.05)

    if controller:
        controller.stop_sim()
