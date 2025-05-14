# 217000981 JJ PETERS - Assignment 4 - Smart Room Controller

from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
from threading import Thread
from datetime import datetime
import sqlite3
import httpx
import asyncio
from functools import wraps
from time import sleep

# Initialize the Flask application
app = Flask(__name__)
app.config["SECRET_KEY"] = "1234567"  # Secret key for session management

# Define authorization token and device IP for Arduino communication
AUTH_TOKEN = "1234567"  # Same token as in Arduino code
DEVICE_IP = "http://192.168.43.147"  # Replace with your Arduino's IP address

# Set up SocketIO for real-time communication between Flask and the front-end
socketio = SocketIO(app, async_mode="threading")


# --------------------- Database Setup ---------------------
def init_db():
    """
    Initializes the SQLite database by creating a table for logging sensor data if it doesn't exist.
    """
    conn = sqlite3.connect("sensor_data.db")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS sensor_log
           (timestamp TEXT, ldr INTEGER, pir INTEGER, fan_pwm INTEGER, light_state INTEGER, pot INTEGER)"""
    )
    conn.commit()
    conn.close()


# Initialize the database when the application starts
init_db()


# --------------------- Auth Decorator ---------------------
def token_required(f):
    """
    A decorator function to require a valid token in the request headers for protected routes.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Auth-Token")
        if token != AUTH_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)

    return decorated


# --------------------- Background Sensor Poller ---------------------
def background_sensor_updates():
    """
    This function runs in the background to periodically fetch sensor data from the Arduino.
    It logs the data to the database and emits it via SocketIO to update the front-end.
    """
    while True:
        try:
            with httpx.Client() as client:
                # Make GET request to Arduino to fetch sensor data
                response = client.get(f"{DEVICE_IP}/sensors", timeout=2.0)
                if response.status_code == 200:
                    data = response.json()  # Parse JSON response
                    log_sensor_data(data)  # Log the data to the database
                    socketio.emit(
                        "sensor_update", data
                    )  # Emit the data to the front-end via SocketIO
        except Exception as e:
            print(f"Sensor update error: {e}")  # Handle exceptions
        sleep(3)  # Wait for 3 seconds before polling again


def log_sensor_data(data):
    """
    Log sensor data (LDR, PIR, fan PWM, light state, potentiometer value) into the SQLite database.
    """
    ldr = data.get("ldr", 0)
    pir = data.get(
        "pir", "Not Detected"
    )  # Default to "Not Detected" if PIR data is missing
    # Convert PIR string response to 0 (Not Detected) or 1 (Detected)
    pir = 1 if pir == "Person Detected" else 0 if pir == "Not Detected" else 0
    fan_pwm = data.get("fan_pwm", 0)
    light_st = (
        1 if data.get("light_state", 0) == 0 else 1
    )  # Invert the state for correct ON/OFF representation
    pot = data.get("pot", 0)

    # Insert the data into the database with the current timestamp
    conn = sqlite3.connect("sensor_data.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO sensor_log (timestamp, ldr, pir, fan_pwm, light_state, pot) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), ldr, pir, fan_pwm, light_st, pot),
    )
    conn.commit()
    conn.close()


# --------------------- Routes ---------------------


@app.route("/")
def index():
    """
    Render the index.html page for the dashboard.
    """
    return render_template("index.html")


@app.route("/sensors")
async def get_sensor_data():
    """
    Fetch sensor data from the Arduino device, log it into the database, and return it to the client.
    """
    try:
        async with httpx.AsyncClient() as client:
            # Asynchronously fetch sensor data
            response = await client.get(f"{DEVICE_IP}/sensors", timeout=2.0)
            if response.status_code == 200:
                data = response.json()  # Parse JSON response
                sensor_data = {
                    "ldr": data.get("ldr", 0),
                    "pir": data.get("pir", 0),
                    "pot": data.get("pot", 0),
                    "fan_pwm": data.get("fan_pwm", 0),
                    "light_state": data.get("light_state", 0),
                }
                log_sensor_data(data)  # Log the data into the database
                return jsonify(sensor_data)  # Return the data as JSON
        return (
            jsonify({"error": "Device unreachable"}),
            503,
        )  # Handle unreachable device
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Handle other errors


