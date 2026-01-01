from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from database import db
from models import AutoOffRule, Schedule, AutoOffRuleCreateRequest, ScheduleCreateRequest, ScheduleUpdateRequest
from routers.users import get_current_user
from datetime import datetime
from bson import ObjectId
from routers.utils import check_house_access

router = APIRouter()

# Hàm phụ trợ check quyền sở hữu thiết bị
async def verify_device_ownership(device_id: str, user_id: str):
    device = await db.devices.find_one({"deviceId": device_id})
    if not device:
        raise HTTPException(status_code=404, detail="Thiết bị không tồn tại")

    await check_house_access(device["houseId"], user_id, required_role="ADMIN")

    return device

# Tạo / cập nhật luật tự tắt cho 1 endpoint
@router.post("/{device_id}/auto-off", status_code=status.HTTP_200_OK)
async def set_auto_off_rule(
    device_id: str,
    rule_req: AutoOffRuleCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    await verify_device_ownership(device_id, str(current_user["_id"]))

    rule_data = {
        "deviceId": device_id,
        "endpointId": rule_req.endpointId,
        "enabled": rule_req.enabled,
        "durationSec": rule_req.durationSec,
        "updatedAt": datetime.now()
    }

    await db.auto_off_rules.update_one(
        {"deviceId": device_id, "endpointId": rule_req.endpointId},
        {"$set": rule_data},
        upsert=True
    )

    return {"message": "Đã lưu cấu hình tự động tắt"}

# Lấy cấu hình tự tắt của 1 thiết bị
@router.get("/{device_id}/auto-off")
async def get_auto_off_rule(
    device_id: str,
    endpoint_id: int,
    current_user: dict = Depends(get_current_user)
):
    await verify_device_ownership(device_id, str(current_user["_id"]))
    
    rule = await db.auto_off_rules.find_one({"deviceId": device_id, "endpointId": endpoint_id})
    if not rule:
        return {"enabled": False, "durationSec": 0}
    
    rule["_id"] = str(rule["_id"])

    return rule


# Tạo lịch hẹn
@router.post("/{device_id}/schedules", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    device_id: str,
    sch_req: ScheduleCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    await verify_device_ownership(device_id, str(current_user["_id"]))

    new_schedule = Schedule(
        deviceId=device_id,
        endpointId=sch_req.endpointId,
        name=sch_req.name,
        enabled=sch_req.enabled,
        action=sch_req.action,
        scheduleType=sch_req.scheduleType,
        nextRunAt=sch_req.nextRunAt,
        timezone=sch_req.timezone
    )

    result = await db.schedules.insert_one(new_schedule.model_dump(by_alias=True, exclude=["id"]))

    return {"message": "Tạo lịch hẹn thành công", "scheduleId": str(result.inserted_id)}

# Lấy danh sách lịch hẹn
@router.get("/schedules/{device_id}", response_model=List[Schedule])
async def get_device_schedules(
    device_id: str,
    endpoint_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    await verify_device_ownership(device_id, str(current_user["_id"]))

    query = {"deviceId": device_id}
    if endpoint_id is not None:
        query["endpointId"] = endpoint_id

    schedules = await db.schedules.find(query).to_list(length=100)

    for sch in schedules:
        sch["_id"] = str(sch["_id"])

    return schedules

# Cập nhật lịch hẹn
@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    update_req: ScheduleUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    schedule = await db.schedules.find_one({"_id": ObjectId(schedule_id)})
    if not schedule:
        raise HTTPException(status_code=404, detail="Lịch hẹn không tồn tại")

    await verify_device_ownership(schedule["deviceId"], str(current_user["_id"]))

    # exclude_unset=True giúp loại bỏ các trường user không gửi
    update_data = update_req.model_dump(exclude_unset=True)

    if not update_data:
        return {"message": "Không có dữ liệu thay đổi"}

    await db.schedules.update_one(
        {"_id": ObjectId(schedule_id)},
        {"$set": update_data}
    )

    return {"message": "Cập nhật lịch hẹn thành công"}

# Xóa lịch hẹn
@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: dict = Depends(get_current_user)
):
    schedule = await db.schedules.find_one({"_id": ObjectId(schedule_id)})
    if not schedule:
        raise HTTPException(status_code=404, detail="Lịch hẹn không tồn tại")
        
    await verify_device_ownership(schedule["deviceId"], str(current_user["_id"]))

    await db.schedules.delete_one({"_id": ObjectId(schedule_id)})
    return {"message": "Đã xóa lịch hẹn"}