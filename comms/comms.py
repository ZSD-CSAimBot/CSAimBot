import serial
import socket
import platform
import threading


class SerialCommsModule:
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


class TCPCommsModule:
    # Constructor
    def __init__(self, host="127.0.0.1", port=5000, timeout=2):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None

    # Try to connect with TCP server
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            print(f"Connected to {self.host}:{self.port}.")
            return True
        except socket.error as e:
            print(f"Connection error {self.host}:{self.port}\n{e}")
            self.socket = None
            return False

    # Encodes command and sends it to server
    def send_command(self, command):
        if self.socket:
            try:
                text_to_send = f"{command}\r\n".encode('utf-8')
                self.socket.sendall(text_to_send)
                print(f"Sent: {command}")
            except socket.error as e:
                print(f"Send error: {e}")
        else:
            print("Socket not connected.")

    # Tries to read response from server
    def get_response(self):
        if self.socket:
            try:
                response = self.socket.recv(1024).decode('utf-8', errors='ignore').strip()
                if response:
                    return response
                return None
            except socket.timeout:
                print("Socket timeout.")
                return None
            except socket.error as e:
                print(f"Receive error: {e}")
                return None
        else:
            print("Socket not connected.")
            return None

    # Closes the socket if it's open
    def disconnect(self):
        if self.socket:
            try:
                self.socket.close()
                print("Socket closed.")
            except socket.error as e:
                print(f"Error closing socket: {e}")
            finally:
                self.socket = None
        else:
            print("Socket already closed or not opened.")


class TCPServer:
    #on_received_message is a callback function that takes a message as input
    #it has to be written in code that will use this module (or not)
    def __init__(self, host="127.0.0.1", port=5000, on_received_message=None):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.on_received_message = on_received_message

    def start(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            print(f"TCP Server started on {self.host}:{self.port}")

            # Accept connections in a separate thread
            server_thread = threading.Thread(target=self.accept_connection, daemon=True)
            server_thread.start()
        except socket.error as e:
            print(f"Error starting server: {e}")
            self.running = False

    def accept_connection(self):
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                print(f"Client connected: {client_address}")

                # Handle client in a separate thread
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
            except socket.error as e:
                if self.running:
                    print(f"Error accepting connection: {e}")
                break

    def handle_client(self, client_socket, client_address):
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                message = data.decode('utf-8', errors='ignore').strip()
                print(f"[{client_address}] Received: {message}")

                if self.on_received_message:
                    response = self.on_received_message(message)
                    if response:
                        client_socket.sendall(response.encode('utf-8'))
                else:
                    # Echo back the message
                    response = f"Echo: {message}\r\n"
                    client_socket.sendall(response.encode('utf-8'))
                    print(f"[{client_address}] Sent: {response.strip()}")

        except socket.error as e:
            print(f"Error handling client {client_address}: {e}")
        finally:
            client_socket.close()
            print(f"Client disconnected: {client_address}")

    def stop(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
                print("TCP Server stopped.")
            except socket.error as e:
                print(f"Error stopping server: {e}")


if __name__ == "__main__":
    print("Don't run me!")
