from fastapi import FastAPI
from database import db
from routers import users, houses, rooms, devices, automations, members
from mqtt_client import mqtt
from datetime import datetime
import json

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Server is running..."}


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
    print("Đã kết nối tới MQTT Broker (HiveMQ)!")
    mqtt.client.subscribe("+/+/device")

@mqtt.on_message()
async def message(client, topic, payload, qos, properties):
    try:
        payload_str = payload.decode()
        print(f"Received message: {topic} -> {payload_str}")

        parts = topic.split("/")
        if len(parts) == 3 and parts[2] == "device":
            house_id = parts[0]
            room_id = parts[1]

            try:
                data = json.loads(payload_str)
            except json.JSONDecodeError:
                print("Lỗi: Payload không phải JSON")
                return
            
            # Lấy thông tin endpoint từ payload
            endpoint_id = data.get("id")
            new_value = data.get("val")

            if endpoint_id is None or new_value is None:
                return

            # Tìm thiết bị theo house_id và room_id
            result = await db.devices.update_one(
                {
                    "houseId": house_id,
                    "roomId": room_id,
                    "endpoints.id": endpoint_id
                },
                {
                    "$set": {
                        "endpoints.$.value": new_value,
                        "endpoints.$.lastUpdated": datetime.now(),
                        "isOnline": True,
                        "lastSeenAt": datetime.now()
                    }
                }
            )

            if result.matched_count > 0:
                print(f"Đã update: Nhà {house_id} - Phòng {room_id} - Endpoint {endpoint_id}")
            else:
                print(f"Không tìm thấy thiết bị tại Nhà {house_id}, Phòng {room_id} hoặc Endpoint sai ID.")

    except Exception as e:
        print(f"Lỗi xử lý MQTT: {e}")