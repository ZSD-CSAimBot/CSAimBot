import pytest
import sys
import numpy as np
from unittest.mock import MagicMock, patch

import torch
import cv2
import camera
import detection_system


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def mock_bettercam():
    """Mocks the bettercam library for Windows."""
    mock = MagicMock()
    mock.create.return_value = MagicMock()
    with patch.dict("sys.modules", {"bettercam": mock}):
        yield mock


@pytest.fixture
def windows_provider(mock_bettercam):
    """Provides a CameraProvider in a mocked Windows environment."""
    # The 'camera' module is already cleanly imported at the top of the file.
    # Here we temporarily mock the platform during object creation.
    with patch("camera.sys.platform", "win32"):
        provider = camera.CameraProvider(region=(320, 172, 1600, 908))
        yield provider


@pytest.fixture
def mock_mss():
    """Mocks the mss library for Linux."""
    mock = MagicMock()
    mock.mss.return_value = MagicMock()
    with patch.dict("sys.modules", {"mss": mock}):
        yield mock


@pytest.fixture
def linux_provider(mock_mss):
    """Provides a CameraProvider in a mocked Linux environment."""
    with patch("camera.sys.platform", "linux"):
        provider = camera.CameraProvider(region=(320, 172, 1600, 908))
        yield provider


@pytest.fixture
def aimbot():
    """Provides an AimBot instance with mocked camera, YOLO, and PyTorch."""
    mock_camera = MagicMock()
    mock_yolo_class = MagicMock()
    mock_model_instance = MagicMock()
    mock_yolo_class.return_value = mock_model_instance

    fake_tensor = MagicMock()
    fake_tensor.__truediv__ = MagicMock(return_value=fake_tensor)
    fake_tensor.div_ = MagicMock(return_value=fake_tensor)

    with patch("detection_system.CameraProvider", return_value=mock_camera), \
            patch("detection_system.YOLO", mock_yolo_class), \
            patch("detection_system.torch.zeros", return_value=fake_tensor), \
            patch("detection_system.torch.empty", return_value=fake_tensor):
        bot = detection_system.AimBot("fake_model.engine")
        yield bot


@pytest.fixture
def gui_app():
    """Provides a mocked GUI based on DearPyGui."""
    mock_dpg = MagicMock()
    mock_dpg.window.return_value.__enter__ = MagicMock(return_value=None)
    mock_dpg.window.return_value.__exit__ = MagicMock(return_value=False)
    mock_dpg.group.return_value.__enter__ = MagicMock(return_value=None)
    mock_dpg.group.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"dearpygui": MagicMock(), "dearpygui.dearpygui": mock_dpg}):
        from gui import GUI
        pipe = MagicMock()
        app = GUI(pipe)
        yield app


# ==============================================================================
# CAMERA PROVIDER TESTS
# ==============================================================================

class TestCameraProviderWindows:

    def test_init_creates_bettercam_with_correct_args(self, mock_bettercam, windows_provider):
        mock_bettercam.create.assert_called_once_with(
            output_color="BGRA", region=(320, 172, 1600, 908), nvidia_gpu=True
        )

    def test_init_stores_region(self, windows_provider):
        assert windows_provider.region == (320, 172, 1600, 908)

    @patch("camera.torch.from_dlpack")
    def test_grab_gpu_tensor_returns_tensor_when_frame_available(self, mock_dlpack, windows_provider):
        fake_frame = MagicMock()
        fake_tensor = MagicMock()
        mock_dlpack.return_value = fake_tensor
        windows_provider.camera.grab.return_value = fake_frame

        result = windows_provider.grab_gpu_tensor()

        assert result is fake_tensor
        mock_dlpack.assert_called_once_with(fake_frame)

    def test_grab_gpu_tensor_returns_none_when_no_frame(self, windows_provider):
        windows_provider.camera.grab.return_value = None
        result = windows_provider.grab_gpu_tensor()
        assert result is None

    def test_release_calls_camera_release(self, windows_provider):
        windows_provider.release()
        windows_provider.camera.release.assert_called_once()


class TestCameraProviderLinux:

    def test_init_sets_monitor_dict(self, linux_provider):
        assert linux_provider.monitor == {
            "left": 320,
            "top": 172,
            "width": 1280,
            "height": 736
        }

    @patch("camera.np.array")
    @patch("camera.torch.from_numpy")
    def test_grab_gpu_tensor_returns_tensor_when_frame_available(self, mock_from_numpy, mock_np_array, linux_provider):
        fake_frame = MagicMock()
        fake_tensor = MagicMock()
        mock_from_numpy.return_value.to.return_value = fake_tensor
        linux_provider.camera.grab.return_value = fake_frame

        result = linux_provider.grab_gpu_tensor()

        assert result is fake_tensor

    def test_grab_gpu_tensor_returns_none_when_no_frame(self, linux_provider):
        linux_provider.camera.grab.return_value = None
        result = linux_provider.grab_gpu_tensor()
        assert result is None

    def test_release_calls_camera_close(self, linux_provider):
        linux_provider.release()
        linux_provider.camera.close.assert_called_once()


