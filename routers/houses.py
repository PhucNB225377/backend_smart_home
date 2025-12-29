from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from database import db
from models import House, HouseCreateRequest
from routers.users import get_current_user
from datetime import datetime
from bson import ObjectId
from routers.utils import check_house_access, delete_house_data

router = APIRouter()

# API tạo nhà mới
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_house(
    house_req: HouseCreateRequest,
    current_user: dict = Depends(get_current_user) # Login rồi mới tạo nhà
):
    # Chuẩn bị dữ liệu nhà
    new_house = House(
        ownerId=str(current_user["_id"]),
        name=house_req.name,
        address=house_req.address,
        mapId=house_req.mapId,
        createdAt=datetime.now()
    )

    # Lưu vào DB
    result = await db.houses.insert_one(new_house.model_dump(by_alias=True, exclude=["id"]))

    return {
        "message": "Tạo nhà thành công", 
        "houseId": str(result.inserted_id),
        "owner": current_user["email"]
    }

# API lấy danh sách nhà của user
@router.get("/", response_model=List[House])
async def get_houses(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])

    owned_houses_cursor = db.houses.find({"ownerId": user_id})
    owned_houses = await owned_houses_cursor.to_list(length=100)

    members_cursor = db.home_members.find({"userId": user_id, "status": "ACCEPTED"})
    members = await members_cursor.to_list(length=100)

    joined_house_ids = [ObjectId(m["houseId"]) for m in members]

    joined_houses_cursor = db.houses.find({"_id": {"$in": joined_house_ids}})
    joined_houses = await joined_houses_cursor.to_list(length=100)

    return owned_houses + joined_houses

# API cập nhật thông tin nhà
@router.put("/{house_id}")
async def update_house(
    house_id: str,
    house_req: HouseCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    # Kiểm tra quyền access
    await check_house_access(house_id, str(current_user["_id"]), required_role="ADMIN")

    await db.houses.update_one(
        {"_id": ObjectId(house_id)},
        {"$set": {"name": house_req.name, "address": house_req.address, "mapId": house_req.mapId}}
    )
    return {"message": "Cập nhật nhà thành công"}

# API xóa nhà
@router.delete("/{house_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_house(
    house_id: str,
    current_user: dict = Depends(get_current_user)
):
    # Kiểm tra quyền sở hữu
    house = await db.houses.find_one({"_id": ObjectId(house_id), "ownerId": str(current_user["_id"])})
    if not house:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhà hoặc bạn không có quyền")

    await delete_house_data(house_id)
    
    return None