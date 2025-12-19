from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from database import db
from models import AutoOffRule, Schedule, AutoOffRuleCreateRequest, ScheduleCreateRequest
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

# Tạo / cập nhật luật tự tắt cho 1 thiết bị
@router.post("/auto-off", status_code=status.HTTP_200_OK)
async def set_auto_off_rule(
    rule_req: AutoOffRuleCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    await verify_device_ownership(rule_req.deviceId, str(current_user["_id"]))

    rule_data = {
        "deviceId": rule_req.deviceId,
        "enabled": rule_req.enabled,
        "durationSec": rule_req.durationSec,
        "updatedAt": datetime.now()
    }

    await db.auto_off_rules.update_one(
        {"deviceId": rule_req.deviceId},
        {"$set": rule_data},
        upsert=True
    )

    return {"message": "Đã lưu cấu hình tự động tắt"}

# Lấy cấu hình tự tắt của 1 thiết bị
@router.get("/auto-off/{device_id}")
async def get_auto_off_rule(
    device_id: str,
    current_user: dict = Depends(get_current_user)
):
    await verify_device_ownership(device_id, str(current_user["_id"]))
    
    rule = await db.auto_off_rules.find_one({"deviceId": device_id})
    if not rule:
        return {"enabled": False, "durationSec": 0}
    
    rule["_id"] = str(rule["_id"])

    return rule


# Tạo lịch hẹn
@router.post("/schedules", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    sch_req: ScheduleCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    await verify_device_ownership(sch_req.deviceId, str(current_user["_id"]))

    new_schedule = Schedule(
        deviceId=sch_req.deviceId,
        name=sch_req.name,
        enabled=sch_req.enabled,
        action=sch_req.action,
        scheduleType=sch_req.scheduleType,
        nextRunAt=sch_req.nextRunAt,
        timezone=sch_req.timezone
    )

    result = await db.schedules.insert_one(new_schedule.model_dump(by_alias=True, exclude=["id"]))

    return {"message": "Tạo lịch hẹn thành công", "scheduleId": str(result.inserted_id)}

# Lấy danh sách lịch hẹn của 1 thiết bị
@router.get("/schedules/{device_id}", response_model=List[Schedule])
async def get_device_schedules(
    device_id: str,
    current_user: dict = Depends(get_current_user)
):
    await verify_device_ownership(device_id, str(current_user["_id"]))
    
    schedules_cursor = db.schedules.find({"deviceId": device_id})
    schedules = await schedules_cursor.to_list(length=100)

    schedules["_id"] = str(schedules["_id"])
    return schedules

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