import os
import json
import hashlib
from datetime import datetime, timedelta

class AuthManager:
    def __init__(self, auth_file="auth/users.json"):
        """Initialize the authentication manager."""
        self.auth_file = auth_file
        self.sessions = {}
        
        # Create auth directory if it doesn't exist
        os.makedirs(os.path.dirname(auth_file), exist_ok=True)
        
        # Create users file if it doesn't exist
        if not os.path.exists(auth_file):
            with open(auth_file, 'w') as f:
                json.dump({"users": {}}, f)
                
    def _load_users(self):
        """Load users from the auth file."""
        with open(self.auth_file, 'r') as f:
            return json.load(f)
    
    def _save_users(self, data):
        """Save users to the auth file."""
        with open(self.auth_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _hash_password(self, password):
        """Hash a password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username, password, full_name=None, admin=False):
        """Create a new user."""
        data = self._load_users()
        
        if username in data["users"]:
            raise ValueError(f"User '{username}' already exists.")
            
        data["users"][username] = {
            "password_hash": self._hash_password(password),
            "full_name": full_name,
            "admin": admin,
            "created_at": datetime.now().isoformat(),
            "trial_access": []  # List of trial IDs this user can access
        }
        
        self._save_users(data)
    
    def authenticate(self, username, password):
        """Authenticate a user and create a session."""
        data = self._load_users()
        
        if username not in data["users"]:
            return False
            
        user = data["users"][username]
        if user["password_hash"] != self._hash_password(password):
            return False
            
        # Create session
        session_id = hashlib.sha256(f"{username}_{datetime.now().isoformat()}".encode()).hexdigest()
        self.sessions[session_id] = {
            "username": username,
            "expires": (datetime.now() + timedelta(hours=24)).isoformat()
        }
        
        return session_id
    
    def validate_session(self, session_id):
        """Validate a session."""
        if session_id not in self.sessions:
            return None
            
        session = self.sessions[session_id]
        if datetime.now() > datetime.fromisoformat(session["expires"]):
            del self.sessions[session_id]
            return None
            
        return session["username"]
    
    def logout(self, session_id):
        """End a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def get_user_info(self, username):
        """Get information about a user."""
        data = self._load_users()
        
        if username not in data["users"]:
            return None
            
        return data["users"][username]
    
    def grant_trial_access(self, username, trial_id):
        """Grant a user access to a trial."""
        data = self._load_users()
        
        if username not in data["users"]:
            raise ValueError(f"User '{username}' does not exist.")
            
        if trial_id not in data["users"][username]["trial_access"]:
            data["users"][username]["trial_access"].append(trial_id)
            self._save_users(data)
    
    def has_trial_access(self, username, trial_id):
        """Check if a user has access to a trial."""
        data = self._load_users()
        
        if username not in data["users"]:
            return False
            
        user = data["users"][username]
        
        # Admins have access to all trials
        if user["admin"]:
            return True
            
        return trial_id in user["trial_access"]
    
    def has_users(self):
        """Check if any users exist in the system."""
        if not os.path.exists(self.auth_file):
            return False
        
        try:
            with open(self.auth_file, 'r') as f:
                data = json.load(f)
                # Check if there are any users in the users dictionary
                return "users" in data and len(data["users"]) > 0
        except (json.JSONDecodeError, FileNotFoundError):
            return False 