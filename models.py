from pydantic import BaseModel, Field, EmailStr, BeforeValidator
from typing import Optional
from datetime import datetime
from typing_extensions import Annotated

# Chuyển ObjectId của MongoDB thành String
PyObjectId = Annotated[str, BeforeValidator(str)]

# Model cơ sở cho các document trong MongoDB
class MongoBaseModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda dt: dt.isoformat()}

# User
class User(MongoBaseModel):
    email: EmailStr
    passwordHash: str
    fullName: str
    phone: Optional[str] = None
    status: str = "ACTIVE" # Mặc định là Active
    createdAt: datetime = Field(default_factory=datetime.now) # Mặc định tự lấy thời gian hiện tại

# RefreshToken
class RefreshToken(MongoBaseModel):
    userId: str
    token: str
    expiresAt: datetime

# House
class House(MongoBaseModel):
    ownerId: str # Link tới User
    name: str
    address: Optional[str] = None
    mapId: Optional[str] = None
    createdAt: datetime = Field(default_factory=datetime.now)

# HomeMember
class HomeMember(MongoBaseModel):
    houseId: str # Link tới House
    userId: str # Link tới User
    role: str = "OWNER" # OWNER, ADMIN, MEMBER
    status: str = "PENDING" # PENDING, ACCEPTED
    invitedBy: Optional[str] = None # Link tới User đã mời
    joinedAt: datetime = Field(default_factory=datetime.now)

# Room
class Room(MongoBaseModel):
    houseId: str # Link tới House
    name: str
    floor: Optional[int] = None
    createdAt: datetime = Field(default_factory=datetime.now)

# Device
class Device(MongoBaseModel):
    deviceId: str # Mã định danh thiết bị, unique
    houseId: str
    roomId: Optional[str] = None # Có thể chưa có phòng
    typeCode: str # Mã loại thiết bị (LIGHT...)
    name: str
    serialNo: Optional[str] = None
    bleMac: Optional[str] = None
    isOnline: bool = False
    lastSeenAt: Optional[datetime] = None
    createdAt: datetime = Field(default_factory=datetime.now)

# DeviceStateCurrent
class DeviceStateCurrent(MongoBaseModel):
    deviceId: str
    power: bool = False
    value: Optional[str] = None # Thông tin mở rộng
    sensors: Optional[str] = None # Cảm biến nhiệt độ, độ ẩm...
    source: str = "APP" # APP, AUTO, DEVICE
    updatedAt: datetime = Field(default_factory=datetime.now)

# Command
class Command(MongoBaseModel):
    commandId: str
    deviceId: str
    command: str # TURN_ON, TURN_OFF, SET_VALUE
    payload: Optional[str] = None # Tham số lệnh
    status: str = "PENDING" # 'PENDING', 'SENT', 'ACKED', 'FAILED'
    createdAt: datetime = Field(default_factory=datetime.now)
    ackedAt: Optional[datetime] = None

# AutoOffRule
class AutoOffRule(MongoBaseModel):
    deviceId: str
    enabled: bool = True
    durationSec: int = 0
    updatedAt: datetime = Field(default_factory=datetime.now)

# Schedule
class Schedule(MongoBaseModel):
    deviceId: str
    name: str
    enabled: bool = True
    action: str # JSON string mô tả hành động
    scheduleType: str # ONCE, DAILY, WEEKLY
    nextRunAt: datetime
    timezone: str = "Asia/Ho_Chi_Minh"


# Models phụ trợ cho API
# Dùng khi đăng ký tài khoản
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    fullName: str

# Dùng khi update user
class UserUpdateRequest(BaseModel):
    passwordHash: str
    fullName: str
    phone: str
    

# Dùng khi tạo nhà mới
class HouseCreateRequest(BaseModel):
    name: str
    address: Optional[str] = None
    mapId: Optional[str] = None

# Dùng khi mời thành viên
class InviteMemberRequest(BaseModel):
    houseId: str
    email: EmailStr
    role: str = "MEMBER"

# Dùng khi phản hồi lời mời
class RespondInviteRequest(BaseModel):
    memberId: str
    accept: bool

# Dùng khi tạo phòng mới
class RoomCreateRequest(BaseModel):
    houseId: str
    name: str
    floor: Optional[int] = None

# Dùng khi update phòng
class RoomUpdateRequest(BaseModel):
    name: str
    floor: Optional[int] = None

# Dùng khi tạo thiết bị mới
class DeviceCreateRequest(BaseModel):
    houseId: str
    roomId: Optional[str] = None
    deviceId: str
    typeCode: str
    name: str
    serialNo: Optional[str] = None

# Request điều khiển thiết bị
class CommandRequest(BaseModel):
    command: str
    payload: Optional[str] = None

# Request tạo luật tự động tắt
class AutoOffRuleCreateRequest(BaseModel):
    deviceId: str
    enabled: bool = True
    durationSec: int = 60

# Request tạo lịch hẹn
class ScheduleCreateRequest(BaseModel):
    deviceId: str
    name: str
    enabled: bool = True
    action: str
    scheduleType: str = "ONCE"
    nextRunAt: datetime
    timezone: str = "Asia/Ho_Chi_Minh"