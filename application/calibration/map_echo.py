import socket


class CSGOTelemetry:
    def __init__(self, ip="127.0.0.1", port=5000, mouse_distance_inches=4.8228346, callback=None):
        # config
        self.ip = ip
        self.port = port
        self.callback = callback

        #math config
        self.mouse_distance_inches = mouse_distance_inches
        self.base_yaw = 0.022

        self.first_shot_yaw = None

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.ip, self.port))

    def _calculate_delta(self, yaw1, yaw2):
        """Calculating angle difference between two values"""
        delta = abs(yaw2 - yaw1)
        if delta > 180.0:
            delta = 360.0 - delta
        return delta

    def _calculate_edpi(self, delta_yaw):
        """Calculating eDPI value based on distance traveled"""
        if self.mouse_distance_inches <= 0:
            return 0.0
        return delta_yaw / (self.mouse_distance_inches * self.base_yaw)

    def start_listening(self):
        print(f"Calibration on port: {self.port}.")
        print("Step 1: Fire the first shot")
        print(f"Step 2: Fire the second shot (after moving {self.mouse_distance_inches})\n")

        while True:
            data, _ = self.sock.recvfrom(1024)
            msg = data.decode('utf-8').strip('\x00')
            parts = msg.split(';')

            if parts[0] == "IMPACT":
                player = parts[1]
                yaw = float(parts[6])

                if self.first_shot_yaw is None:
                    self.first_shot_yaw = yaw
                    print(f"[{player}] First shot fired. (Yaw: {yaw:.2f}). Waiting for the second shot")
                    if self.callback:
                        self.callback("First shot recorded. Waiting for second...")
                else:
                    delta = self._calculate_delta(self.first_shot_yaw, yaw)
                    edpi = self._calculate_edpi(delta)

                    print(f"[{player}] Second shot fired. (Yaw: {yaw:.2f}).")
                    print("-" * 40)
                    print(f"Calculation results:")
                    print(f"-> Mouse movement: {self.mouse_distance_inches} inches")
                    print(f"-> Delta yaw: {delta:.2f} degree")
                    print(f"eDPI: {edpi:.0f}")
                    print("-" * 40 + "\n")

                    if self.callback:
                        self.callback(f"Finished! eDPI: {edpi:.0f} (Delta: {delta:.2f} deg)")
                    self.first_shot_yaw = None
                    return edpi


if __name__ == "__main__":
    print("Do not run this file directly.")