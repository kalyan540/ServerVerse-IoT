import paho.mqtt.client as mqtt
from motor.motor_asyncio import AsyncIOMotorClient
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import logging
import asyncio
import aioredis
from typing import Dict, List
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MongoDB connection
client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = client.rs485_db

# Redis connection
redis = aioredis.from_url(
    f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}",
    password=os.getenv("REDIS_PASSWORD"),
    encoding="utf-8",
    decode_responses=True
)

# MQTT Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# Batch processing configuration
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
BATCH_INTERVAL = int(os.getenv("BATCH_INTERVAL", "5"))

# Security
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
fernet = Fernet(API_KEY_SECRET.encode())

# In-memory batch storage
device_batches: Dict[str, List[dict]] = {}

def decrypt_api_key(encrypted_key: str) -> str:
    try:
        return fernet.decrypt(encrypted_key.encode()).decode()
    except Exception as e:
        logger.error(f"Error decrypting API key: {e}")
        return None

async def validate_device(device_id: str, api_key: str) -> bool:
    try:
        # Find device in database
        device = await db.devices.find_one({
            "device_id": device_id,
            "api_key": api_key
        })
        return device is not None
    except Exception as e:
        logger.error(f"Error validating device: {e}")
        return False

async def save_to_redis(device_id: str, data: dict):
    try:
        # Add timestamp to data
        data["timestamp"] = datetime.utcnow().isoformat()
        
        # Add to Redis stream
        await redis.xadd(
            f"device:{device_id}:stream",
            {"data": json.dumps(data)},
            maxlen=10000  # Keep last 10000 messages per device
        )
        
        # Add to batch
        if device_id not in device_batches:
            device_batches[device_id] = []
        device_batches[device_id].append(data)
        
        logger.info(f"Data saved to Redis for device {device_id}")
    except Exception as e:
        logger.error(f"Error saving to Redis: {e}")

async def process_batch(device_id: str):
    try:
        if device_id in device_batches and len(device_batches[device_id]) >= BATCH_SIZE:
            batch = device_batches[device_id]
            # Save batch to MongoDB
            await db.device_data.insert_many([
                {
                    "device_id": device_id,
                    "data": item["data"],
                    "timestamp": datetime.fromisoformat(item["timestamp"])
                }
                for item in batch
            ])
            logger.info(f"Batch of {len(batch)} records saved to MongoDB for device {device_id}")
            device_batches[device_id] = []
    except Exception as e:
        logger.error(f"Error processing batch for device {device_id}: {e}")

async def batch_processor():
    while True:
        try:
            for device_id in list(device_batches.keys()):
                await process_batch(device_id)
            await asyncio.sleep(BATCH_INTERVAL)
        except Exception as e:
            logger.error(f"Error in batch processor: {e}")
            await asyncio.sleep(1)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker")
        # Subscribe to all device topics
        client.subscribe("devices/+/data")
    else:
        logger.error(f"Failed to connect to MQTT broker with code: {rc}")

async def process_message(device_id: str, payload: dict):
    try:
        # Validate API key
        api_key = payload.get("api_key")
        if not api_key:
            logger.warning(f"No API key provided for device {device_id}")
            return
        
        # Decrypt API key
        decrypted_key = decrypt_api_key(api_key)
        if not decrypted_key:
            logger.warning(f"Invalid API key for device {device_id}")
            return
        
        # Validate device
        if not await validate_device(device_id, decrypted_key):
            logger.warning(f"Invalid device or API key for device {device_id}")
            return
        
        # Save to Redis
        await save_to_redis(device_id, payload.get("data", {}))
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def on_message(client, userdata, msg):
    try:
        # Extract device_id from topic
        device_id = msg.topic.split('/')[1]
        
        # Parse message
        payload = json.loads(msg.payload.decode())
        
        # Process message asynchronously
        asyncio.create_task(process_message(device_id, payload))
        
    except Exception as e:
        logger.error(f"Error in message handler: {e}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        logger.warning("Unexpected disconnection from MQTT broker")
    else:
        logger.info("Disconnected from MQTT broker")

async def main():
    # Create event loop
    loop = asyncio.get_event_loop()
    
    # Start batch processor
    loop.create_task(batch_processor())
    
    # Create MQTT client
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    # Set callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    # Connect to broker
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.loop_forever()
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 