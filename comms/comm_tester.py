import time
import math
from comms import CommsModule  # Importujemy naszą klasę z poprzedniego kroku


def run_30hz_stream():
    esp = CommsModule()  # Zmień na swój port
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
    except KeyboardInterrupt:
        print("\nPrzerwano pętlę przez użytkownika.")
    finally:
        esp.disconnect()


if __name__ == "__main__":
    run_30hz_stream()