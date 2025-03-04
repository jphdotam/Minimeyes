import unittest
import os
import shutil
import tempfile
import pandas as pd
from auth import AuthManager
from data_manager import DataManager
from minimiser import Minimiser

class TestIntegration(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests
        self.test_dir = tempfile.mkdtemp()
        self.auth_file = os.path.join(self.test_dir, "users.json")
        
        # Initialize managers
        self.auth_manager = AuthManager(auth_file=self.auth_file)
        self.data_manager = DataManager(base_dir=os.path.join(self.test_dir, "trials"))
        
        # Create a test user
        self.auth_manager.create_user("testuser", "password123", "Test User")
        
        # Standard test variables
        self.minimisation_vars = {
            'gender': ('male', 'female'),
            'age_group': ('<=50', '>50')
        }
        self.arms = ('A', 'B')
        self.trial_id = "test_trial"
        
    def tearDown(self):
        # Clean up temp directory
        shutil.rmtree(self.test_dir)
        
    def test_full_workflow(self):
        """Test a complete workflow from user login to patient management."""
        # 1. User authentication
        session_id = self.auth_manager.authenticate("testuser", "password123")
        self.assertIsNotNone(session_id)
        username = self.auth_manager.validate_session(session_id)
        self.assertEqual(username, "testuser")
        
        # 2. Create a trial
        minimiser = self.data_manager.create_trial(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed",
            user=username
        )
        
        # Grant user access to the trial
        self.auth_manager.grant_trial_access(username, self.trial_id)
        self.assertTrue(self.auth_manager.has_trial_access(username, self.trial_id))
        
        # 3. Add some patients
        patients = [
            {"id": "patient1", "gender": "male", "age_group": "<=50"},
            {"id": "patient2", "gender": "female", "age_group": ">50"},
            {"id": "patient3", "gender": "male", "age_group": ">50"}
        ]
        
        for patient in patients:
            characteristics = {k: v for k, v in patient.items() if k != "id"}
            arm = self.data_manager.add_patient(
                trial_id=self.trial_id,
                patient_id=patient["id"],
                characteristics=characteristics,
                user=username
            )
            self.assertIn(arm, self.arms)
        
        # 4. List trials and verify
        trials = self.data_manager.list_trials()
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0]["trial_id"], self.trial_id)
        self.assertEqual(trials[0]["total_patients"], 3)
        self.assertEqual(trials[0]["active_patients"], 3)
        
        # 5. Deactivate a patient
        self.data_manager.change_patient_status(
            trial_id=self.trial_id,
            patient_id="patient2",
            active=False,
            user=username
        )
        
        # 6. List trials again and verify patient counts
        trials = self.data_manager.list_trials()
        self.assertEqual(trials[0]["total_patients"], 3)
        self.assertEqual(trials[0]["active_patients"], 2)
        
        # 7. Verify that the data is correctly stored and can be loaded
        minimiser = self.data_manager.load_trial(self.trial_id)
        self.assertEqual(minimiser.get_n_patients(), 3)
        self.assertEqual(minimiser.get_active_patients(), 2)
        self.assertTrue(minimiser.df_patients.loc["patient1", "active"])
        self.assertFalse(minimiser.df_patients.loc["patient2", "active"])
        
        # 8. Get audit trail and verify entries
        audit_entries = self.data_manager.get_audit_trail(self.trial_id)
        self.assertTrue(len(audit_entries) >= 5)  # create_trial + 3 add_patient + deactivate
        
        # 9. User logout
        self.auth_manager.logout(session_id)
        self.assertIsNone(self.auth_manager.validate_session(session_id))

if __name__ == '__main__':
    unittest.main() 