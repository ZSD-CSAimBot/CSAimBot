"""
Unit tests for communications module.

Tests cover serial communication functionality (connection, command sending, response reading),
keyboard input handling, and system performance benchmarking.
"""

import os
import time
import sys
from unittest.mock import MagicMock, patch
from comms import SerialCommsModule, KeyboardInputModule
import serial


class TestSerialCommsModule:
    """
    Unit tests for SerialCommsModule class.
    
    Covers connection handling, command sending, response reading, and disconnection.
    """
    @patch("comms.serial.Serial")
    def test_connect_success(self, mock_serial):
        """Test successful ESP32 connection."""
        module = SerialCommsModule(port="COM3")
        result = module.connect()
        assert result is True
        mock_serial.assert_called_once_with(port="COM3", baudrate=115200, timeout=2)

    @patch("comms.serial.Serial", side_effect=serial.SerialException("Port busy"))
    def test_connect_failure(self):
        """Test connection failure handling."""
        module = SerialCommsModule(port="COM3")
        result = module.connect()
        assert result is False

    @patch("comms.serial.Serial")
    def test_send_command(self, mock_serial):
        """Test command transmission to ESP32."""
        mock_instance = MagicMock()
        mock_instance.is_open = True
        mock_serial.return_value = mock_instance

        module = SerialCommsModule()
        module.connect()
        module.send_command("FORWARD")

        mock_instance.write.assert_called_once_with(b"FORWARD\r")
        mock_instance.flush.assert_called_once()

    @patch("comms.serial.Serial")
    def test_send_command_port_closed(self, mock_serial):
        """Test send_command behavior when port is closed."""
        mock_instance = MagicMock()
        mock_instance.is_open = False
        mock_serial.return_value = mock_instance

        module = SerialCommsModule()
        module.connect()
        module.send_command("FORWARD")

        mock_instance.write.assert_not_called()

    @patch("comms.serial.Serial")
    def test_get_response(self, mock_serial):
        """Test successful response reception from ESP32."""
        mock_instance = MagicMock()
        mock_instance.is_open = True
        mock_instance.readline.return_value = b"OK\r\n"
        mock_serial.return_value = mock_instance

        module = SerialCommsModule()
        module.connect()
        response = module.get_response()

        assert response == "OK"

    @patch("comms.serial.Serial")
    def test_get_response_empty(self, mock_serial):
        """Test handling of empty response from serial buffer."""
        mock_instance = MagicMock()
        mock_instance.is_open = True
        mock_instance.readline.return_value = b""
        mock_serial.return_value = mock_instance

        module = SerialCommsModule()
        module.connect()
        response = module.get_response()

        assert response is None

    @patch("comms.serial.Serial")
    def test_disconnect(self, mock_serial):
        """Test port disconnection."""
        mock_instance = MagicMock()
        mock_instance.is_open = True
        mock_serial.return_value = mock_instance

        module = SerialCommsModule()
        module.connect()
        module.disconnect()

        mock_instance.close.assert_called_once()

    def test_default_port_linux(self):
        """Test default port assignment for Linux platform."""
        with patch("comms.platform.system", return_value="Linux"):
            module = SerialCommsModule()
            assert module.port == "/dev/ttyUSB0"

    def test_default_port_windows(self):
        """Test default port assignment for Windows platform."""
        with patch("comms.platform.system", return_value="Windows"):
            module = SerialCommsModule()
            assert module.port == "COM3"


