from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from database import db
from models import User, UserRegisterRequest, UserUpdateRequest
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import jwt
import os
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv()

router = APIRouter()

# Cấu hình bảo mật
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


# Hàm mã hóa password
def get_password_hash(password):
    return pwd_context.hash(password)

# Hàm kiểm tra password
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Hàm tạo jwt token
def create_access_token(data: dict):
    to_encode = data.copy()
    # Token hết hạn sau 7 ngày
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# API đăng ký user mới
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user_req: UserRegisterRequest):
    # Check email trùng
    existing_user = await db.users.find_one({"email": user_req.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email này đã được sử dụng")

    # Tạo user mới
    new_user = User(
        email=user_req.email,
        passwordHash=get_password_hash(user_req.password),
        fullName=user_req.fullName
    )

    # Lưu xuống DB
    result = await db.users.insert_one(new_user.model_dump(by_alias=True, exclude=["id"]))
    
    return {"message": "Đăng ký thành công", "userId": str(result.inserted_id)}

# API đăng nhập user
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2PasswordRequestForm nhận username (là email) và password

    # Tìm user trong DB
    user = await db.users.find_one({"email": form_data.username})
    if not user:
        raise HTTPException(status_code=400, detail="Sai email hoặc mật khẩu")

    # Kiểm tra mật khẩu
    if not verify_password(form_data.password, user["passwordHash"]):
        raise HTTPException(status_code=400, detail="Sai email hoặc mật khẩu")

    # Tạo token
    # Cho userId vào trong token để sau này biết ai đang gọi
    access_token = create_access_token(data={"sub": str(user["_id"])})
    
    return {"access_token": access_token, "token_type": "bearer"}


# Định nghĩa nơi lấy token (link API login)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")

# Hàm lấy token từ header, giải mã và tìm user trong DB
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Token không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Giải mã token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        userId: str = payload.get("sub") # Lấy userId
        if userId is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    # Tìm user trong DB
    user = await db.users.find_one({"_id": ObjectId(userId)})
    if user is None:
        raise credentials_exception

    # Trả về toàn bộ thông tin user để các hàm khác dùng
    return user

# API lấy thông tin user hiện tại
@router.get("/detail", response_model=User)
async def get_user(current_user: dict = Depends(get_current_user)):
    return current_user

# API cập nhật thông tin user hiện tại
@router.put("/detail")
async def update_user(
    user_update: UserUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    for k, v in user_update.model_dump().items():
        if k == "passwordHash" and v is not None:
            user_update.passwordHash = get_password_hash(v)
    update_data = {k: v for k, v in user_update.model_dump().items() if v is not None}
    
    if len(update_data) >= 1:
        await db.users.update_one(
            {"_id": current_user["_id"]},
            {"$set": update_data}
        )
    
    return {"message": "Cập nhật thông tin thành công"}