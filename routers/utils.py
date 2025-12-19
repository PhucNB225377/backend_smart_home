from fastapi import HTTPException
from database import db
from models import Device
from bson import ObjectId

# Định nghĩa cấp độ quyền hạn
ROLE_LEVELS = {
    "MEMBER": 1,
    "ADMIN": 2,
    "OWNER": 3
}

# Hàm kiểm tra quyền truy cập nhà
async def check_house_access(house_id: str, user_id: str, required_role: str = "MEMBER"):    
    # Check Ownership
    house = await db.houses.find_one({"_id": ObjectId(house_id)})
    if not house:
        raise HTTPException(status_code=404, detail="Nhà không tồn tại")
        
    if house["ownerId"] == user_id:
        return True

    # Check bảng home_members
    member = await db.home_members.find_one({
        "houseId": house_id,
        "userId": user_id,
        "status": "ACCEPTED"
    })
    
    if not member:
        raise HTTPException(status_code=403, detail="Bạn không phải thành viên của nhà này")

    # Check quyền hạn
    user_role_level = ROLE_LEVELS.get(member["role"], 0)
    required_level = ROLE_LEVELS.get(required_role, 1)

    if user_role_level < required_level:
        raise HTTPException(
            status_code=403, 
            detail=f"Bạn cần quyền {required_role} để thực hiện thao tác này"
        )
        
    return True


# Hàm xử lý xóa dữ liệu liên quan
async def delete_device_data(device_id: str):
    await db.device_state_current.delete_one({"deviceId": device_id})
    await db.commands.delete_many({"deviceId": device_id})
    await db.auto_off_rules.delete_one({"deviceId": device_id})
    await db.schedules.delete_many({"deviceId": device_id})
    await db.devices.delete_one({"deviceId": device_id})
    print(f"Đã xóa thiết bị: {device_id}")

async def delete_room_data(room_id: str):
    devices_cursor = db.devices.find({"roomId": room_id})
    async for device in devices_cursor:
        await delete_device_data(device["deviceId"])

    await db.rooms.delete_one({"_id": ObjectId(room_id)})

    print(f"Đã xóa phòng: {room_id}")

async def delete_house_data(house_id: str):
    devices_cursor = db.devices.find({"houseId": house_id})
    async for device in devices_cursor:
        await delete_device_data(device["deviceId"])

    await db.rooms.delete_many({"houseId": house_id})

    await db.home_members.delete_many({"houseId": house_id})

    await db.houses.delete_one({"_id": ObjectId(house_id)})

    print(f"Đã xóa nhà: {house_id}")