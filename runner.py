import gc
import logging
import traceback
from collections import deque
from typing import Counter

import cv2
from flask import Response

from ConfigReader import config
from DB.db import CarLogs, Registered, Vehicle, db
from Detector.load_yolo import DetectorYolo
from OCR.load_ocr import OCR
from Tracker.load_tracker import Tracker
from Utils.utils import save_car_image

# from ocr_test import NumPlateOCR


class Runner:
    def __init__(self, input_path) -> None:
        self.db = db
        self.db.create_all()

        # create a shared queue

        logging.basicConfig(level=logging.INFO, filename="yololog.txt", filemode="w")
        self.config = config.YOLO
        self.vehicle_detector = DetectorYolo(config=self.config["vehicle_detection"])
        self.numberplate_detector = DetectorYolo(config=self.config["license_plate"])
        self.fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self.cap = cv2.VideoCapture(input_path)
        self.ocr = OCR()
        self.tracker = Tracker()
        self.writer = cv2.VideoWriter(
            "output/out.avi",
            self.fourcc,
            25.0,
            (int(self.cap.get(3)), int(self.cap.get(4))),
        )
        if self.cap.isOpened() is False:
            print("Video Error")
            exit(-1)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))  # width
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))  # height

        self.tracked_cars_lp = {}
        self.final_results = {}  # {car_id: lp}

        # cv2.namedWindow("frame", cv2.WINDOW_NORMAL)

        self.prev_car_id = None

    def get_cap(self):
        return self.cap    

    @staticmethod
    def get_max_lp(list_of_lp):
        return Counter(list_of_lp).most_common(1)[0][0]

    @staticmethod
    def crop(frame, sub_frame):
        return frame[
            int(sub_frame["ymin"]) : int(sub_frame["ymax"]),
            int(sub_frame["xmin"]) : int(sub_frame["xmax"]),
        ]

    @staticmethod
    def insert_car(best_number_plate, cropped_car):
        # license, datetime, car_image,
        print("insert-method-called")

        car_path, date_time = save_car_image(cropped_car, best_number_plate)
        print(f"Car-saved: license-plate={best_number_plate}")
        try:
            is_suspicious = (
                Vehicle.query.filter_by(num_plate=best_number_plate).first().suspicious
            )
        except AttributeError:
            is_suspicious = False
        except Exception as e:
            is_suspicious = False
            print(f"insert-cars execption: {e}")

        if is_suspicious:
            print("\n\n\nIN IS_SUSPICIOUS")
            # TODO Generate ALERT and stuff
            vehicle_id = (
                Registered.query.join(Vehicle, Registered.vehicle_id == Vehicle.id)
                .filter_by(num_plate=best_number_plate)
                .first()
                .vehicle_id
            )
            print(f"vehicle_id: {vehicle_id}\n")
            car_log = CarLogs(
                image_path=car_path,
                time=date_time,
                vehicle_id=vehicle_id,
                is_suspicious=True,
                is_registered=True,
                license_plate=best_number_plate,
            )
            db.session.add(car_log)
            db.session.commit()
            print("SUSPICIOUS Car found..")
        else:
            # GET USER ID for that number plate
            try:
                print("before-vehicle-id query")
                vehicle_id = (
                    Registered.query.join(Vehicle, Registered.vehicle_id == Vehicle.id)
                    .filter_by(num_plate=best_number_plate)
                    .first()
                    .vehicle_id
                )
                # Vehicle exists, Add the vehicle to the database
                # image_path, time, v_id
                print("Detected car vehicle-id: ", vehicle_id)
                car_log = CarLogs(
                    image_path=car_path,
                    time=date_time,
                    vehicle_id=vehicle_id,
                    is_registered=True,
                    license_plate=best_number_plate,
                )
                db.session.add(car_log)
                db.session.commit()
                print("car-recognized")

            except AttributeError:  # User Does no exist, GENERATE ALERT
                # TODO: generate alert that unregistered car is entrying
                # save this alert to db
                # visitor = Visitor(
                #     name="None-name",
                #     cnic="6110112345678",
                #     license_plate=best_number_plate,
                # )
                car_log = CarLogs(
                    image_path=car_path,
                    time=date_time,
                    vehicle_id=None,
                    is_visitor=True,
                    license_plate=best_number_plate,
                )
                # db.session.add(visitor)
                db.session.add(car_log)
                db.session.commit()
                print("UNKNOWN CAR DETECTED..")

            except Exception as e:
                print(type(e).__name__)
                print("\nERROR found insert-car func. Error is as below: \n", e)

    def __call__(self):

        ret, frame_orig = self.cap.read()

        if cv2.waitKey(1) & 0xFF == ord("q"):
            self.cap.release()
            ret = False

        if ret is True:
            frame = frame_orig.copy()

            car_det = self.vehicle_detector(frame)

            if len(car_det.pandas().xyxy[0]):

                best_car = car_det.pandas().xyxy[0].iloc[0, :]

                # Track best car
                tracked_car = self.tracker.update(best_car)
                # If the tracked id changes, we insert the most common LP of previous id to the database
                # TODO:
                try:
                    print(
                        f"prev-car-id: {self.prev_car_id}  --  curr-car-id: {tracked_car[0][-1]}"
                    )
                except IndexError:
                    ret, jpeg = cv2.imencode(".jpg", frame)
                    return jpeg.tobytes()
                if self.prev_car_id == tracked_car[0][-1]:
                    ...
                else:
                    if (
                        self.prev_car_id != tracked_car[0][-1]
                    ):  # If New Car come, insert the best of previous car to Database
                        try:
                            best_license_plate = self.get_max_lp(
                                self.tracked_cars_lp[self.prev_car_id]
                            )
                            self.insert_car(best_license_plate, cropped_car)
                            print("inserting")
                        except Exception as e:
                            print(e)
                            print("\nERROR: unable to exec insert_cars func")
                            traceback.print_stack()
                        self.prev_car_id = tracked_car[0][-1]
                        self.tracked_cars_lp[self.prev_car_id] = []

                cv2.rectangle(
                    frame,
                    (int(best_car["xmin"]), int(best_car["ymin"])),
                    (int(best_car["xmax"]), int(best_car["ymax"])),
                    (255, 0, 0),
                    2,
                )

                cropped_car = Runner.crop(frame, best_car)

                licence_det = self.numberplate_detector(cropped_car)
                best_lp = licence_det.pandas().xyxy[0].iloc[0:1, :]

                if len(best_lp):
                    # print('best-lp', best_lp)
                    cropped_lp = Runner.crop(cropped_car, best_lp)
                    # print(f'cropped-lp: {cropped_lp}')
                    print(f"cropped-lp shape: {cropped_lp.shape}")
                    # cropped_lp = cropped_car[
                    #     int(best_lp["ymin"]) : int(best_lp["ymax"]),
                    #     int(best_lp["xmin"]) : int(best_lp["xmax"]),
                    # ]
                    # cv2.imshow("croppedlp", cropped_lp)
                    try:
                        big_lp = cv2.resize(cropped_lp, (0, 0), fx=5, fy=5)
                    # print(f'big-lp: {big_lp}')
                    except Exception:
                        ret, jpeg = cv2.imencode(".jpg", frame)
                        return jpeg.tobytes()
                        # cv2.imshow("cripped-car", cropped_lp)
                        # cv2.imshow('best-lp', best_lp)
                        # try:
                        #     cv2.imshow("big-lp", big_lp)
                        # except Exception:
                        #     ...
                        # cv2.waitKey(0)
                    #     print("Error: ", E)
                    #     print("Error: ", E)
                    #     continue
                    # print(big_lp.shape)
                    ocr_result = self.ocr(big_lp)
                    # print(ocr_result)

                    # add ocr results to tracked dictionary
                    if len(ocr_result) and len(tracked_car):
                        if tracked_car[0][-1] in self.tracked_cars_lp:
                            self.tracked_cars_lp[tracked_car[0][-1]].append(
                                ocr_result[0][1]
                            )
                        else:
                            self.tracked_cars_lp[tracked_car[0][-1]] = [
                                ocr_result[0][1]
                            ]

                        # print(self.tracked_cars_lp)
                        most_common = Runner.get_max_lp(
                            self.tracked_cars_lp[tracked_car[0][-1]]
                        )
                        # print(f'most-common-lps: {most_common}//')

                        # if a suspicious car is detected
                        # if Vehicle.query.filter_by(num_plate=most_common).first().suspicious:
                        #     print('FOUND A SUSPICIOUS CAR: ', most_common)

                    # self.ocr(cropped_lp)
                    if len(ocr_result) and len(tracked_car):
                        cv2.rectangle(
                            cropped_car,
                            (int(best_lp["xmin"]), int(best_lp["ymin"])),
                            (int(best_lp["xmax"]), int(best_lp["ymax"])),
                            (0, 255, 0),
                            2,
                        )

                        # id on car
                        cv2.putText(
                            frame,
                            str(self.tracked_cars_lp[tracked_car[0][-1]]),
                            (
                                int(best_car["xmin"] + 50),
                                int(best_car["ymin"] + 300),
                            ),
                            cv2.FONT_HERSHEY_DUPLEX,
                            2.0,
                            (0, 255, 0),
                            2,
                        )

                        # add license plate details to the cropped car
                        # print(ocr_result)
                        # cv2.putText(
                        #     cropped_car,
                        #     most_common,
                        #     (10, 30),
                        #     cv2.FONT_HERSHEY_SIMPLEX,
                        #     1.0,
                        #     (0, 255, 0),
                        #     2,
                        # )

            self.writer.write(frame)

            ret, jpeg = cv2.imencode(".jpg", frame)
            return jpeg.tobytes()

            # frame = cv2.imencode(".jpg", frame)
            # frame = frame.tobytes()
            # yield (
            #     b"--frame\r\n"
            #     b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n\r\n"
            # )
            # # break

        else:
            # print("WRONG PATH")
            self.cap.release()
            cv2.destroyAllWindows()
            return None

    def gen(self):
        while True:
            frame = self.__call__()
            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n\r\n"
                )

            else:
                print("THIS msg")
                return {"message": "Done"}
