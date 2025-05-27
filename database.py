from pymongo import MongoClient
import os
from bson.binary import Binary
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# MongoDB Atlas connection
MONGODB_URI = os.getenv('MongoDbURL', "")
client = MongoClient(MONGODB_URI)
db = client['voice_auth_db']
users_collection = db['users']
reset_codes_collection = db['reset_codes']

def init_db():
    """Initialize MongoDB database."""
    # Create indexes
    users_collection.create_index('email', unique=True)
    reset_codes_collection.create_index('email', unique=True)
    reset_codes_collection.create_index('reset_code_expiry', expireAfterSeconds=15*60)  # Auto-delete expired codes

def save_user_data(email, voice_data, phrase_data, key_data):
    """Save user data to MongoDB."""
    user_data = {
        'email': email,
        'voice_data': Binary(voice_data),
        'phrase_data': Binary(phrase_data),
        'key_data': Binary(key_data)
    }
    users_collection.update_one(
        {'email': email},
        {'$set': user_data},
        upsert=True
    )

def get_user_data(email):
    """Retrieve user data by email."""
    user = users_collection.find_one({'email': email})
    if user:
        return (
            user['voice_data'],
            user['phrase_data'],
            user['key_data']
        )
    return None

def save_reset_code(email, code):
    """Save reset code and expiry to MongoDB."""
    expiry = datetime.utcnow().timestamp() + 15 * 60  # 15 minutes from now
    reset_code_data = {
        'email': email,
        'code': code,
        'reset_code_expiry': expiry
    }
    reset_codes_collection.update_one(
        {'email': email},
        {'$set': reset_code_data},
        upsert=True
    )

def verify_reset_code(email, code):
    """Verify reset code and check if it's still valid."""
    reset_code = reset_codes_collection.find_one({'email': email})
    if reset_code and reset_code.get('code') == code:
        if reset_code.get('reset_code_expiry') > datetime.utcnow().timestamp():
            # Clear the reset code after successful verification
            reset_codes_collection.delete_one({'email': email})
            return True
    # Clear invalid or expired codes
    reset_codes_collection.delete_one({'email': email})
    return False