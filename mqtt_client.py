from fastapi_mqtt import FastMQTT, MQTTConfig
import os
from dotenv import load_dotenv
import ssl

load_dotenv()


# Cấu hình MQTT
mqtt_config = MQTTConfig(
    host = os.getenv("MQTT_HOST"),
    port = int(os.getenv("MQTT_PORT")),
    username = os.getenv("MQTT_USER"),
    password = os.getenv("MQTT_PASSWORD"),
    keepalive = 60,
    ssl = ssl.create_default_context()
)

# Khởi tạo đối tượng MQTT
mqtt = FastMQTT(config=mqtt_config)