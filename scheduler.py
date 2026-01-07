import asyncio
import json
from datetime import datetime, timedelta
from database import db
from mqtt_client import mqtt

# Hàm hỗ trợ tạo payload gộp 3 thiết bị
def build_fixed_payload(device, target_ep_id, target_val):
    payload = {}
    # Loop cố định 1, 2, 3
    for i in range(1, 4):
        key = f"device{i}"

        if i == target_ep_id:
            payload[key] = target_val
        else:
            # Lấy giá trị cũ từ DB
            current_val = 0
            for ep in device.get("endpoints", []):
                if ep["id"] == i:
                    val_str = str(ep["value"]).upper()
                    if val_str == "ON" or val_str == "1":
                        current_val = 1
                    break
            payload[key] = current_val
    return payload

# Hàm xử lý logic Auto-Off
async def check_auto_off_rules():
    # Lấy các luật đang bật
    rules = await db.auto_off_rules.find({"enabled": True}).to_list(None)
    
    for rule in rules:
        device_id = rule["deviceId"]
        endpoint_id = rule["endpointId"]
        duration = rule["durationSec"]

        # Tìm thiết bị trong DB để kiểm tra trạng thái
        device = await db.devices.find_one({"deviceId": device_id})
        if not device: continue

        # Tìm endpoint đích
        target_ep = next((ep for ep in device["endpoints"] if ep["id"] == endpoint_id), None)
        
        # Check thời gian
        if target_ep and str(target_ep["value"]).upper() != "OFF":
            turn_on_time = target_ep["lastUpdated"]
            if (datetime.now() - turn_on_time).total_seconds() >= duration:
                print(f"Auto-Off: Tắt device{endpoint_id}")
                
                if device.get("roomId"):
                    topic = f"{device['roomId']}/device"
                    # Tắt -> target_val = 0
                    payload = build_fixed_payload(device, endpoint_id, 0)
                    mqtt.publish(topic, json.dumps(payload))
                
                # Cập nhật DB
                await db.devices.update_one(
                    {"deviceId": device_id, "endpoints.id": endpoint_id},
                    {"$set": {"endpoints.$.value": "OFF", "endpoints.$.lastUpdated": datetime.now()}}
                )

# Hàm xử lý Schedule
async def check_schedules():
    now = datetime.now()
    # Tìm các lịch đã đến giờ (hoặc quá giờ) mà chưa chạy
    pending_schedules = await db.schedules.find({
        "enabled": True,
        "nextRunAt": {"$lte": now}
    }).to_list(None)

    for sch in pending_schedules:
        print(f"Schedule: Thực thi lịch {sch['name']}")
        
        # Gửi lệnh MQTT
        device = await db.devices.find_one({"deviceId": sch["deviceId"]})
        if device and device.get("roomId"):
            try:
                action = json.loads(sch["action"])
                cmd = action.get("command")
                
                # Xác định target value
                target_val = 1 if cmd == "TURN_ON" else 0
                if cmd == "SET_VALUE": target_val = int(action.get("payload", 0))

                # Gửi lệnh gộp
                topic = f"{device['roomId']}/device"
                payload = build_fixed_payload(device, sch["endpointId"], target_val)
                mqtt.publish(topic, json.dumps(payload))
            except Exception as e:
                print(f"Lỗi schedule: {e}")

        # Tính toán thời gian chạy tiếp theo
        updates = {}
        if sch["scheduleType"] == "ONCE":
            updates["enabled"] = False # Chạy 1 lần rồi tắt
        elif sch["scheduleType"] == "DAILY":
            updates["nextRunAt"] = sch["nextRunAt"] + timedelta(days=1)
        elif sch["scheduleType"] == "WEEKLY":
            updates["nextRunAt"] = sch["nextRunAt"] + timedelta(weeks=1)
            
        if updates:
            await db.schedules.update_one({"_id": sch["_id"]}, {"$set": updates})

# Vòng lặp chính (Background Task)
async def run_scheduler():
    print("Scheduler Service đã khởi động...")
    while True:
        try:
            await check_auto_off_rules()
            await check_schedules()
        except Exception as e:
            print(f"Lỗi Scheduler: {e}")
        
        # Nghỉ 10 giây rồi quét tiếp
        await asyncio.sleep(10)