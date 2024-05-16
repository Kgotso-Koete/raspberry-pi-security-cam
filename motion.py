# with help from https://www.hackster.io/mastrolinux/iot-security-camera-with-raspberry-pi-render-and-picamera2-dd3298
from gpiozero import MotionSensor
from picamera2.picamera2 import *
from datetime import datetime
from signal import pause
import os

# Define the path to the project directory
project_dir = os.path.dirname(os.path.abspath(__file__))
gallery_dir = os.path.join(project_dir, "static", "gallery")

# Create the gallery directory if it doesn't exist
if not os.path.exists(gallery_dir):
    os.makedirs(gallery_dir)

pir = MotionSensor(14)
camera = Picamera2()
camera.start_preview(Preview.NULL)
config = camera.create_still_configuration()
camera.configure(config)


def capture():
    camera.start()
    timestamp = datetime.now().isoformat()
    print("%s Detected movement" % timestamp)

    # Save the image to the gallery directory
    image_path = os.path.join(gallery_dir, f"{timestamp}.jpg")
    metadata = camera.capture_file(image_path)
    print(metadata)
    camera.stop()


def not_moving():
    timestamp = datetime.now().isoformat()
    print("%s All clear" % timestamp)


pir.when_motion = capture
pir.when_no_motion = not_moving

pause()
