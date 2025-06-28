from flask import Flask, Response, jsonify, stream_with_context
import cv2
import PySpin
import threading
import cv2

class AcquisitionCamera:
    def __init__(self):
        self.system = None
        self.cam_list = None
        self.cam = None
        self.latest_image = None
        self.processor = PySpin.ImageProcessor()

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
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False
                    
        return True

    def acquire_image(self):
        try:
            image_result = self.cam.GetNextImage(1000)
            if not image_result.IsIncomplete():
                image_result = self.processor.Convert(image_result, PySpin.PixelFormat_BGR8)
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
        #if self.system is not None:
            #self.system.ReleaseInstance()
        self.cam = None
        self.cam_list = None
        self.system = None
        self.latest_image = None
        self.running = False

    def serve_image(self):
        while True:
            img = self.get_image()
            if img is not None:
                yield (b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + img + b'\r\n')

app = Flask(__name__)
if __name__ == "__main__":
    cam = AcquisitionCamera()
    if cam.start():
        def image_loop(stop_event):
            while not stop_event.is_set():
                cam.acquire_image()
        stop_event = threading.Event()
        t = threading.Thread(target=image_loop, daemon=True, args=(stop_event,))
        t.start()
        @app.route('/')
        def video_feed():
            return Response(stream_with_context(cam.serve_image()),
                            mimetype='multipart/x-mixed-replace; boundary=frame')
        app.run(host='0.0.0.0', port=9001, threaded=True)
        stop_event.set()
        t.join()
        cam.stop()
    else:
        print("Failed to start camera.")