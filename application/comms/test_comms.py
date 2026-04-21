import pytest
from unittest.mock import MagicMock, patch, call
from comms import SerialCommsModule, TCPCommsModule, TCPServer, KeyboardInputModule
import serial


class TestSerialCommsModule:

    @patch("comms.serial.Serial")
    def test_connect_success(self, mock_serial):
        module = SerialCommsModule(port="COM3")
        result = module.connect()

        assert result is True
        mock_serial.assert_called_once_with(port="COM3", baudrate=115200, timeout=2)

    @patch("comms.serial.Serial", side_effect=serial.SerialException("Port busy"))
    def test_connect_failure(self, mock_serial):
        module = SerialCommsModule(port="COM3")
        result = module.connect()

        assert result is False

    @patch("comms.serial.Serial")
    def test_send_command(self, mock_serial):
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
        mock_instance = MagicMock()
        mock_instance.is_open = False
        mock_serial.return_value = mock_instance

        module = SerialCommsModule()
        module.connect()
        module.send_command("FORWARD")  # Nie powinno rzucić wyjątku

        mock_instance.write.assert_not_called()

    @patch("comms.serial.Serial")
    def test_get_response(self, mock_serial):
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
        mock_instance = MagicMock()
        mock_instance.is_open = True
        mock_serial.return_value = mock_instance

        module = SerialCommsModule()
        module.connect()
        module.disconnect()

        mock_instance.close.assert_called_once()

    def test_default_port_linux(self):
        with patch("comms.platform.system", return_value="Linux"):
            module = SerialCommsModule()
            assert module.port == "/dev/ttyUSB0"

    def test_default_port_windows(self):
        with patch("comms.platform.system", return_value="Windows"):
            module = SerialCommsModule()
            assert module.port == "COM3"

class TestTCPCommsModule:

    @patch("comms.socket.socket")
    def test_connect_success(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        module = TCPCommsModule(host="127.0.0.1", port=5000)
        result = module.connect()

        assert result is True
        mock_sock.connect.assert_called_once_with(("127.0.0.1", 5000))

    @patch("comms.socket.socket")
    def test_connect_failure(self, mock_socket_class):
        import socket
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = socket.error("Connection refused")
        mock_socket_class.return_value = mock_sock

        module = TCPCommsModule()
        result = module.connect()

        assert result is False
        assert module.socket is None

    @patch("comms.socket.socket")
    def test_send_command(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        module = TCPCommsModule()
        module.connect()
        module.send_command("STOP")

        mock_sock.sendall.assert_called_once_with(b"STOP\r\n")

    @patch("comms.socket.socket")
    def test_get_response(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b"ACK\r\n"
        mock_socket_class.return_value = mock_sock

        module = TCPCommsModule()
        module.connect()
        response = module.get_response()

        assert response == "ACK"

    @patch("comms.socket.socket")
    def test_get_response_timeout(self, mock_socket_class):
        import socket
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = socket.timeout()
        mock_socket_class.return_value = mock_sock

        module = TCPCommsModule()
        module.connect()
        response = module.get_response()

        assert response is None

    @patch("comms.socket.socket")
    def test_disconnect(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        module = TCPCommsModule()
        module.connect()
        module.disconnect()

        mock_sock.close.assert_called_once()
        assert module.socket is None

class TestTCPServer:

    @patch("comms.socket.socket")
    @patch("comms.threading.Thread")
    def test_start(self, mock_thread, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        server = TCPServer(host="127.0.0.1", port=5000)
        server.start()

        mock_sock.bind.assert_called_once_with(("127.0.0.1", 5000))
        mock_sock.listen.assert_called_once_with(5)
        assert server.running is True
        mock_thread.assert_called_once()

    @patch("comms.socket.socket")
    def test_stop(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        server = TCPServer()
        server.server_socket = mock_sock
        server.running = True
        server.stop()

        assert server.running is False
        mock_sock.close.assert_called_once()

    def test_handle_client_with_callback(self):
        callback = MagicMock(return_value="RESPONSE\r\n")
        server = TCPServer(on_received_message=callback)
        server.running = True

        mock_client = MagicMock()
        # Pierwsza iteracja zwraca dane, druga kończy pętlę
        mock_client.recv.side_effect = [b"HELLO", b""]

        server.handle_client(mock_client, ("127.0.0.1", 1234))

        callback.assert_called_once_with("HELLO")
        mock_client.sendall.assert_called_once_with(b"RESPONSE\r\n")

    def test_handle_client_echo(self):
        server = TCPServer()  # Brak callbacka – tryb echo
        server.running = True

        mock_client = MagicMock()
        mock_client.recv.side_effect = [b"PING", b""]

        server.handle_client(mock_client, ("127.0.0.1", 1234))

        mock_client.sendall.assert_called_once_with(b"Echo: PING\r\n")

class TestKeyboardInputModule:

    @patch("comms.keyboard.is_pressed")
    def test_estop_priority(self, mock_is_pressed):
        # E-stop ma absolutny priorytet
        mock_is_pressed.side_effect = lambda key: key == "p"

        module = KeyboardInputModule()
        result = module.get_key()

        assert result == "p"

    @patch("comms.keyboard.is_pressed")
    def test_single_key_pressed(self, mock_is_pressed):
        mock_is_pressed.side_effect = lambda key: key == "i"

        module = KeyboardInputModule()
        result = module.get_key()

        assert result == "i"

    @patch("comms.keyboard.is_pressed")
    def test_multiple_keys_pressed(self, mock_is_pressed):
        mock_is_pressed.side_effect = lambda key: key in ("i", "l")

        module = KeyboardInputModule()
        result = module.get_key()

        assert "i" in result
        assert "l" in result

    @patch("comms.keyboard.is_pressed")
    def test_no_keys_pressed(self, mock_is_pressed):
        mock_is_pressed.return_value = False

        module = KeyboardInputModule()
        result = module.get_key()

        assert result == ""

    @patch("comms.keyboard.is_pressed", side_effect=Exception("kbd error"))
    def test_keyboard_exception(self, mock_is_pressed):
        module = KeyboardInputModule()
        result = module.get_key()

        assert result == ""