from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from database import db
from models import CommandRequest, Device, DeviceCreateRequest, DeviceUpdateRequest, Command, EndpointCreateRequest, EndpointUpdateRequest, DeviceEndpoint
from routers.users import get_current_user
from datetime import datetime
from bson import ObjectId
from routers.utils import check_house_access, delete_device_data, delete_endpoint_data
from mqtt_client import mqtt
import json

router = APIRouter()

# API tạo thiết bị mới
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_device(
    device_req: DeviceCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    await check_house_access(device_req.houseId, str(current_user["_id"]), required_role="ADMIN")

    new_device = Device(
        houseId=device_req.houseId,
        roomId=device_req.roomId,
        name=device_req.name,
        endpoints=[],
        createdAt=datetime.now()
    )

    result = await db.devices.insert_one(new_device.model_dump(by_alias=True, exclude=["id"]))

    return {
        "message": "Thêm thiết bị thành công",
        "deviceId": str(result.inserted_id)
    }

# API cập nhật device
@router.put("/{device_id}")
async def update_device(
    device_id: str,
    req: DeviceUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    device = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not device:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")

    await check_house_access(device["houseId"], str(current_user["_id"]), required_role="ADMIN")

    update_data = {}

    if req.name:
        update_data["name"] = req.name

    # Cập nhật phòng
    if req.roomId:
        # Kiểm tra phòng có tồn tại và thuộc cùng 1 nhà không
        if req.roomId != device.get("roomId"):
            target_room = await db.rooms.find_one({"_id": ObjectId(req.roomId)})
            if not target_room:
                raise HTTPException(status_code=404, detail="Phòng mới không tồn tại")

            if target_room["houseId"] != device["houseId"]:
                raise HTTPException(status_code=400, detail="Phòng mới không thuộc nhà hiện tại của thiết bị")

            update_data["roomId"] = req.roomId

    if not update_data:
        return {"message": "Không có thông tin nào thay đổi"}

    await db.devices.update_one(
        {"_id": ObjectId(device_id)},
        {"$set": update_data}
    )

    return {"message": "Cập nhật thiết bị thành công"}

# API xóa thiết bị
@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    current_user: dict = Depends(get_current_user)
):
    device = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not device:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")

    # Check quyền
    await check_house_access(device["houseId"], str(current_user["_id"]), required_role="ADMIN")

    await delete_device_data(device_id)

    return None


# API thêm endpoint mới
@router.post("/{device_id}/endpoints", status_code=status.HTTP_201_CREATED)
async def add_endpoint(
    device_id: str,
    endpoint_req: EndpointCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    device = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not device:
        raise HTTPException(status_code=404, detail="Thiết bị không tồn tại")

    await check_house_access(device["houseId"], str(current_user["_id"]), required_role="ADMIN")

    for ep in device.get("endpoints", []):
        if ep["id"] == endpoint_req.id:
            raise HTTPException(status_code=400, detail="ID endpoint đã tồn tại")

    new_endpoint = DeviceEndpoint(
        id=endpoint_req.id,
        name=endpoint_req.name,
        type=endpoint_req.type,
        value=0,
        lastUpdated=datetime.now()
    )

    # Push vào mảng endpoints
    await db.devices.update_one(
        {"_id": ObjectId(device_id)},
        {"$push": {"endpoints": new_endpoint.model_dump()}}
    )

    return {"message": "Đã thêm endpoint mới"}

# API cập nhật endpoint
@router.put("/{device_id}/endpoints/{endpoint_id}")
async def update_endpoint(
    device_id: str,
    endpoint_id: int,
    req: EndpointUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    device = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not device:
        raise HTTPException(status_code=404, detail="Thiết bị không tồn tại")
        
    await check_house_access(device["houseId"], str(current_user["_id"]), required_role="ADMIN")

    # Update logic dùng arrayFilters của MongoDB
    update_fields = {}
    if req.name: update_fields["endpoints.$.name"] = req.name
    if req.type: update_fields["endpoints.$.type"] = req.type

    if not update_fields:
        return {"message": "Không có dữ liệu thay đổi"}

    result = await db.devices.update_one(
        {"_id": ObjectId(device_id), "endpoints.id": endpoint_id},
        {"$set": update_fields}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Endpoint không tìm thấy")

    return {"message": "Cập nhật thành công"}

# API xóa endpoint
@router.delete("/{device_id}/endpoints/{endpoint_id}")
async def delete_endpoint(
    device_id: str,
    endpoint_id: int,
    current_user: dict = Depends(get_current_user)
):
    device = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not device:
        raise HTTPException(status_code=404, detail="Thiết bị không tồn tại")
        
    await check_house_access(device["houseId"], str(current_user["_id"]), required_role="ADMIN")

    await delete_endpoint_data(device_id, endpoint_id)

    return {"message": "Đã xóa endpoint"}


# API lấy danh sách thiết bị theo house
@router.get("/house/{house_id}", response_model=List[Device])
async def get_devices_by_house(
    house_id: str,
    current_user: dict = Depends(get_current_user)
):
    # Kiểm tra quyền access
    await check_house_access(house_id, str(current_user["_id"]))

    devices = await db.devices.find({"houseId": house_id}).to_list(length=100)
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

    devices = await db.devices.find({"roomId": room_id}).to_list(length=100)
    return devices


# API gửi lệnh điều khiển endpoint
@router.post("/{device_id}/command", status_code=status.HTTP_201_CREATED)
async def send_command(
    device_id: str,
    cmd_req: CommandRequest,
    current_user: dict = Depends(get_current_user)
):
    device = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not device:
        raise HTTPException(status_code=404, detail="Thiết bị không tồn tại")

    await check_house_access(device["houseId"], str(current_user["_id"]))

    new_command = Command(
        commandId=str(ObjectId()),
        deviceId=device_id,
        endpointId=cmd_req.endpointId,
        command=cmd_req.command,
        payload=cmd_req.payload,
        status="PENDING",
        createdAt=datetime.now()
    )

    await db.commands.insert_one(new_command.model_dump(by_alias=True, exclude=["id"]))

    # Gửi lệnh qua MQTT
    room_id = device.get("roomId")
    if not room_id:
        raise HTTPException(status_code=400, detail="Thiết bị chưa được gán vào phòng")

    payload = {}

    target_val = 0
    if cmd_req.command == "TURN_ON":
        target_val = 1
    elif cmd_req.command == "TURN_OFF":
        target_val = 0

    # Tạo payload đầy đủ cho tất cả các endpoint (device1, device2, device3)
    for i in range(1, 4):
        key = f"device{i}"

        # Nếu i trùng với endpoint đang điều khiển -> lấy giá trị mới
        if i == cmd_req.endpointId:
            payload[key] = target_val
        else:
            # Nếu không phải -> tìm giá trị hiện tại trong DB
            # Mặc định là 0 nếu không tìm thấy trong DB
            current_val = 0

            # Quét endpoints trong DB để tìm id tương ứng
            for ep in device.get("endpoints", []):
                if ep["id"] == i:
                    if ep.get("value") == 1: 
                        current_val = 1
                    break
            
            payload[key] = current_val

    topic = f"{room_id}/device"
    mqtt.publish(topic, json.dumps(payload))

    return {
        "message": "Đã gửi lệnh gộp xuống thiết bị", 
        "mqtt_topic": topic, 
        "payload": payload
    }

# API lấy lịch sử lệnh
@router.get("/{device_id}/history")
async def get_device_history(
    device_id: str,
    limit: int = 20, # Mặc định lấy 20 lệnh gần nhất
    skip: int = 0, # Dùng để load more (phân trang)
    current_user: dict = Depends(get_current_user)
):
    # Check quyền truy cập thiết bị
    device = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not device:
        raise HTTPException(status_code=404, detail="Thiết bị không tồn tại")

    await check_house_access(device["houseId"], str(current_user["_id"]))

    # Query lịch sử từ bảng commands
    # Sắp xếp theo createdAt giảm dần để lấy lệnh mới nhất trước
    cursor = db.commands.find({"deviceId": device_id}).sort("createdAt", -1).skip(skip).limit(limit)
    
    history = await cursor.to_list(length=limit)

    result = []
    for cmd in history:
        # Tìm tên endpoint để hiển thị
        ep_name = "Unknown"
        for ep in device.get("endpoints", []):
            if ep["id"] == cmd["endpointId"]:
                ep_name = ep["name"]
                break

        result.append({
            "commandId": cmd.get("commandId"),
            "endpointId": cmd["endpointId"],
            "endpointName": ep_name,
            "command": cmd["command"], # TURN_ON, TURN_OFF
            "status": cmd["status"], # PENDING, SENT...
            "createdAt": cmd["createdAt"],
            "ackedAt": cmd.get("ackedAt") # Thời điểm thiết bị phản hồi
        })

    return result