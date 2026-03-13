import serial
import platform


class CommsModule:
    # Constructor
    def __init__(self, port=None, baud_rate=115200, timeout=2):
        # Set default port based on OS
        if port is None:
            if platform.system() == "Windows":
                port = "COM3"
            else:  # Linux
                port = "/dev/ttyUSB0"
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.esp = None

    # Try to connect with esp
    def connect(self):
        try:
            self.esp = serial.Serial(port=self.port, baudrate=self.baud_rate, timeout=self.timeout)
            print(f"Connected on {self.port}.")
            #time.sleep(2)
            return True
        except serial.SerialException as e:
            print(f"Connection error {self.port}\n{e}")
            return False

    # Encodes command and sends it to esp
    def send_command(self, command):
        if self.esp and self.esp.is_open:
            text_to_send = f"{command}\r".encode('utf-8')
            self.esp.write(text_to_send)
            print(f"Sent: {command}")
        else:
            print("Port closed. Unable to send command.")

    # Tries to read response from esp, returns None if no response
    def get_response(self):
        if self.esp and self.esp.is_open:
            response = self.esp.readline().decode('utf-8', errors='ignore').strip()
            if response:
                return response
            return None
        else:
            print("Port closed. Unable to read response.")
            return None

    # Closes the port if it's open
    def disconnect(self):
        if self.esp and self.esp.is_open:
            self.esp.close()
            print("Port closed successfully.")
        else:
            print("Port already closed or not yet opened.")


if __name__ == "__main__":
    print("Dont run me!")
