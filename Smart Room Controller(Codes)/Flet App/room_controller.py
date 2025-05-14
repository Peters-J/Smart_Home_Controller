# 217000981 JJ PETERS - Assignment 4 - Smart Room Controller

# Import required libraries
import flet as ft  # Flet for UI
import httpx  # Async HTTP client
import asyncio  # For async loops
import socketio  # For real-time Socket.IO connection

# Backend Flask server URL (make sure it matches your Flask IP)
FLASK_BACKEND = "http://127.0.0.1:5000"
AUTH_TOKEN = "1234567"  # Authorization token for protected routes

# Initialize Socket.IO client
sio = socketio.Client()


# Main Flet function to define UI
def main(page: ft.Page):
    page.title = "Smart Room Dashboard"
    page.auto_scroll = True  # Enable auto-scroll

    # UI text elements to display sensor states
    pir_text = ft.Text("PIR: ")
    ldr_text = ft.Text("LDR: ")
    pot_text = ft.Text("Potentiometer: ")
    fan_speed_text = ft.Text("Fan PWM: ")
    light_state_text = ft.Text("Light: ")

    # UI elements to control outputs
    light_switch = ft.Switch(label="Light", value=False)  # Toggle for light
    fan_slider = ft.Slider(
        min=0, max=255, divisions=255, label="{value}"
    )  # PWM fan control

    # Sensor data history buffers
    history_length = 50
    ldr_data, pot_data, fan_data = [], [], []

    # Table to display recent sensor data
    data_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("LDR")),
            ft.DataColumn(ft.Text("Potentiometer")),
            ft.DataColumn(ft.Text("Fan PWM")),
        ],
        rows=[],
        expand=True,
    )

    # Add components to the page layout
    page.add(
        ft.Column(
            [
                pir_text,
                ldr_text,
                pot_text,
                fan_speed_text,
                light_state_text,
                ft.Row([light_switch]),
                ft.Text("Fan Control Slider:"),
                fan_slider,
                ft.Text("Sensor Data Table:"),
                data_table,
            ]
        )
    )

    # Socket.IO event when connected
    @sio.event
    def connect():
        print("Connected to Flask server")

    # Socket.IO event when disconnected
    @sio.event
    def disconnect():
        print("Disconnected from Flask server")

    # Socket.IO event for receiving sensor updates
    @sio.event
    def sensor_update(data):
        # Update UI with sensor values from backend
        pir_text.value = (
            f"PIR: {'Person Detected' if data['pir'] else 'Person Not Detected'}"
        )
        ldr_text.value = f"LDR: {data['ldr']}"
        pot_text.value = f"Potentiometer: {data['pot']}"
        fan_speed_text.value = f"Fan PWM: {data['fan_pwm']}"
        light_state_text.value = f"Light: {'On' if data['light_state'] else 'Off'}"
        light_switch.value = bool(data["light_state"])
        fan_slider.value = data["fan_pwm"]

        # Store latest values in history
        ldr_data.append(data["ldr"])
        pot_data.append(data["pot"])
        fan_data.append(data["fan_pwm"])

        # Limit history to fixed length
        if len(ldr_data) > history_length:
            ldr_data.pop(0)
            pot_data.pop(0)
            fan_data.pop(0)

        # Update data table with latest values
        data_table.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(ldr_data[-1]))),
                    ft.DataCell(ft.Text(str(pot_data[-1]))),
                    ft.DataCell(ft.Text(str(fan_data[-1]))),
                ]
            )
        ]
        page.update()

    # Connect to Flask server via Socket.IO
    sio.connect(FLASK_BACKEND)

    # Async function to periodically get data from REST endpoint (backup to socket)
    async def update_ui():
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{FLASK_BACKEND}/sensors", timeout=2)
                if r.status_code == 200:
                    data = r.json()
                else:
                    raise ValueError(f"Unexpected response: {r.text}")

            # Update all UI components with data
            pir_text.value = (
                f"PIR: {'Person Detected' if data['pir'] else 'Person Not Detected'}"
            )
            ldr_text.value = f"LDR: {data['ldr']}"
            pot_text.value = f"Potentiometer: {data['pot']}"
            fan_speed_text.value = f"Fan PWM: {data['fan_pwm']}"
            light_state_text.value = f"Light: {'On' if data['light_state'] else 'Off'}"
            light_switch.value = bool(data["light_state"])
            fan_slider.value = data["fan_pwm"]

            # Store history
            ldr_data.append(data["ldr"])
            pot_data.append(data["pot"])
            fan_data.append(data["fan_pwm"])

            if len(ldr_data) > history_length:
                ldr_data.pop(0)
                pot_data.pop(0)
                fan_data.pop(0)

            data_table.rows = [
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(ldr_data[-1]))),
                        ft.DataCell(ft.Text(str(pot_data[-1]))),
                        ft.DataCell(ft.Text(str(fan_data[-1]))),
                    ]
                )
            ]
            page.update()

        except Exception as e:
            print(f"[UI Error] {e}")

    # Infinite loop to refresh data periodically (every second)
    async def auto_refresh():
        while True:
            await update_ui()
            await asyncio.sleep(1)

    # Send fan speed to backend via POST
    async def set_fan_speed(speed):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{FLASK_BACKEND}/set_fan",
                    json={"fan_speed": int(float(speed))},
                    timeout=2,
                )
            fan_speed_text.value = f"Fan PWM: {int(speed)}"
            page.update()
        except Exception as e:
            print(f"[Fan Error] {e}")

    # Send light state to backend via POST
    async def toggle_light(state):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{FLASK_BACKEND}/toggle_light",
                    json={"state": bool(state)},
                    timeout=2,
                )
            light_state_text.value = f"Light: {'On' if state else 'Off'}"
            page.update()
        except Exception as e:
            print(f"[Light Error] {e}")

    # Handler for fan slider changes
    def on_slider_change(e):
        async def task():
            await set_fan_speed(e.control.value)

        page.run_task(task)  # Run as async task

    # Handler for light switch changes
    def on_light_switch_change(e):
        async def task():
            await toggle_light(e.control.value)

        page.run_task(task)

    # Link UI events to handlers
    fan_slider.on_change = on_slider_change
    light_switch.on_change = on_light_switch_change

    # Start auto refresh task
    page.run_task(auto_refresh)


# Launch the Flet app
ft.app(target=main)
