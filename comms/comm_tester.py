import time
import math
from comms import SerialCommsModule, TCPCommsModule, TCPServer, KeyboardInputModule


def run_30hz_stream():
    esp = SerialCommsModule()  # Zmień na swój port
    if not esp.connect():
        return
    counter = 0
    try:
        while True:
            start_time = time.time()
            x = int(100 * math.cos(counter))
            y = int(100 * math.sin(counter))
            counter += 0.01
            command = f"{x},{y}"
            if esp.esp and esp.esp.is_open:
                esp.esp.write(f"{command}\r".encode('utf-8'))
            response = esp.get_response()
            if response:
                print(f"ESP zglasza: {response}")
            exe_time = time.time() - start_time
            time.sleep(max(0.0, (1.0 / 30.0) - exe_time))
    finally:
        esp.disconnect()


def test_tcp_single_command():
    server = TCPServer(host="127.0.0.1", port=5000)
    server.start()
    time.sleep(0.5)

    comms = TCPCommsModule(host="127.0.0.1", port=5000)
    if comms.connect():
        comms.send_command("Hello from client")
        response = comms.get_response()
        if response:
            print(f"\nResponse: {response}")
        comms.disconnect()
    server.stop()


def test_tcp_stream():
    server = TCPServer(host="127.0.0.1", port=5000)
    server.start()
    time.sleep(0.5)  # Wait for server to start
    comms = TCPCommsModule(host="127.0.0.1", port=5000)
    if comms.connect():
        counter = 0
        try:
            for i in range(30):  # Send 30 commands at 30Hz
                start_time = time.time()
                x = int(100 * math.cos(counter))
                y = int(100 * math.sin(counter))
                counter += 0.01
                command = f"{x},{y}"
                
                comms.send_command(command)
                response = comms.get_response()
                if response:
                    print(f"[{i}] Response: {response}")
                
                exe_time = time.time() - start_time
                time.sleep(max(0.0, (1.0 / 30.0) - exe_time))
        finally:
            comms.disconnect()
    server.stop()

def test_tcp_multiple_connections():
    server = TCPServer(host="127.0.0.1", port=5000)
    server.start()
    time.sleep(0.5)
    clients = []

    # Create 3 clients
    for i in range(3):
        client = TCPCommsModule(host="127.0.0.1", port=5000)
        if client.connect():
            clients.append(client)

    # Send commands from each client
    for i, client in enumerate(clients):
        client.send_command(f"Message from client {i+1}")
        response = client.get_response()
        if response:
            print(f"Client {i+1} received: {response}")
    
    # Disconnect all
    for client in clients:
        client.disconnect()
    
    server.stop()


def test_keyboard_only():
    # Initialize the keyboard module with default settings
    keyboard_input = KeyboardInputModule()

    print("\n--- KEYBOARD MODULE TEST ---")
    print(f"Tracked keys: {keyboard_input.tracked_keys} | E-STOP: '{keyboard_input.estop_key}'\n")

    while True:
        start_time = time.time()

        # Read the current state of tracked keys
        current_keys = keyboard_input.get_key()
        print(f"Current input: '{current_keys}'")

        # Exit the loop immediately if the emergency stop key is pressed
        if current_keys == keyboard_input.estop_key:
            print("\n!!! E-STOP TRIGGERED !!!")
            break

        # Maintain loop frequency at approximately 30Hz
        exe_time = time.time() - start_time
        time.sleep(max(0.0, (1.0 / 30.0) - exe_time))

if __name__ == "__main__":
    #test_tcp_stream()
    test_keyboard_only()
