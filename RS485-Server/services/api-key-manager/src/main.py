from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import os
from cryptography.fernet import Fernet
import base64
import secrets
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="API Key Manager")

# MongoDB connection
client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = client.rs485_db

# Security
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
fernet = Fernet(API_KEY_SECRET.encode())

# Models
class ClientCreate(BaseModel):
    name: str
    email: str
    validity_days: int
    description: Optional[str] = None

class ClientResponse(BaseModel):
    client_id: str
    name: str
    email: str
    api_key: str
    created_at: datetime
    expires_at: datetime
    description: Optional[str]

# Helper functions
def generate_api_key():
    key = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(key).decode('utf-8')

def encrypt_api_key(api_key: str) -> str:
    return fernet.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    return fernet.decrypt(encrypted_key.encode()).decode()

# Routes
@app.post("/api/v1/clients", response_model=ClientResponse)
async def create_client(client_data: ClientCreate):
    # Generate API key
    api_key = generate_api_key()
    encrypted_key = encrypt_api_key(api_key)
    
    # Calculate expiration
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(days=client_data.validity_days)
    
    # Create client document
    client_doc = {
        "name": client_data.name,
        "email": client_data.email,
        "api_key": encrypted_key,
        "created_at": created_at,
        "expires_at": expires_at,
        "description": client_data.description
    }
    
    # Insert into database
    result = await db.clients.insert_one(client_doc)
    
    # Return response with unencrypted API key
    return {
        "client_id": str(result.inserted_id),
        "name": client_data.name,
        "email": client_data.email,
        "api_key": api_key,  # Return unencrypted key only once
        "created_at": created_at,
        "expires_at": expires_at,
        "description": client_data.description
    }

@app.get("/api/v1/clients/{client_id}", response_model=ClientResponse)
async def get_client(client_id: str):
    client = await db.clients.find_one({"_id": client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Decrypt API key
    client["api_key"] = decrypt_api_key(client["api_key"])
    
    return {
        "client_id": str(client["_id"]),
        "name": client["name"],
        "email": client["email"],
        "api_key": client["api_key"],
        "created_at": client["created_at"],
        "expires_at": client["expires_at"],
        "description": client.get("description")
    }

@app.get("/api/v1/clients", response_model=list[ClientResponse])
async def list_clients():
    clients = []
    cursor = db.clients.find()
    async for client in cursor:
        client["api_key"] = decrypt_api_key(client["api_key"])
        clients.append({
            "client_id": str(client["_id"]),
            "name": client["name"],
            "email": client["email"],
            "api_key": client["api_key"],
            "created_at": client["created_at"],
            "expires_at": client["expires_at"],
            "description": client.get("description")
        })
    return clients

@app.delete("/api/v1/clients/{client_id}")
async def delete_client(client_id: str):
    result = await db.clients.delete_one({"_id": client_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted successfully"}

@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"} 