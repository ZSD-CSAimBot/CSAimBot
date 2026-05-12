"""Camera abstraction used by the detection system."""

import sys
import torch
import numpy as np


class CameraProvider:
    def __init__(self, region):
        """
        Initialize the camera backend for the active platform.

        Args:
            region: Capture region in the form (left, top, right, bottom).
        """
        self.platform = sys.platform
        self.region = region
        
        if self.platform == 'win32':
            import bettercam
            self.camera = bettercam.create(output_color="BGRA", region=region, nvidia_gpu=True)
            
        elif self.platform.startswith('linux'):
            import mss
            self.camera = mss.mss()
            self.monitor = {
                "left": region[0],
                "top": region[1],
                "width": region[2] - region[0],
                "height": region[3] - region[1]
            }

    def grab_gpu_tensor(self):
        """
        Capture a frame and return it as a GPU tensor.

        Returns:
            A PyTorch tensor containing the frame on the GPU, or None if capture fails.
        """
        if self.platform == 'win32':
            frame = self.camera.grab()
            if frame is not None:
                return torch.from_dlpack(frame)
                
        elif self.platform.startswith('linux'):
            frame = self.camera.grab(self.monitor)
            if frame is not None:
                np_frame = np.array(frame, copy=False)
                return torch.from_numpy(np_frame).to('cuda', non_blocking=True)
                
        return None

    def release(self):
        """Release the underlying capture backend."""
        if self.platform == 'win32':
            self.camera.release()
        elif self.platform.startswith('linux'):
            self.camera.close()