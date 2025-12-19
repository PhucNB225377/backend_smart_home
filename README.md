**Clone code**
```bash
git clone https://github.com/PhucNB225377/backend_smart_home
cd backend_smart_home
```

**Tạo môi trường ảo**
* Windows
```bash
py -m venv venv
.\venv\Scripts\activate
```
* MAC/Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

**Cài thư viện**
```bash
pip install -r requirements.txt
```

**Tạo thư mục .env nội dung tôi gửi qua mail**

**Chạy**
* Khởi động
```bash
uvicorn main:app --reload
```
* Server chạy tại http://127.0.0.1:8000
* Test API tại http://127.0.0.1:8000/docs
