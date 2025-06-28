from flask import Flask, Response, jsonify, stream_with_context
import cv2
import threading
import time

app = Flask(__name__)

# Global registry for cameras
cameras = {}            # { index: cv2.VideoCapture }
clients = {}            # { index: int }
locks = {}              # { index: threading.Lock }
restart_flags = {}      # { index: threading.Event }

def get_lock(index):
    if index not in locks:
        locks[index] = threading.Lock()
    return locks[index]

def get_restart_flag(index):
    if index not in restart_flags:
        restart_flags[index] = threading.Event()
    return restart_flags[index]

def get_camera(index):
    if index not in cameras or cameras[index] is None:
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            return None
        cameras[index] = cap
    return cameras[index]

def release_camera(index):
    if index in cameras and cameras[index] is not None:
        cameras[index].release()
        cameras[index] = None

def generate_frames(index):
    try:
        lock = get_lock(index)
        restart_event = get_restart_flag(index)

        with lock:
            cam = get_camera(index)
            if cam is None:
                yield b''  # Empty stream
                return
            clients[index] = clients.get(index, 0) + 1
            restart_event.clear()

        while True:
            if restart_event.is_set():
                break

            with lock:
                cam = get_camera(index)
                if cam is None:
                    break
                success, frame = cam.read()
                if not success:
                    break
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            #time.sleep(0.05)

    finally:
        with get_lock(index):
            clients[index] = max(clients.get(index, 1) - 1, 0)
            if clients[index] == 0:
                release_camera(index)

@app.route('/cam/<int:index>')
def video_feed(index):
    return Response(stream_with_context(generate_frames(index)),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/cam/<int:index>/status')
def status(index):
    with get_lock(index):
        cam = cameras.get(index)
        active = cam is not None and cam.isOpened()
        return jsonify({
            'camera_index': index,
            'camera_active': active,
            'connected_clients': clients.get(index, 0)
        })

@app.route('/cam/<int:index>/restart')
def restart(index):
    with get_lock(index):
        restart_flags[index] = get_restart_flag(index)
        restart_flags[index].set()
        release_camera(index)
    return jsonify({'camera_index': index, 'status': 'restarting'})

def list_available_cameras(max_index=5):
    available = []
    for i in range(max_index + 1):
        cap = cv2.VideoCapture(i)
        if cap is not None and cap.isOpened():
            available.append(i)
            cap.release()
    return available

@app.route('/cameras')
def list_cameras():
    cameras = list_available_cameras()
    return jsonify({'available_cameras': cameras})

@app.route('/')
def index():
    return jsonify({
        'message': 'Use /cam/<index> for stream, /cam/<index>/status, /cam/<index>/restart, /cameras'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9001, threaded=True)
