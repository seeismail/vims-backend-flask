YOLO = {
    "vehicle_detection": {
        "input_shape": (640, 640),
        "n_classes": 3,
        "classes": [5, 2],
        "size": 640,
    },
    "license_plate": {"custom": True, "size": 640, "path": "weights/license_plate.pt"},
}
