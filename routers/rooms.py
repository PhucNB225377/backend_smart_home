from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from database import db
from models import Room, RoomCreateRequest, RoomUpdateRequest
from routers.users import get_current_user
from datetime import datetime
from bson import ObjectId
from routers.utils import check_house_access, delete_room_data

router = APIRouter()

# API tạo phòng mới
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_room(
    room_req: RoomCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    # Kiểm tra quyền access
    await check_house_access(room_req.houseId, str(current_user["_id"]), required_role="ADMIN")

    new_room = Room(
        houseId=room_req.houseId,
        name=room_req.name,
        floor=room_req.floor,
        createdAt=datetime.now()
    )

    result = await db.rooms.insert_one(new_room.model_dump(by_alias=True, exclude=["id"]))

    return {
        "message": "Tạo phòng thành công", 
        "roomId": str(result.inserted_id),
        "houseId": room_req.houseId
    }

# API lấy danh sách phòng theo houseId
@router.get("/{house_id}", response_model=List[Room])
async def get_rooms_by_house(
    house_id: str,
    current_user: dict = Depends(get_current_user)
):
    # Kiểm tra quyền access
    await check_house_access(house_id, str(current_user["_id"]))

    rooms_cursor = db.rooms.find({"houseId": house_id})
    rooms = await rooms_cursor.to_list(length=100)
    return rooms

# API cập nhật phòng
@router.put("/{room_id}")
async def update_room(
    room_id: str,
    room_req: RoomUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    room = await db.rooms.find_one({"_id": ObjectId(room_id)})
    if not room:
        raise HTTPException(status_code=404, detail="Phòng không tồn tại")

    # Kiểm tra quyền access
    await check_house_access(room["houseId"], str(current_user["_id"]), required_role="ADMIN")

    await db.rooms.update_one(
        {"_id": ObjectId(room_id)},
        {"$set": {"name": room_req.name, "floor": room_req.floor}}
    )
    return {"message": "Cập nhật phòng thành công"}

# API xóa phòng
@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    room = await db.rooms.find_one({"_id": ObjectId(room_id)})
    if not room:
        raise HTTPException(status_code=404, detail="Phòng không tồn tại")

    # Kiểm tra quyền access
    await check_house_access(room["houseId"], str(current_user["_id"]), required_role="ADMIN")

    await delete_room_data(room_id)

    return None