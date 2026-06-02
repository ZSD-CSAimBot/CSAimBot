"""
ESP32 Serial Communications Module

Provides serial communication interface and keyboard input handling for the CSAimBot
robot control system. Facilitates bidirectional communication with the ESP32 microcontroller
and captures keyboard input for device operation.
"""

import platform
import time
from pynput import keyboard as pynput_kb
import serial


class SerialCommsModule:
    """
    This class manages serial communication with the ESP32 microcontroller.
    It provides methods to connect, send commands, receive responses, and disconnect.
    """

    def __init__(self, port=None, baud_rate=115200, timeout=0.05):
        """
        Initialize serial communication module with platform-specific default port.

        Args:
            port: Serial port name (auto-detected if None)
            baud_rate: Communication speed in bits/second (default: 115200)
            timeout: Read timeout in seconds (default: 2)
        """
        if port is None:
            currentSystem = platform.system()
            if currentSystem == "Windows":
                port = "COM5"
            elif currentSystem == "Darwin":
                port = "/dev/cu.usbserial-110"
            else:
                port = "/dev/ttyUSB0"

        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.esp = None

    def connect(self):
        """
        Tries to establish a serial connection with the ESP32.
        Returns True if successful, False otherwise.
        """
        try:
            self.esp = serial.Serial()
            self.esp.port = self.port
            self.esp.baudrate = self.baud_rate
            self.esp.timeout = self.timeout
            self.esp.dtr = False
            self.esp.rts = False
            self.esp.open()
            time.sleep(1.5)
            if self.check_connection(self.esp, self.port):
                return True
            else:
                self.esp.close()
                return False
        except serial.SerialException as e:
            print(f"Connection error {self.port}\n{e}")
            return False

    def check_connection(self, esp, port):
        """
        Check if ESP32 is responsive by sending a test command and waiting for a specific response.
        Args:
            esp: Opened serial connection to ESP32
            port: Serial port name
        Returns:
            True if ESP32 is responsive, False otherwise
        """
        esp.reset_input_buffer()
        esp.write(f"ESP32-CHECK\r".encode("utf-8"))
        esp.flush()
        start_time = time.time()
        while time.time() - start_time < 5.0:
            if esp.in_waiting > 0:
                response = esp.readline().decode("utf-8", errors="ignore").strip()
                if response == "ESP32-READY":
                    print(f"Connected on {port}.")
                    return True
        print(f"Connection error {port}: No response from ESP32.")
        return False

    def send_command(self, command):
        """
        Encode and send command to ESP32. Appends carriage return for protocol.

        Args:
            command: Command string to send
        """
        if self.esp and self.esp.is_open:
            text_to_send = f"{command}\r".encode("utf-8")
            self.esp.write(text_to_send)
            self.esp.flush()
        else:
            print("Port closed. Unable to send command.")

    def get_response(self):
        """
        Read response from ESP32.

        Returns:
            Response string if available, None otherwise
        """
        if self.esp and self.esp.is_open:
            response = self.esp.readline().decode("utf-8", errors="ignore").strip()
            if response:
                return response
            return None
        else:
            print("Port closed. Unable to read response.")
            return None

    def disconnect(self):
        """Close the serial port if open."""
        if self.esp and self.esp.is_open:
            self.esp.close()
            print("Port closed successfully.")
        else:
            print("Port already closed or not yet opened.")


