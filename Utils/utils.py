import numpy as np
import cv2
import pytz
from datetime import datetime


def save_car_image(image: np.ndarray, license: str):
    #  {license num of car}_{time of entry/exit}.jpg
    tz_pk = pytz.timezone('Asia/Karachi')
    datetime_pk = datetime.now(tz_pk).strftime("%Y-%m-%d %H:%M:%S")
    save_path = f'cars_images/{license}_{datetime_pk}.jpg'
    saved = cv2.imwrite(save_path, image)
    if saved:
        print('car saved')
    else:
        print('car-not-saved')
    return save_path, datetime_pk