# ==============================================================================
# AIMBOT TESTS
# ==============================================================================

class TestAimBotInit:

    def test_fov_dimensions_set_correctly(self, aimbot):
        assert aimbot.FOV_WIDTH == 1280
        assert aimbot.FOV_HEIGHT == 736

    def test_region_calculated_correctly(self, aimbot):
        assert aimbot.REGION == (320, 172, 1600, 908)

    def test_show_debug_window_default_true(self, aimbot):
        assert aimbot.show_debug_window is True

    def test_model_warmed_up_on_init(self, aimbot):
        assert aimbot.model.called


class TestCaptureAndPreprocessFrame:

    def test_returns_true_when_frame_available(self, aimbot):
        fake_dl_tensor = MagicMock()
        fake_dl_tensor.cpu.return_value.numpy.return_value = np.zeros((736, 1280, 4))
        fake_dl_tensor.__getitem__ = MagicMock(return_value=MagicMock())
        aimbot.camera.grab_gpu_tensor.return_value = fake_dl_tensor

        result = aimbot.capture_and_preprocess_frame()

        assert result is True

    def test_returns_false_when_no_frame(self, aimbot):
        aimbot.camera.grab_gpu_tensor.return_value = None
        result = aimbot.capture_and_preprocess_frame()
        assert result is False

    def test_debug_frame_set_when_debug_on(self, aimbot):
        fake_np = np.zeros((736, 1280, 4), dtype=np.uint8)
        fake_dl_tensor = MagicMock()
        fake_dl_tensor.cpu.return_value.numpy.return_value = fake_np
        fake_dl_tensor.__getitem__ = MagicMock(return_value=MagicMock())

        aimbot.camera.grab_gpu_tensor.return_value = fake_dl_tensor
        aimbot.show_debug_window = True

        aimbot.capture_and_preprocess_frame()
        assert aimbot.debug_frame is not None

    def test_debug_frame_not_set_when_debug_off(self, aimbot):
        fake_dl_tensor = MagicMock()
        fake_dl_tensor.__getitem__ = MagicMock(return_value=MagicMock())

        aimbot.camera.grab_gpu_tensor.return_value = fake_dl_tensor
        aimbot.show_debug_window = False
        aimbot.debug_frame = None

        aimbot.capture_and_preprocess_frame()
        assert aimbot.debug_frame is None


class TestDisplayResults:

    def _make_results(self, boxes_xyxy=None):
        results = [MagicMock()]
        if boxes_xyxy is not None:
            results[0].boxes = MagicMock()
            results[0].boxes.xyxy.cpu.return_value.numpy.return_value = np.array(boxes_xyxy)
        else:
            results[0].boxes = None
        return results

    @patch("detection_system.cv2.imshow")
    @patch("detection_system.cv2.waitKey")
    @patch("detection_system.cv2.rectangle")
    def test_draws_boxes_when_debug_on(self, mock_rect, mock_waitkey, mock_imshow, aimbot):
        aimbot.show_debug_window = True
        aimbot.debug_frame = np.zeros((736, 1280, 4), dtype=np.uint8)
        results = self._make_results([[100, 100, 200, 200], [300, 300, 400, 400]])

        aimbot.display_results(results)

        assert mock_rect.call_count == 2
        mock_imshow.assert_called_once()
        mock_waitkey.assert_called_once_with(1)

    @patch("detection_system.cv2.imshow")
    def test_no_imshow_when_debug_off(self, mock_imshow, aimbot):
        aimbot.show_debug_window = False
        with patch("detection_system.cv2.getWindowProperty", return_value=0):
            aimbot.display_results(self._make_results())
        mock_imshow.assert_not_called()

    @patch("detection_system.cv2.destroyWindow")
    @patch("detection_system.cv2.getWindowProperty", return_value=1)
    def test_destroys_window_when_debug_turned_off(self, mock_prop, mock_destroy, aimbot):
        aimbot.show_debug_window = False
        aimbot.display_results(self._make_results())
        mock_destroy.assert_called_once_with("Aimbot Vision (Debug)")

    @patch("detection_system.cv2.rectangle")
    def test_no_boxes_drawn_when_boxes_none(self, mock_rect, aimbot):
        aimbot.show_debug_window = True
        aimbot.debug_frame = np.zeros((736, 1280, 4), dtype=np.uint8)
        aimbot.display_results(self._make_results(boxes_xyxy=None))
        mock_rect.assert_not_called()


