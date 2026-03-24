import math
import time

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
            esp.send_command(command)
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
        client.send_command(f"Message from client {i + 1}")
        response = client.get_response()
        if response:
            print(f"Client {i + 1} received: {response}")

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
        if current_keys != "":
            print(f"Current input: '{current_keys}'")

        # Exit the loop immediately if the emergency stop key is pressed
        if current_keys == keyboard_input.estop_key:
            print("\n!!! E-STOP TRIGGERED !!!")
            break

        # Maintain loop frequency at approximately 30Hz
        exe_time = time.time() - start_time
        time.sleep(max(0.0, (1.0 / 30.0) - exe_time))


def test_keyboard_to_esp():
    keyboard_input = KeyboardInputModule()
    esp = SerialCommsModule()
    if not esp.connect():
        return

    print("\n--- KEYBOARD TO ESP TEST ---")
    print("Sending: x,y,keys | Press 'p' to E-STOP\n")
    print(f"{'Iteration':<10} {'Sent Command':<20} {'ESP Response':<50}")

    try:
        iteration = 0
        while True:
            iteration += 1
            start_time = time.time()

            x = int(100 * math.cos(start_time))
            y = int(100 * math.sin(start_time))
            keys = keyboard_input.get_key()
            command = f"{x},{y},{keys}"

            esp.send_command(command)
            time.sleep(0.01)

            response = esp.get_response()

            print(f"{iteration:<10} {command:<20} {response:<50}")

            if keys == keyboard_input.estop_key:
                print("\n!!! E-STOP TRIGGERED !!!")
                break

            exe_time = time.time() - start_time
            time.sleep(max(0.0, (1.0 / 30.0) - exe_time))
    finally:
        esp.disconnect()


if __name__ == "__main__":
    # test_tcp_stream()
    # test_keyboard_only()
    test_keyboard_to_esp()
    # test_keyboard_to_esp()
