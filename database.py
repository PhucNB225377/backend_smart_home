import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Đọc các biến từ file .env
load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")

# Tạo kết nối
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

print(f"Kết nối tới MongoDB: {DB_NAME}")