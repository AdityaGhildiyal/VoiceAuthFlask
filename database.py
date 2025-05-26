from pymongo import MongoClient
import os
from bson.binary import Binary
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB Atlas connection
MONGODB_URI = os.getenv('MONGODB_URI', "mongodb+srv://AddyG:UaafywQplfulYrGh@voiceauthdb.jqjw0tk.mongodb.net/?retryWrites=true&w=majority&appName=voiceAuthDB")
client = MongoClient(MONGODB_URI)
db = client['voice_auth_db']
users_collection = db['users']

def init_db():
    """Initialize MongoDB database."""
    # Create indexes
    users_collection.create_index('email', unique=True)

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