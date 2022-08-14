import numpy as np

from Tracker.sort.sort import Sort

# create instance of SORT
mot_tracker = Sort()


class Tracker:
    def __init__(self) -> None:
        self.tracker = Sort()

    @staticmethod
    def __preprocess(bbs):
        return np.array([bbs.values[:-2]])

    def update(self, bbs):
        return self.tracker.update(Tracker.__preprocess(bbs))


if __name__ == "__main__":  # Test case
    import cv2
    import torch

    frame = cv2.imread("frame.png")
    car_model = torch.hub.load("Detector/yolov5", "yolov5s", source="local")
    car_model.classes = [5, 2]

    car_det = car_model(frame)
    best_car = car_det.pandas().xyxy[0].iloc[0, :]

    tracker = Tracker()
    print(tracker.update(best_car))
