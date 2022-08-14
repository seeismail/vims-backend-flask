import numpy as np
import torch

# import logging # implement it


class DetectorYolo:
    def __init__(self, config) -> None:
        self.config = config
        if self.config.get("custom"):
            self.model = torch.hub.load(
                "Detector/yolov5",
                "custom",
                source="local",
                path=config["path"],
            )
        else:
            self.model = torch.hub.load(
                "Detector/yolov5",
                "yolov5s",
                source="local",
            )
            self.model.classes = config["classes"]

    def __call__(self, frame) -> np.ndarray:

        det = self.model(frame, size=self.config["size"])

        return det
