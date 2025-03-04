import unittest
import os
import json
import tempfile
import shutil
from auth import AuthManager

class TestAuthManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the auth file
        self.test_dir = tempfile.mkdtemp()
        self.auth_file = os.path.join(self.test_dir, "users.json")
        self.auth_manager = AuthManager(auth_file=self.auth_file)
        
    def tearDown(self):
        # Clean up temp directory
        shutil.rmtree(self.test_dir)
        
    def test_create_user(self):
        """Test creating a new user."""
        self.auth_manager.create_user("testuser", "password123", "Test User")
        
        # Check that the auth file exists
        self.assertTrue(os.path.exists(self.auth_file))
        
        # Load the auth file directly to check its content
        with open(self.auth_file, 'r') as f:
            data = json.load(f)
            
        # Check that the user is created
        self.assertIn("testuser", data["users"])
        self.assertIn("password_hash", data["users"]["testuser"])
        self.assertEqual(data["users"]["testuser"]["full_name"], "Test User")
        self.assertFalse(data["users"]["testuser"]["admin"])
        
    def test_create_admin_user(self):
        """Test creating an admin user."""
        self.auth_manager.create_user("adminuser", "admin123", "Admin User", admin=True)
        
        # Load the auth file directly to check its content
        with open(self.auth_file, 'r') as f:
            data = json.load(f)
            
        # Check that the user is created with admin privileges
        self.assertIn("adminuser", data["users"])
        self.assertTrue(data["users"]["adminuser"]["admin"])
        
    def test_duplicate_user_error(self):
        """Test that creating a duplicate user raises an error."""
        self.auth_manager.create_user("testuser", "password123")
        
        with self.assertRaises(ValueError):
            self.auth_manager.create_user("testuser", "newpassword")
            
    def test_authenticate(self):
        """Test authenticating a user."""
        self.auth_manager.create_user("testuser", "password123")
        
        # Valid authentication
        session_id = self.auth_manager.authenticate("testuser", "password123")
        self.assertIsNotNone(session_id)
        self.assertIn(session_id, self.auth_manager.sessions)
        
        # Invalid username
        session_id = self.auth_manager.authenticate("nonexistentuser", "password123")
        self.assertFalse(session_id)
        
        # Invalid password
        session_id = self.auth_manager.authenticate("testuser", "wrongpassword")
        self.assertFalse(session_id)
        
    def test_validate_session(self):
        """Test validating a session."""
        self.auth_manager.create_user("testuser", "password123")
        session_id = self.auth_manager.authenticate("testuser", "password123")
        
        # Valid session
        username = self.auth_manager.validate_session(session_id)
        self.assertEqual(username, "testuser")
        
        # Invalid session
        username = self.auth_manager.validate_session("invalid_session_id")
        self.assertIsNone(username)
        
    def test_logout(self):
        """Test ending a session."""
        self.auth_manager.create_user("testuser", "password123")
        session_id = self.auth_manager.authenticate("testuser", "password123")
        
        # Check that session exists
        self.assertIn(session_id, self.auth_manager.sessions)
        
        # End the session
        self.auth_manager.logout(session_id)
        
        # Check that session no longer exists
        self.assertNotIn(session_id, self.auth_manager.sessions)
        
    def test_get_user_info(self):
        """Test getting information about a user."""
        self.auth_manager.create_user("testuser", "password123", "Test User")
        
        # Get info for existing user
        user_info = self.auth_manager.get_user_info("testuser")
        self.assertIsNotNone(user_info)
        self.assertEqual(user_info["full_name"], "Test User")
        
        # Get info for non-existent user
        user_info = self.auth_manager.get_user_info("nonexistentuser")
        self.assertIsNone(user_info)
        
    def test_grant_trial_access(self):
        """Test granting a user access to a trial."""
        self.auth_manager.create_user("testuser", "password123")
        
        # Grant access to a trial
        self.auth_manager.grant_trial_access("testuser", "trial1")
        
        # Check that the user has access
        user_info = self.auth_manager.get_user_info("testuser")
        self.assertIn("trial1", user_info["trial_access"])
        
        # Grant access to another trial
        self.auth_manager.grant_trial_access("testuser", "trial2")
        
        # Check that the user has access to both trials
        user_info = self.auth_manager.get_user_info("testuser")
        self.assertIn("trial1", user_info["trial_access"])
        self.assertIn("trial2", user_info["trial_access"])
        
    def test_has_trial_access(self):
        """Test checking if a user has access to a trial."""
        # Create a regular user and an admin user
        self.auth_manager.create_user("testuser", "password123")
        self.auth_manager.create_user("adminuser", "admin123", admin=True)
        
        # Grant the regular user access to a trial
        self.auth_manager.grant_trial_access("testuser", "trial1")
        
        # Regular user should have access to granted trial but not others
        self.assertTrue(self.auth_manager.has_trial_access("testuser", "trial1"))
        self.assertFalse(self.auth_manager.has_trial_access("testuser", "trial2"))
        
        # Admin user should have access to all trials
        self.assertTrue(self.auth_manager.has_trial_access("adminuser", "trial1"))
        self.assertTrue(self.auth_manager.has_trial_access("adminuser", "trial2"))
        
        # Non-existent user should not have access
        self.assertFalse(self.auth_manager.has_trial_access("nonexistentuser", "trial1"))

if __name__ == '__main__':
    unittest.main() 