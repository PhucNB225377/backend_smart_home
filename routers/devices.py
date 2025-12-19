from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from database import db
from models import CommandRequest, Device, DeviceCreateRequest, DeviceStateCurrent, Command
from routers.users import get_current_user
from datetime import datetime
from bson import ObjectId
from routers.utils import check_house_access, delete_device_data
from mqtt_client import mqtt

router = APIRouter()

# API tạo thiết bị mới (Provisioning)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_device(
    device_req: DeviceCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    # Kiểm tra deviceId đã tồn tại chưa
    existing_device = await db.devices.find_one({"deviceId": device_req.deviceId})
    if existing_device:
        raise HTTPException(status_code=400, detail="Mã thiết bị này đã tồn tại trong hệ thống")

    # Kiểm tra quyền access
    await check_house_access(device_req.houseId, str(current_user["_id"]), required_role="ADMIN")

    new_device = Device(
        deviceId=device_req.deviceId,
        houseId=device_req.houseId,
        roomId=device_req.roomId,
        typeCode=device_req.typeCode,
        name=device_req.name,
        serialNo=device_req.serialNo,
        createdAt=datetime.now()
    )
    
    # Insert device
    result = await db.devices.insert_one(new_device.model_dump(by_alias=True, exclude=["id"]))
    
    # Khởi tạo device state mặc định
    initial_state = DeviceStateCurrent(
        deviceId=device_req.deviceId,
        power=False,
        updatedAt=datetime.now()
    )
    await db.device_state_current.insert_one(initial_state.model_dump(by_alias=True, exclude=["id"]))

    return {
        "message": "Thêm thiết bị thành công",
        "deviceId": device_req.deviceId,
        "id": str(result.inserted_id)
    }

# API lấy danh sách thiết bị theo house
@router.get("/house/{house_id}", response_model=List[Device])
async def get_devices_by_house(
    house_id: str,
    current_user: dict = Depends(get_current_user)
):
    # Kiểm tra quyền access
    await check_house_access(house_id, str(current_user["_id"]))

    devices_cursor = db.devices.find({"houseId": house_id})
    devices = await devices_cursor.to_list(length=100)
    return devices

# API lấy danh sách thiết bị theo room
@router.get("/room/{room_id}", response_model=List[Device])
async def get_devices_by_room(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    room = await db.rooms.find_one({"_id": ObjectId(room_id)})
    if not room:
        raise HTTPException(status_code=404, detail="Phòng không tồn tại")

    # Kiểm tra quyền access
    await check_house_access(room["houseId"], str(current_user["_id"]))

    devices_cursor = db.devices.find({"roomId": room_id})
    devices = await devices_cursor.to_list(length=100)
    return devices

# API cập nhật thông tin thiết bị
@router.put("/{device_id}")
async def update_device_info(
    device_id: str,
    update_data: dict,
    current_user: dict = Depends(get_current_user)
):
    device = await db.devices.find_one({"deviceId": device_id})
    if not device:
        raise HTTPException(status_code=404, detail="Thiết bị không tồn tại")
    
    # Check quyền
    await check_house_access(device["houseId"], str(current_user["_id"]), required_role="ADMIN")

    # Các trường có thể update
    allowed_fields = {"name", "roomId", "isOnline"}
    data_to_update = {k: v for k, v in update_data.items() if k in allowed_fields}

    if not data_to_update:
        raise HTTPException(status_code=400, detail="Không có dữ liệu hợp lệ để cập nhật")

    result = await db.devices.update_one(
        {"deviceId": device_id},
        {"$set": data_to_update}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị hoặc dữ liệu không thay đổi")

    return {"message": "Cập nhật thành công"}

# API xóa thiết bị
@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    current_user: dict = Depends(get_current_user)
):
    device = await db.devices.find_one({"deviceId": device_id})
    if not device:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")

    # Check quyền
    await check_house_access(device["houseId"], str(current_user["_id"]), required_role="ADMIN")

    await delete_device_data(device_id)

    return None

# API lấy state của device
@router.get("/{device_id}/state")
async def get_device_state(
    device_id: str,
    current_user: dict = Depends(get_current_user)
):
    device = await db.devices.find_one({"deviceId": device_id})
    if not device:
        raise HTTPException(status_code=404, detail="Thiết bị không tồn tại")

    await check_house_access(device["houseId"], str(current_user["_id"]))

    state = await db.device_state_current.find_one({"deviceId": device_id})
    if not state:
        return {
            "deviceId": device_id,
            "power": False,
            "isOnline": False
        }

    state["_id"] = str(state["_id"])
    state["isOnline"] = device.get("isOnline", False)
    state["lastSeenAt"] = device.get("lastSeenAt")

    return state

# API gửi lệnh điều khiển thiết bị
@router.post("/{device_id}/command", status_code=status.HTTP_201_CREATED)
async def send_command(
    device_id: str,
    cmd_req: CommandRequest,
    current_user: dict = Depends(get_current_user)
):
    device = await db.devices.find_one({"deviceId": device_id})
    if not device:
        raise HTTPException(status_code=404, detail="Thiết bị không tồn tại")

    await check_house_access(device["houseId"], str(current_user["_id"]))

    new_command = Command(
        commandId=str(ObjectId()),
        deviceId=device_id,
        command=cmd_req.command,
        payload=cmd_req.payload,
        status="PENDING",
        createdAt=datetime.now()
    )

    await db.commands.insert_one(new_command.model_dump(by_alias=True, exclude=["id"]))

    # Gửi lệnh qua MQTT
    topic = f"devices/{device_id}/set"

    payload = {
        "command": cmd_req.command,
        "payload": cmd_req.payload
    }

    mqtt.publish(topic, str(payload))

    return {"message": "Đã gửi lệnh xuống thiết bị", "mqtt_topic": topic}