// Create database
db = db.getSiblingDB('rs485_db');

// Create collections
db.createCollection('clients');
db.createCollection('devices');
db.createCollection('device_data');

// Create indexes
db.clients.createIndex({ "api_key": 1 }, { unique: true });
db.clients.createIndex({ "email": 1 }, { unique: true });
db.clients.createIndex({ "expires_at": 1 });

db.devices.createIndex({ "device_id": 1 }, { unique: true });
db.devices.createIndex({ "api_key": 1 });
db.devices.createIndex({ "created_at": 1 });

db.device_data.createIndex({ "device_id": 1, "timestamp": -1 });
db.device_data.createIndex({ "timestamp": -1 });

// Create admin user
db.createUser({
    user: process.env.MONGO_INITDB_ROOT_USERNAME,
    pwd: process.env.MONGO_INITDB_ROOT_PASSWORD,
    roles: [
        {
            role: "readWrite",
            db: "rs485_db"
        }
    ]
}); 