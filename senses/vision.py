from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np


class Vision:
    def __init__(self, camera_index: int = 0) -> None:
        self.logger = logging.getLogger(__name__)
        self.camera_index = camera_index
        self.capture = cv2.VideoCapture(camera_index)

    def capture_frame(self) -> Optional[np.ndarray]:
        if not self.capture.isOpened():
            self.logger.warning("Camera not available.")
            return None
        success, frame = self.capture.read()
        if not success:
            self.logger.warning("Failed to capture frame.")
            return None
        return frame

    def release(self) -> None:
        if self.capture.isOpened():
            self.capture.release()
