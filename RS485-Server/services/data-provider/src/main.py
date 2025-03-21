from fastapi import FastAPI, HTTPException, Depends, Security, Query
from fastapi.security import APIKeyHeader
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, List
import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Data Provider Service")

# MongoDB connection
client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = client.rs485_db

# Security
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
fernet = Fernet(API_KEY_SECRET.encode())
api_key_header = APIKeyHeader(name="X-API-Key")

# Models
class DeviceData(BaseModel):
    device_id: str
    timestamp: datetime
    data: dict

class DeviceDataResponse(BaseModel):
    status: str
    data: List[DeviceData]
    total: int
    page: int
    page_size: int

def decrypt_api_key(encrypted_key: str) -> str:
    try:
        return fernet.decrypt(encrypted_key.encode()).decode()
    except Exception:
        return None

async def validate_api_key(api_key: str = Security(api_key_header)):
    # Decrypt API key
    decrypted_key = decrypt_api_key(api_key)
    if not decrypted_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    # Check if API key exists and is valid
    client = await db.clients.find_one({
        "api_key": decrypted_key,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not client:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key"
        )
    
    return decrypted_key

@app.get("/api/v1/devices/{device_id}/data", response_model=DeviceDataResponse)
async def get_device_data(
    device_id: str,
    api_key: str = Depends(validate_api_key),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000)
):
    # Validate device ownership
    device = await db.devices.find_one({
        "device_id": device_id,
        "api_key": api_key
    })
    
    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found or access denied"
        )
    
    # Build query
    query = {"device_id": device_id}
    if start_time:
        query["timestamp"] = {"$gte": start_time}
    if end_time:
        if "timestamp" in query:
            query["timestamp"]["$lte"] = end_time
        else:
            query["timestamp"] = {"$lte": end_time}
    
    # Get total count
    total = await db.device_data.count_documents(query)
    
    # Get paginated data
    cursor = db.device_data.find(query)
    cursor = cursor.sort("timestamp", -1)
    cursor = cursor.skip((page - 1) * page_size).limit(page_size)
    
    data = []
    async for doc in cursor:
        data.append(DeviceData(
            device_id=doc["device_id"],
            timestamp=doc["timestamp"],
            data=doc["data"]
        ))
    
    return DeviceDataResponse(
        status="success",
        data=data,
        total=total,
        page=page,
        page_size=page_size
    )

@app.get("/api/v1/devices", response_model=List[str])
async def list_devices(api_key: str = Depends(validate_api_key)):
    # Get all devices for the API key
    cursor = db.devices.find({"api_key": api_key})
    devices = []
    async for doc in cursor:
        devices.append(doc["device_id"])
    return devices

@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"} 