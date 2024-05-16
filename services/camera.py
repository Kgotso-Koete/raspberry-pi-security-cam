# general system imports
import os, io, logging, json, time, re
from datetime import datetime
from threading import Condition
import threading

# flas imports
from flask import Flask, render_template, request, jsonify, Response, send_file, abort

# picamera imports
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
from libcamera import Transform, controls

# Python Imaging Library imports
from PIL import Image

# project classes
from .stream import StreamingOutput


class Camera:
    """
    A that stores a Picamera object and other relevant settings.
    """

    # Picamera2
    picam2 = None
    # default settings
    camera_config = None
    current_dir = None

    # settings
    live_settings = None
    rotation_settings = None
    sensor_mode = None
    capture_settings = None
    selected_resolution = None
    resolution = None
    camera_modes = None
    mode = None
    video_config = None
    default_settings = None
    # camera hardware module variables
    camera_module_info = None
    camera_properties = None
    # timelapse variables
    timelapse_running = None
    timelapse_thread = None
    # streaming variables
    output = None
    metadata = None

    # -------------------------------------------------------------------------------
    # set class variables when service is initialized
    # -------------------------------------------------------------------------------

    def __init__(self, app):
        """
        Constructs all the necessary attributes for the Camera object.
        """

        # Int Picamera2 and default settings
        self.picam2 = Picamera2()
        # Int Picamera2 and default settings
        self.timelapse_running = False
        self.timelapse_thread = None

        self.load_picture_config()

        # Split config for different uses
        self.live_settings = self.camera_config.get("controls", {})
        self.rotation_settings = self.camera_config.get("rotation", {})
        self.sensor_mode = self.camera_config.get("sensor-mode", 1)
        self.capture_settings = self.camera_config.get("capture-settings", {})

        # Parse the selected capture resolution for later
        self.selected_resolution = self.capture_settings["Resolution"]
        self.resolution = self.capture_settings["available-resolutions"][
            self.selected_resolution
        ]
        print(f"\nCamera Settings:\n{self.capture_settings}\n")
        print(f"\nCamera Set Resolution:\n{self.resolution}\n")

        # Get the sensor modes and pick from the the camera_config
        self.camera_modes = self.picam2.sensor_modes
        self.mode = self.picam2.sensor_modes[self.sensor_mode]

        # Create the video_config
        self.load_video_config()

        # Pull default settings and filter live_settings for anything picamera2 wont use (because the not all cameras use all settings)
        self.load_default_settings()

        #  Load camera modules data from the camera-module-info.json JSON file
        self.load_hardware_modules_info()

        # Create the upload folder if it doesn't exist
        self.create_upload_folder(app)

        return

    # -------------------------------------------------------------------------------
    # initialization methods
    # -------------------------------------------------------------------------------

    def load_picture_config(self):
        """
        Loads configuration/settings from the camera-config.json file
        """

        # Get the directory of the current script
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        # Define the path to the camera-config.json file
        camera_config_path = os.path.join(self.current_dir, "camera-config.json")
        # Pull settings from from config file
        with open(camera_config_path, "r") as file:
            self.camera_config = json.load(file)
        # Print config for validation
        print(f"\nCamera Config:\n{self.camera_config}\n")

        return

    def load_video_config(self):
        """
        Loads video configuration/settings from initialized mode settings
        """

        main = {"size": self.resolution}
        sensor = {"output_size": self.mode["size"], "bit_depth": self.mode["bit_depth"]}
        self.video_config = self.picam2.create_video_configuration(
            main=main, sensor=sensor
        )

        print(f"\nVideo Config:\n{self. video_config}\n")

        return

    def load_default_settings(self):
        """
        Pull default settings and filter live_settings for anything picamera2 wont use (because the not all cameras use all settings)
        """

        self.default_settings = self.picam2.camera_controls
        self.live_settings = {
            key: value
            for key, value in self.live_settings.items()
            if key in self.default_settings
        }

        return

    def load_hardware_modules_info(self):
        """
        Load camera modules data from the camera-module-info.json JSON file
        """

        # Define the path to the camera-module-info.json file
        camera_module_info_path = os.path.join(
            self.current_dir, "camera-module-info.json"
        )
        # Load camera modules data from the JSON file
        with open(camera_module_info_path, "r") as file:
            self.camera_module_info = json.load(file)

        self.camera_properties = self.picam2.camera_properties
        print(f"\nPicamera2 Camera Properties:\n{self.camera_properties}\n")

        return

    def create_upload_folder(self, app):
        """
        Create the upload folder if it doesn't exist
        """

        # Set the path where the images will be stored
        UPLOAD_FOLDER = os.path.join(self.current_dir, "static/gallery")
        app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

        # Create the upload folder if it doesn't exist
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

        return

    def configure_camera(self):
        """
        Configure the camera
        """
        self.picam2.set_controls(self.live_settings)
        time.sleep(0.5)
        return

    def restart_configure_camera(self, restart_settings):
        """
        Reset the camera
        """
        self.stop_camera_stream()
        transform = Transform()
        # Update settings that require a restart
        for key, value in restart_settings.items():
            if key in restart_settings:
                if key in ("hflip", "vflip"):
                    setattr(transform, key, value)

        self.video_config["transform"]
        self.start_camera_stream()

        return

    # -------------------------------------------------------------------------------
    # camera operation methods
    # -------------------------------------------------------------------------------

    def take_snapshot(self, app):
        """
        Take a snapshot
        """

        try:
            image_name = f"snapshot/pimage_snapshot"
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], image_name)
            request = self.picam2.capture_request()
            request.save("main", f"{filepath}.jpg")
            logging.info(f"Image captured successfully. Path: {filepath}")
        except Exception as e:
            logging.error(f"Error capturing image: {e}")

        return

    def take_photo(self):
        """
        Function to take images for timelapse
        """
        try:
            timestamp = int(datetime.timestamp(datetime.now()))
            image_name = f"pimage_{timestamp}"
            filepath = os.path.join(self.app.config["UPLOAD_FOLDER"], image_name)
            request = self.picam2.capture_request()
            request.save("main", f"{filepath}.jpg")
            if self.capture_settings["makeRaw"]:
                request.save_dng(f"{filepath}.dng")

            request.release()

            # selected_resolution = self.capture_settings["Resolution"]
            # resolution = self.capture_settings["available-resolutions"][selected_resolution]
            # original_image = Image.open(filepath)
            # resized_image = original_image.resize(resolution)
            # resized_image.save(filepath)

            logging.info(f"Image captured successfully. Path: {filepath}")
        except Exception as e:
            logging.error(f"Error capturing image: {e}")

        return

    def take_lapse(self, interval):
        """
        Function to take images for timelapse
        """
        while self.timelapse_running:
            self.take_photo()
            time.sleep(interval)

        return

    def start_timelapse(self):
        """
        Create a timelapse
        """

        # Check if the timelapse is already running
        if not self.timelapse_running:
            # Specify the interval between images (in seconds)
            interval = 2

            # Set the timelapse flag to True
            self.timelapse_running = True

            # Create a new thread to run the timelapse function
            self.timelapse_thread = threading.Thread(
                target=self.take_lapse, args=(interval,)
            )

            # Start the timelapse thread
            self.timelapse_thread.start()

            return jsonify(success=True, message="Timelapse started successfully")
        else:
            print("Timelapse is already running")
            return jsonify(success=True, message="Timelapse is already running")

    # -------------------------------------------------------------------------------
    # camera stream methods
    # -------------------------------------------------------------------------------

    def start_camera_stream(self):
        """
        Initialize camera stream
        """

        self.picam2.configure(self.video_config)
        self.output = StreamingOutput()
        self.picam2.start_recording(JpegEncoder(), FileOutput(self.output))
        self.metadata = self.picam2.capture_metadata()
        time.sleep(1)

        return

    def stop_camera_stream(self):
        """
        Stop the camera stream
        """

        self.picam2.stop_recording()
        time.sleep(1)

        return

    def generate(self):
        """
        Generate output to be combined into a video feed
        """
        while True:
            with self.output.condition:
                self.output.condition.wait()
                frame = self.output.frame
            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