class TestProcessSingleFrame:

    @patch("detection_system.torch.cuda.synchronize")
    def test_skips_inference_when_no_frame(self, mock_sync, aimbot):
        aimbot.capture_and_preprocess_frame = MagicMock(return_value=False)
        aimbot.process_single_frame()

        # Warmup -> 1
        assert aimbot.model.call_count == 1
        mock_sync.assert_not_called()

    @patch("detection_system.torch.cuda.synchronize")
    def test_runs_inference_when_frame_available(self, mock_sync, aimbot):
        aimbot.capture_and_preprocess_frame = MagicMock(return_value=True)
        aimbot.display_results = MagicMock()

        aimbot.process_single_frame()
        assert aimbot.model.call_count == 2

        aimbot.model.assert_called_with(aimbot.model_tensor, verbose=False)
        mock_sync.assert_called_once()


class TestAimBotCleanup:

    @patch("detection_system.cv2.destroyAllWindows")
    def test_cleanup_releases_camera_and_destroys_windows(self, mock_destroy, aimbot):
        aimbot.cleanup()
        aimbot.camera.release.assert_called_once()
        mock_destroy.assert_called_once()


# ==============================================================================
# VISION WORKER TESTS
# ==============================================================================

class TestVisionWorker:

    def _run_worker(self, messages, mock_aimbot_instance):
        from detection_system import vision_worker

        pipe = MagicMock()
        pipe.poll.side_effect = [True] * len(messages) + [False] * 1000
        pipe.recv.side_effect = messages

        with patch("detection_system.AimBot", return_value=mock_aimbot_instance), \
                patch("detection_system.time.sleep"), \
                patch("detection_system.cv2.destroyAllWindows"):
            vision_worker(pipe, "fake.engine", 60)

    def test_start_sets_is_running(self):
        mock_aimbot = MagicMock()
        pipe = MagicMock()

        call_count = 0

        def poll_side():
            nonlocal call_count
            call_count += 1
            return call_count <= 2

        pipe.poll.side_effect = poll_side
        pipe.recv.side_effect = [{"cmd": "START"}, {"cmd": "QUIT"}]

        from detection_system import vision_worker
        with patch("detection_system.AimBot", return_value=mock_aimbot), \
                patch("detection_system.time.sleep"), \
                patch("detection_system.time.perf_counter", side_effect=[0.0, 0.02]), \
                patch("detection_system.cv2.destroyAllWindows"):
            vision_worker(pipe, "fake.engine", 60)

        mock_aimbot.process_single_frame.assert_called()

    def test_stop_command_stops_processing(self):
        mock_aimbot = MagicMock()
        self._run_worker([{"cmd": "STOP"}, {"cmd": "QUIT"}], mock_aimbot)
        mock_aimbot.process_single_frame.assert_not_called()

    def test_debug_command_sets_show_debug_window(self):
        mock_aimbot = MagicMock()
        self._run_worker([{"cmd": "DEBUG", "value": False}, {"cmd": "QUIT"}], mock_aimbot)
        assert mock_aimbot.show_debug_window is False

    def test_cleanup_called_on_exit(self):
        mock_aimbot = MagicMock()
        self._run_worker([{"cmd": "QUIT"}], mock_aimbot)
        mock_aimbot.cleanup.assert_called_once()


# ==============================================================================
# GUI TESTS
# ==============================================================================

class TestGUI:

    def test_on_start_sends_start_command(self, gui_app):
        gui_app.on_start(None, None)
        gui_app.pipe.send.assert_called_once_with({"cmd": "START"})

    def test_on_stop_sends_stop_command(self, gui_app):
        gui_app.on_stop(None, None)
        gui_app.pipe.send.assert_called_once_with({"cmd": "STOP"})

    def test_on_debug_toggle_sends_debug_true(self, gui_app):
        gui_app.on_debug_toggle(None, True)
        gui_app.pipe.send.assert_called_once_with({"cmd": "DEBUG", "value": True})

    def test_on_debug_toggle_sends_debug_false(self, gui_app):
        gui_app.on_debug_toggle(None, False)
        gui_app.pipe.send.assert_called_once_with({"cmd": "DEBUG", "value": False})

    def test_run_sends_quit_on_exit(self, gui_app):
        gui_app.run()
        gui_app.pipe.send.assert_called_with({"cmd": "QUIT"})