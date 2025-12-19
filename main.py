from fastapi import FastAPI
from database import db
from routers import users, houses, rooms, devices, automations, members
from mqtt_client import mqtt
from datetime import datetime
import json

app = FastAPI()

mqtt.init_app(app)

# Đăng ký các Router
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(houses.router, prefix="/houses", tags=["Houses"])
app.include_router(rooms.router, prefix="/rooms", tags=["Rooms"])
app.include_router(devices.router, prefix="/devices", tags=["Devices"])
app.include_router(automations.router, prefix="/automations", tags=["Automations"])
app.include_router(members.router, prefix="/members", tags=["Members"])

# MQTT Event Handlers
@mqtt.on_connect()
def connect(client, flags, rc, properties):
    print("Đã kết nối tới MQTT Broker!")
    mqtt.client.subscribe("devices/+/state")

@mqtt.on_message()
async def message(client, topic, payload, qos, properties):
    try:
        payload_str = payload.decode()
        print(f"Received message: {topic} -> {payload_str}")

        parts = topic.split("/")
        if len(parts) == 3 and parts[2] == "state":
            device_id = parts[1]

            # Kiểm tra thiết bị trong DB
            device = await db.devices.find_one({"deviceId": device_id})
            if not device:
                print(f"Cảnh báo: Nhận dữ liệu từ thiết bị lạ {device_id}.")
                return

            data = json.loads(payload_str)

            update_data = {
                "updatedAt": datetime.now(),
                "source": "DEVICE"
            }
            if "power" in data:
                update_data["power"] = data["power"]
            if "value" in data:
                update_data["value"] = str(data["value"])
            if "sensors" in data:
                update_data["sensors"] = json.dumps(data["sensors"])

            await db.device_state_current.update_one(
                {"deviceId": device_id},
                {"$set": update_data},
                upsert=True
            )

            await db.devices.update_one(
                {"deviceId": device_id},
                {"$set": {"isOnline": True, "lastSeenAt": datetime.now()}}
            )
            print(f"Đã cập nhật trạng thái cho {device_id}")

    except Exception as e:
        print(f"Lỗi xử lý MQTT: {e}")