@app.route("/set_fan", methods=["POST"])
async def set_fan_speed():
    """
    Set the fan speed on the Arduino via HTTP POST request.
    """
    try:
        speed = int(request.json.get("fan_speed", 0))
        if not 0 <= speed <= 255:
            return (
                jsonify({"error": "Invalid fan speed"}),
                400,
            )  # Ensure speed is within valid range

        async with httpx.AsyncClient() as client:
            # Send the fan speed to the Arduino
            await client.post(
                f"{DEVICE_IP}/set_fan",
                json={"fan_speed": speed},
                headers={"X-Auth-Token": AUTH_TOKEN},
                timeout=2.0,
            )
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Handle errors


@app.route("/toggle_light", methods=["POST"])
async def toggle_light():
    """
    Toggle the light state on the Arduino via HTTP POST request.
    """
    try:
        state = bool(request.json.get("state", False))
        async with httpx.AsyncClient() as client:
            # Toggle the light state on the Arduino
            await client.post(
                f"{DEVICE_IP}/toggle_light",
                json={"state": state},
                headers={"X-Auth-Token": AUTH_TOKEN},
                timeout=2.0,
            )
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Handle errors


@app.route("/toggle_ldr", methods=["POST"])
async def toggle_ldr():
    """
    Toggle the LDR (Light Dependent Resistor) state on the Arduino.
    """
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{DEVICE_IP}/toggle_ldr",
                headers={"X-Auth-Token": AUTH_TOKEN},
                timeout=2.0,
            )
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Handle errors


@app.route("/control/light", methods=["POST"])
@token_required
async def control_light():
    """
    Control the light state, requires authentication token.
    """
    try:
        state = request.json.get("state") == "on"
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{DEVICE_IP}/toggle_light",
                json={"state": state},
                headers={"X-Auth-Token": AUTH_TOKEN},
                timeout=2.0,
            )
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400  # Handle errors


@app.route("/control/fan", methods=["POST"])
@token_required
async def control_fan():
    """
    Control the fan speed, requires authentication token.
    """
    try:
        speed = int(request.json.get("speed", 0))
        if not 0 <= speed <= 255:
            return jsonify({"error": "Fan speed out of range"}), 400
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{DEVICE_IP}/set_fan",
                json={"fan_speed": speed},
                headers={"X-Auth-Token": AUTH_TOKEN},
                timeout=2.0,
            )
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400  # Handle errors


@app.route("/authenticate", methods=["POST"])
def authenticate():
    """
    Authenticate a user by validating the provided token.
    """
    token = request.json.get("token")
    if token == AUTH_TOKEN:
        return jsonify({"message": "Token successfully added"}), 200
    return jsonify({"message": "Wrong token added"}), 401  # Unauthorized


# --------------------- New Routes for Pin 6 Control ---------------------
@app.route("/turn_on_pin6", methods=["POST"])
async def turn_on_pin6():
    """
    Control Pin 6 on the Arduino to turn it on (custom logic).
    """
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{DEVICE_IP}/turn_on_pin6",
                headers={"X-Auth-Token": AUTH_TOKEN},
                timeout=2.0,
            )
        return jsonify({"status": "Pin 6 ON"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Handle errors


@app.route("/turn_off_pin6", methods=["POST"])
async def turn_off_pin6():
    """
    Control Pin 6 on the Arduino to turn it off (custom logic).
    """
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{DEVICE_IP}/turn_off_pin6",
                headers={"X-Auth-Token": AUTH_TOKEN},
                timeout=2.0,
            )
        return jsonify({"status": "Pin 6 OFF"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Handle errors


# --------------------- SocketIO Events ---------------------
@socketio.on("connect")
def handle_connect():
    """
    Handle client connection to SocketIO.
    """
    print("Client connected")


@socketio.on("disconnect")
def handle_disconnect():
    """
    Handle client disconnection from SocketIO.
    """
    print("Client disconnected")


# --------------------- Entry Point ---------------------
if __name__ == "__main__":
    # Start background sensor updates in a separate thread
    Thread(target=background_sensor_updates, daemon=True).start()
    # Run the Flask app with SocketIO support
    socketio.run(app, debug=True, host="0.0.0.0")
