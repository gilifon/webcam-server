import os
import PySpin
import sys
import platform
import threading
import time
import cv2

class AcquisitionCamera:
    def __init__(self):
        self.system = None
        self.cam_list = None
        self.cam = None
        self.latest_image = None

    def start(self):
        self.system = PySpin.System.GetInstance()
        self.cam_list = self.system.GetCameras()
        num_cameras = self.cam_list.GetSize()
        if num_cameras == 0:
            self.cam_list.Clear()
            self.system.ReleaseInstance()
            print('No cameras!')
            return False
        self.cam = self.cam_list[0]
        self.cam.Init()
        try:
            self.cam.BeginAcquisition()
            #processor = PySpin.ImageProcessor()
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False
                    
        return True

    def acquire_image(self):
        try:
            image_result = self.cam.GetNextImage(1000)
            if not image_result.IsIncomplete():
                image_data = image_result.GetNDArray()
                success, jpg_bytes = cv2.imencode('.jpg', image_data)
                if success:
                    jpg_bytes = jpg_bytes.tobytes()  # This is the JPEG image in bytes
                    self.latest_image = jpg_bytes
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False
        return True

    def get_image(self):
        return self.latest_image

    def stop(self):
        if self.cam is not None:
            try:
                self.cam.EndAcquisition()
                self.cam.DeInit()
            except Exception:
                pass
        if self.cam_list is not None:
            self.cam_list.Clear()
        if self.system is not None:
            self.system.ReleaseInstance()
        self.cam = None
        self.cam_list = None
        self.system = None
        self.latest_image = None
        self.running = False

if __name__ == "__main__":
    cam = AcquisitionCamera()
    if cam.start():
        def image_loop():
            while True:
                cam.acquire_image()
        t = threading.Thread(target=image_loop, daemon=True)
        t.start()
        try:
            while t.is_alive():
                img = cam.get_image()
                if img is not None:
                    try:
                        with open('output.jpg', 'wb') as f:
                            f.write(img)
                            #img.Save('acquired_image.jpg')
                        print("Image saved to acquired_image.jpg.")
                    except PySpin.SpinnakerException as ex:
                        print("Failed to save image: %s" % ex)
                else:
                    print("No image available.")
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("Stopping acquisition...")
        cam.stop()
    else:
        print("Failed to start camera.")
    print("Exiting.")
