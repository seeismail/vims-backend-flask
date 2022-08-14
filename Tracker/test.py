import cv2
import numpy as np
import torch

from sort.sort import Sort

frame = cv2.imread("frame.png")
car_model = torch.hub.load("Detector/yolov5", "yolov5s", source="local")
car_model.classes = [5, 2]

car_det = car_model(frame)
best_car = car_det.pandas().xyxy[0].iloc[0, :]

print(np.array([best_car.values[:-2]]).shape)

mot_tracker = Sort()

track_bbs_ids = mot_tracker.update(np.array([best_car.values[:-2]]))
