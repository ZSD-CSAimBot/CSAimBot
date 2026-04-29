import platform
import socket
import threading
import time
#import keyboard
from pynput import keyboard as pynput_kb
import serial
import sys
import os


class SerialCommsModule:
    # Constructor
    def __init__(self, port=None, baud_rate=115200, timeout=2):
        #Set default port based on OS if not provided
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

    # Try to connect with esp
    def connect(self):
        try:
            self.esp = serial.Serial(port=self.port, baudrate=self.baud_rate, timeout=self.timeout)
            print(f"Connected on {self.port}.")
            # time.sleep(2)
            return True
        except serial.SerialException as e:
            print(f"Connection error {self.port}\n{e}")
            return False

    # Encodes command and sends it to esp
    def send_command(self, command):
        if self.esp and self.esp.is_open:
            # Flush input buffer to remove old data
            self.esp.reset_input_buffer()
            text_to_send = f"{command}\r".encode('utf-8')
            self.esp.write(text_to_send)
            self.esp.flush()  # Wait until all data is sent
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


def comms_worker(conn):
    esp = SerialCommsModule()
    keyboard = KeyboardInputModule()
    last_keys = None
    last_send_time = None

    is_connected = False # Ustawiamy na False na start

    running = True
    while running:
        # 1. Nasłuchiwanie komend z GUI
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

        # 2. ODCZYT Z ESP32
        # Używamy esp.esp.in_waiting, aby sprawdzić, czy są dane bez blokowania pętli
                # 2. ODCZYT Z ESP32
                try:
                    # Używamy esp.esp.in_waiting, aby sprawdzić, czy są dane bez blokowania pętli
                    if is_connected and esp.esp and esp.esp.in_waiting > 0:
                        response = esp.get_response()
                        if response:
                            # Odsyłamy wiadomość do GUI do wyświetlenia w logach
                            conn.send({"type": "esp_msg", "value": response})
                except Exception as e:
                    # Przechwytujemy zerwanie portu przez zakłócenia EMI z solenoidu
                    print(f"<System> Zerwano połączenie USB (skok napięcia/EMI?): {e}")
                    esp.disconnect()
                    is_connected = False
                    conn.send({"type": "connection_status", "status": "disconnected"})

        # 3. Wysyłanie stanu klawiatury do GUI
        keys = keyboard.get_key()
        current_time = time.time()
        if keys != last_keys or (keys and current_time - last_send_time > 0.1):
            conn.send({"type": "keyboard", "keys": keys if keys else ""})
            last_keys = keys
            last_send_time = current_time
        time.sleep(0.01)


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
    # on_received_message is a callback function that takes a message as input
    # it has to be written in code that will use this module (or not)
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


class KeyboardInputModule:
    def __init__(self, tracked_keys=None, estop_key="p"):
        # DODANO 'h' DO LISTY
        self.tracked_keys = tracked_keys or ['i', 'j', 'k', 'l', 'z', 'x', 'v', '1', '2', 'h']
        self.estop_key = estop_key
        self.pressed_keys = set()

        # Uruchomienie bezpiecznego nasłuchiwania w tle (pynput)
        self.listener = pynput_kb.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )
        self.listener.start()

    def on_press(self, key):
        try:
            char = key.char.lower()
            if char in self.tracked_keys or char == self.estop_key:
                self.pressed_keys.add(char)
        except AttributeError:
            # Ignoruj klawisze funkcyjne (shift, ctrl, alt)
            pass

    def on_release(self, key):
        try:
            char = key.char.lower()
            if char in self.pressed_keys:
                self.pressed_keys.remove(char)
        except AttributeError:
            pass

    def get_key(self):
        # E-stop zawsze ma najwyższy priorytet
        if self.estop_key in self.pressed_keys:
            return self.estop_key

        # Zwróć wszystkie wciśnięte klawisze w formie stringa (np. "ij")
        result = ""
        for k in self.tracked_keys:
            if k in self.pressed_keys:
                result += k
        return result


def run_benchmark():
    esp = SerialCommsModule()

    if not esp.connect():
        print("Nie można nawiązać połączenia. Przerwanie testu.")
        return

    print("Czekam 2 sekundy na inicjalizację mikrokontrolera...")
    time.sleep(2)

    if esp.esp.in_waiting > 0:
        esp.esp.read(esp.esp.in_waiting)

    iterations = 10000
    lost_packets = 0
    latencies = []

    print(f"\nRozpoczynam test pingu ({iterations} iteracji).")
    print("UWAGA: Przez najbliższe kilka sekund konsola będzie wyciszona, aby nie opóźniać testu.\nCzekaj...")

    # Zapisanie oryginalnego wyjścia (stdout) i przekierowanie go do "kosza", żeby printy nie psuły pingu
    original_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')

    for i in range(iterations):
        # Było: payload = f"{i},{i},ij"
        payload = f"{i},{i},75,ij"  # Dodane statyczne 75 dla testu

        # Mierzymy czas w nanosekundach dla maksymalnej precyzji
        start_time = time.perf_counter()

        esp.send_command(payload)
        response = esp.get_response()

        end_time = time.perf_counter()

        # Weryfikacja: Twoje ESP powinno odesłać "Zrozumialem X: ... Y: ... Keys: ..."
        if response is None or not response.startswith("Zrozumialem"):
            lost_packets += 1
        else:
            # Obliczamy Round-Trip Time (RTT) w milisekundach
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

    # Przywrócenie standardowego wyświetlania w konsoli
    sys.stdout.close()
    sys.stdout = original_stdout

    esp.disconnect()

    # --- ANALIZA WYNIKÓW ---
    if len(latencies) > 0:
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)
    else:
        avg_latency = max_latency = min_latency = 0

    packet_loss_pct = (lost_packets / iterations) * 100

    # Prędkość z komputera do ESP to w teorii połowa całkowitego czasu odpowiedzi (RTT / 2)
    one_way_latency = avg_latency / 2

    # Sprawdzenie, czy parametry zdają test
    latency_passed = one_way_latency < 5.0
    loss_passed = packet_loss_pct < 0.5  # Próg tolerancji dla ułamków promila (zgubienie paru na 10000 jest akceptowalne)

    print("\n" + "=" * 40)
    print("           RAPORT Z BENCHMARKU")
    print("=" * 40)

    print("\n[ Czas reakcji (Round-Trip Time) ]")
    print(f"  • Średni czas całej pętli: {avg_latency:.2f} ms")
    print(f"  • Najszybsza odpowiedź:    {min_latency:.2f} ms")
    print(f"  • Najwolniejsza odpowiedź: {max_latency:.2f} ms")

    print("\n[ Stabilność transmisji ]")
    print(f"  • Ilość zgubionych ramek:  {lost_packets} z {iterations}")
    print(f"  • Procent strat:           {packet_loss_pct:.3f}%")

    print("\n" + "=" * 40)
    print("         WERYFIKACJA WYMAGAŃ")
    print("=" * 40)

    print(f"1. Opóźnienie na linii PC -> ESP < 5 ms: ")
    print(f"   Szacowane na podstawie średniej: {one_way_latency:.2f} ms")
    print(f"   Status: {'ZALICZONE' if latency_passed else 'NIEZALICZONE'}")

    print(f"\n2. Zgubione ramki na poziomie ~0%: ")
    print(f"   Odnotowano: {packet_loss_pct:.3f}%")
    print(f"   Status: {'ZALICZONE' if loss_passed else 'NIEZALICZONE'}")
    print("=" * 40)


if __name__ == "__main__":
    run_benchmark()