def comms_worker(conn):
    """
    Manage multiprocess communication between GUI, ESP32, and keyboard input.

    Runs in a separate process and handles command dispatch to ESP32,
    response reception, and keyboard state transmission back to GUI.

    Args:
        conn: multiprocessing.Connection object for IPC
    """
    esp = SerialCommsModule()
    keyboard = KeyboardInputModule()
    last_keys = ""
    last_send_time = 0.0
    is_connected = False
    running = True
    pressed_keys_set = set()  # Track which keys are currently pressed

    while running:
        while conn.poll():
            msg = conn.recv()
            if msg.get("cmd") == "QUIT":
                running = False
            elif msg.get("cmd") == "CONNECT":
                is_connected = esp.connect()
                status_str = "connected" if is_connected else "disconnected"
                conn.send({"type": "connection_status", "status": status_str})
            elif msg.get("cmd") == "DISCONNECT":
                esp.disconnect()
                is_connected = False
                conn.send({"type": "connection_status", "status": "disconnected"})
            elif msg.get("cmd") == "SEND":
                esp.send_command(msg.get("value"))
            elif msg.get("cmd") == "CHANGE_PORT":
                esp.disconnect()
                is_connected = False
                esp.port = msg.get("value")
                conn.send({"type": "connection_status", "status": "disconnected"})
        try:
            if is_connected and esp.esp and esp.esp.in_waiting > 0:
                response = esp.get_response()
                print(f"Received from ESP: {response}")
                if response:
                    conn.send({"type": "esp_msg", "value": response})
                """
                if response.startswith("STATS,"):
                    parts = response.split(",")
                    if len(parts) == 4:
                        lmb = int(parts[1])
                        rmb = int(parts[2])
                        distance_m = float(parts[3]) / 100.0  # cm -> m
                        conn.send({"type": "stat_update", "data": {"lmb": lmb, "rmb": rmb, "dist": distance_m}})
                elif response:
                    conn.send({"type": "esp_msg", "value": response})
                    """
        except Exception as e:
            print(f"<System> USB connection error: {e}")
            esp.disconnect()
            is_connected = False
            conn.send({"type": "connection_status", "status": "disconnected"})

        keys = keyboard.get_key()
        current_time = time.time()

        # Detect key releases (key was pressed before, but not anymore)
        current_keys_set = set(keys) if keys else set()
        released_keys = pressed_keys_set - current_keys_set

        # Count each released key as one key press
        if released_keys:
            num_released = len(released_keys)
            conn.send({"type": "stat_increment", "key": "keys", "amount": num_released})

        pressed_keys_set = current_keys_set

        if keys != last_keys or (keys and current_time - last_send_time > 0.1):
            conn.send({"type": "keyboard", "keys": keys if keys else ""})
            last_keys = keys
            last_send_time = current_time
        time.sleep(0.01)


class KeyboardInputModule:
    """
    Keyboard input listener using pynput library.

    Tracks specific keys for device control and an emergency stop key.
    Runs a background listener thread to capture key events.
    """

    def __init__(self, tracked_keys=None, estop_key="p"):
        """
        Initialize keyboard listener.

        Args:
            tracked_keys: List of keys to monitor (default: movement and control keys)
            estop_key: Emergency stop key character (default: 'p')
        """
        self.tracked_keys = tracked_keys or [
            "i", # forward
            "j", # left
            "k", # backward
            "l", # right
            "v", # gripper
            "1", # lmb
            "2", # rmb
            "h", # homing
            "c", # center
            "u", # z-up
            "o", # z-down
            ']',  # calibration
            '/'  # testing
        ]
        self.estop_key = estop_key
        self.pressed_keys = set()
        self.listener = pynput_kb.Listener(
            on_press=self.on_press, on_release=self.on_release
        )
        self.listener.start()

    def on_press(self, key):
        """
        Handle key press event. Add to pressed_keys set if tracked or estop.

        Args:
            key: pynput Key object from listener
        """
        try:
            char = key.char.lower()
            if char in self.tracked_keys or char == self.estop_key:
                self.pressed_keys.add(char)
        except AttributeError:
            pass

    def on_release(self, key):
        """
        Handle key release event. Remove from pressed_keys set.

        Args:
            key: pynput Key object from listener
        """
        try:
            char = key.char.lower()
            if char in self.pressed_keys:
                self.pressed_keys.remove(char)
        except AttributeError:
            pass

    def get_key(self):
        """
        Get current keyboard state.

        Returns:
            Emergency stop key if pressed, otherwise string of all active tracked keys
        """
        if self.estop_key in self.pressed_keys:
            return self.estop_key
        result = ""
        for k in self.tracked_keys:
            if k in self.pressed_keys:
                result += k
        return result


if __name__ == "__main__":
    print(
        "This module is not meant to be run directly. Please run the main application instead."
    )
