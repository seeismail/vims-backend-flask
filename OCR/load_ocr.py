import cv2
import easyocr
import numpy as np
from skimage.morphology import disk, opening


class OCR:
    def __init__(self) -> None:
        self.ocr = easyocr.Reader(
            ["en"],
            gpu=True,
            quantize=True,
            recognizer=True,
            recog_network="english_g2",
        )

    @staticmethod
    def gray_scale(frame):
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def resize(frame, fx, fy, interpolation):
        return cv2.resize(
            frame,
            None,
            fx=fx,
            fy=fy,
            interpolation=interpolation,
        )

    @staticmethod
    def dilate_frame(gray_scale, kernel_size, iterations):
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        return cv2.dilate(gray_scale, kernel, iterations=iterations)

    @staticmethod
    def erode_frame(dilated_frame, kernel_size, iterations):
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        return cv2.erode(dilated_frame, kernel, iterations=iterations)

    @staticmethod
    def blur(frame):
        return cv2.medianBlur(frame, 3)

    @staticmethod
    def threshold(
        frame,
        max_val,
        adapt_method,
        thresh_type,
        block_size,
        const,
    ):
        return cv2.adaptiveThreshold(
            frame, max_val, adapt_method, thresh_type, block_size, const
        )

    def __preprocessing(self, img: np.ndarray) -> str:
        gray_scale = OCR.gray_scale(img)
        resized_frame = OCR.resize(
            gray_scale,
            1.2,
            1.2,
            cv2.INTER_NEAREST,
        )

        dilated_frame = OCR.dilate_frame(resized_frame, 3, 5)

        eroded_frame = OCR.erode_frame(dilated_frame, 3, 5)

        blured = OCR.blur(eroded_frame)

        binariezed_threshold = OCR.threshold(
            blured,
            256,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            9,
            10,
        )

        return binariezed_threshold

    def __call__(self, img: np.ndarray) -> str:
        # img = cv2.imread(img)
        # TODO: Add more pre-processing steps https://dontrepeatyourself.org/post/number-plate-recognition-with-opencv-and-easyocr/
        # img_pre = self.__preprocessing(img)
        # gray scale
        # gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # cv2.imshow("grayorig", img_gray)

        black = 0
        white = 255
        threshold = 140

        pixels = img_gray

        pixels[pixels > threshold] = white
        pixels[pixels < threshold] = black

        blobSize = 3  # Select the maximum radius of the blobs you would like to remove
        structureElement = disk(
            blobSize
        )  # you can define different shapes, here we take a disk shape
        # We need to invert the image such that black is background and white foreground to perform the opening
        pixels = np.invert(opening(np.invert(pixels), structureElement))

        # cv2.imshow("prepro", pixels)
        # cv2.waitKey(0)
        return self.ocr.readtext(
            pixels,
            # decoder="beamsearch",
            beamWidth=15,
            workers=4,
            allowlist="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ- ",
            contrast_ths=0.3,
            adjust_contrast=0.8,
            batch_size=4,
        )


if __name__ == "__main__":
    ...
    # ocr = OCR()

    # img = cv2.imread("croppedlp.png")
    # print(img.shape)

    # ocr_result = ocr(img)
    # print(f"{ocr_result[0][1]} {ocr_result[0][2] * 100:.2f}%")
    # ocr = easyocr.Reader(["ar"])

    # img = cv2.imread("idcard.jpg")

    # result = ocr.readtext(img)
    # for r in result:
    #     print(r[1])