class TestKeyboardInputModule:
    """
    Unit tests for KeyboardInputModule class.
    
    Verifies key detection, E-stop prioritization, and exception handling.
    """
    @patch("comms.keyboard.is_pressed")
    def test_estop_priority(self, mock_is_pressed):
        """Test emergency stop key takes priority over other inputs."""
        mock_is_pressed.side_effect = lambda key: key == "p"

        module = KeyboardInputModule()
        result = module.get_key()

        assert result == "p"

    @patch("comms.keyboard.is_pressed")
    def test_single_key_pressed(self, mock_is_pressed):
        """Test detection of single key press."""
        mock_is_pressed.side_effect = lambda key: key == "i"

        module = KeyboardInputModule()
        result = module.get_key()

        assert result == "i"

    @patch("comms.keyboard.is_pressed")
    def test_multiple_keys_pressed(self, mock_is_pressed):
        """Test detection of simultaneous key presses."""
        mock_is_pressed.side_effect = lambda key: key in ("i", "l")

        module = KeyboardInputModule()
        result = module.get_key()

        assert "i" in result
        assert "l" in result

    @patch("comms.keyboard.is_pressed")
    def test_no_keys_pressed(self, mock_is_pressed):
        """Test behavior when no keys are pressed."""
        mock_is_pressed.return_value = False

        module = KeyboardInputModule()
        result = module.get_key()

        assert result == ""

    @patch("comms.keyboard.is_pressed", side_effect=Exception("kbd error"))
    def test_keyboard_exception(self, mock_is_pressed):
        """Test exception handling in keyboard module."""
        module = KeyboardInputModule()
        result = module.get_key()

        assert result == ""

def run_benchmark():
    """
    Benchmark serial communication performance.
    
    Sends repeated commands to ESP32 and measures response times and packet loss.
    Verifies latency and transmission stability meet specifications.
    """
    esp = SerialCommsModule()

    if not esp.connect():
        print("Failed to establish connection. Aborting test.")
        return

    print("Waiting 2 seconds for ESP32 to initialize...")
    time.sleep(2)

    if esp.esp.in_waiting > 0:
        esp.esp.read(esp.esp.in_waiting)

    iterations = 10000
    lost_packets = 0
    latencies = []

    print(f"Starting benchmark with {iterations} iterations. This may take a few moments...")
    print("ATTENTION: For the next few seconds, the console will be muted to avoid delaying the test.\nPlease wait...")

    # Saving original stdout and redirecting to null to prevent console output during the benchmark
    original_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')

    for i in range(iterations):
        payload = f"{i},{i},75,ij"  # Added 75 as a dummy value for testing purposes

        start_time = time.perf_counter()
        esp.send_command(payload)
        response = esp.get_response()
        end_time = time.perf_counter()

        if response is None or not response.startswith("Understood"):
            lost_packets += 1
        else:
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

    # Recovering original stdout after the benchmark
    sys.stdout.close()
    sys.stdout = original_stdout

    esp.disconnect()

    # Calculating latency statistics
    if len(latencies) > 0:
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)
    else:
        avg_latency = max_latency = min_latency = 0

    packet_loss_pct = (lost_packets / iterations) * 100

    # Speed from PC to ESP is theoretically half of the total response time (RTT / 2)
    one_way_latency = avg_latency / 2

    # Checking if the results meet the specified requirements
    latency_passed = one_way_latency < 5.0
    loss_passed = packet_loss_pct < 0.5

    print("\n" + "=" * 40)
    print("           BENCHMARK RAPORT")
    print("=" * 40)

    print("\n[ Round-Trip Time ]")
    print(f"  • Average time of whole loop: {avg_latency:.2f} ms")
    print(f"  • Fastest response:    {min_latency:.2f} ms")
    print(f"  • Slowest response: {max_latency:.2f} ms")

    print("\n[ Stability of Transmission ]")
    print(f"  • Number of lost packets:  {lost_packets} out of {iterations}")
    print(f"  • Loss percentage:           {packet_loss_pct:.3f}%")

    print("\n" + "=" * 40)
    print("         VERIFICATION OF REQUIREMENTS")
    print("=" * 40)

    print(f"1. Latency on the PC -> ESP line < 5 ms: ")
    print(f"   Estimated based on average: {one_way_latency:.2f} ms")
    print(f"   Status: {'PASSED' if latency_passed else 'FAILED'}")

    print(f"\n2. Lost packets at the level of ~0%: ")
    print(f"   Recorded: {packet_loss_pct:.3f}%")
    print(f"   Status: {'PASSED' if loss_passed else 'FAILED'}")
    print("=" * 40)
    