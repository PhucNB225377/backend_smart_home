from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from database import db
from models import HomeMember, InviteMemberRequest, UpdateMemberRole
from routers.users import get_current_user
from routers.utils import check_house_access
from bson import ObjectId
from datetime import datetime

router = APIRouter()

# API mời thành viên mới
@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_member(
    req: InviteMemberRequest,
    current_user: dict = Depends(get_current_user)
):
    house = await db.houses.find_one({"_id": ObjectId(req.houseId)})
    if not house:
        raise HTTPException(status_code=404, detail="Nhà không tồn tại")

    # Tìm user được mời qua email
    target_user = await db.users.find_one({"email": req.email})
    if not target_user:
        raise HTTPException(status_code=404, detail="Email chưa đăng ký tài khoản")

    target_user_id = str(target_user["_id"])

    # Không mời chính chủ nhà
    if str(house["ownerId"]) == target_user_id:
        raise HTTPException(status_code=400, detail="Không cần mời chủ nhà.")

    if req.role == "OWNER":
        raise HTTPException(status_code=400, detail="Không mời quyền chủ nhà.")

    await check_house_access(req.houseId, str(current_user["_id"]), required_role="OWNER")

    # Kiểm tra xem đã mời / đã là thành viên chưa
    existing_member = await db.home_members.find_one({
        "houseId": req.houseId,
        "userId": target_user_id
    })

    if existing_member:
        if existing_member["status"] == "ACCEPTED":
            raise HTTPException(status_code=400, detail="Đã là thành viên")
        else:
            raise HTTPException(status_code=400, detail="Đã gửi lời mời, đang chờ chấp nhận")

    # Tạo lời mời
    new_member = HomeMember(
        houseId=req.houseId,
        userId=target_user_id,
        role=req.role,
        status="PENDING",
        invitedBy=str(current_user["_id"]),
        joinedAt=datetime.now()
    )

    await db.home_members.insert_one(new_member.model_dump(by_alias=True, exclude=["id"]))

    return {"message": f"Đã gửi lời mời tới {req.email}"}


# API xem danh sách lời mời
@router.get("/invitations")
async def get_invitations(current_user: dict = Depends(get_current_user)):
    invites_cursor = db.home_members.find({
        "userId": str(current_user["_id"]),
        "status": "PENDING"
    })
    invites = await invites_cursor.to_list(length=100)

    result = []
    for inv in invites:
        house = await db.houses.find_one({"_id": ObjectId(inv["houseId"])})
        owner = await db.users.find_one({"_id": ObjectId(house["ownerId"])})
        if house:
            inv["_id"] = str(inv["_id"])
            inv["houseName"] = house["name"]
            inv["ownerName"] = owner["fullName"]
            result.append(inv)
            
    return result


# API chấp nhận lời mời
@router.put("/invitations/{member_id}/accept")
async def accept_invitation(
    member_id: str,
    current_user: dict = Depends(get_current_user)
):
    invite = await db.home_members.find_one({"_id": ObjectId(member_id)})
    if not invite:
        raise HTTPException(status_code=404, detail="Lời mời không tồn tại")

    if invite["userId"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Lời mời này không phải của bạn")

    # Update
    await db.home_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"status": "ACCEPTED", "joinedAt": datetime.now()}}
    )
    return {"message": "Đã chấp nhận lời mời"}

# API từ chối lời mời
@router.put("/invitations/{member_id}/reject")
async def reject_invitation(
    member_id: str,
    current_user: dict = Depends(get_current_user)
):
    invite = await db.home_members.find_one({"_id": ObjectId(member_id)})
    if not invite:
        raise HTTPException(status_code=404, detail="Lời mời không tồn tại")

    if invite["userId"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Lời mời này không phải của bạn")

    await db.home_members.delete_one({"_id": ObjectId(member_id)})
    return {"message": "Đã từ chối lời mời"}


# API lấy danh sách thành viên trong nhà
@router.get("/{house_id}")
async def get_house_members(
    house_id: str,
    current_user: dict = Depends(get_current_user)
):
    await check_house_access(house_id, str(current_user["_id"]))

    members_cursor = db.home_members.find({"houseId": house_id})
    members = await members_cursor.to_list(length=100)

    result = []
    for m in members:
        user = await db.users.find_one({"_id": ObjectId(m["userId"])})
        if user:
            m["_id"] = str(m["_id"])
            m["email"] = user["email"]
            m["fullName"] = user["fullName"]
            result.append(m)

    house = await db.houses.find_one({"_id": ObjectId(house_id)})
    owner = await db.users.find_one({"_id": ObjectId(house["ownerId"])})
    if owner:
        result.insert(0, {
            "userId": str(owner["_id"]),
            "role": "OWNER",
            "status": "ACCEPTED",
            "email": owner["email"],
            "fullName": owner["fullName"]
        })

    return result


# API cập nhật vai trò thành viên
@router.put("/{member_id}/role")
async def update_member_role(
    member_id: str,
    req: UpdateMemberRole,
    current_user: dict = Depends(get_current_user)
):
    member_record = await db.home_members.find_one({"_id": ObjectId(member_id), "houseId": req.houseId})
    if not member_record:
        raise HTTPException(status_code=404, detail="Thành viên không tồn tại")

    if req.role == "OWNER":
        raise HTTPException(status_code=400, detail="Không chuyển quyền chủ nhà.")

    await check_house_access(req.houseId, str(current_user["_id"]), required_role="OWNER")

    await db.home_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"role": req.role}}
    )
    return {"message": "Cập nhật vai trò thành viên thành công"}


# API Xóa thành viên
@router.delete("/{member_id}/{house_id}")
async def remove_member(
    member_id: str,
    house_id: str,
    current_user: dict = Depends(get_current_user)
):
    member_record = await db.home_members.find_one({"_id": ObjectId(member_id), "houseId": house_id})
    if not member_record:
        raise HTTPException(status_code=404, detail="Thành viên không tồn tại")

    await check_house_access(house_id, str(current_user["_id"]), required_role="OWNER")
    
    await db.home_members.delete_one({"_id": ObjectId(member_id), "houseId": house_id})
    return {"message": "Đã xóa thành viên khỏi nhà"}


# API tự rời khỏi nhà
@router.delete("/leave/{house_id}")
async def leave_house(
    house_id: str,
    current_user: dict = Depends(get_current_user)
):
    # Check xem có phải chủ nhà không
    house = await db.houses.find_one({"_id": ObjectId(house_id)})
    if house and str(house["ownerId"]) == str(current_user["_id"]):
        raise HTTPException(
            status_code=400, 
            detail="Chủ nhà không thể rời đi"
        )
    
    member_record = await db.home_members.find_one({
        "houseId": house_id, 
        "userId": str(current_user["_id"])
    })
    
    if not member_record:
        raise HTTPException(status_code=404, detail="Bạn không phải thành viên nhà này")

    await db.home_members.delete_one({"_id": member_record["_id"]})

    return {"message": "Đã rời khỏi nhà thành công"}