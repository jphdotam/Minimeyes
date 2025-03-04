import unittest
import os
import shutil
import tempfile
import json
from data_manager import DataManager
from minimiser import Minimiser

class TestDataManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests
        self.test_dir = tempfile.mkdtemp()
        self.data_manager = DataManager(base_dir=self.test_dir)
        
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
        
    def test_create_trial(self):
        """Test creating a new trial."""
        minimiser = self.data_manager.create_trial(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed",
            user="test_user"
        )
        
        # Check that minimiser is created correctly
        self.assertEqual(minimiser.trial_id, self.trial_id)
        self.assertEqual(minimiser.minimisation_vars, self.minimisation_vars)
        self.assertEqual(minimiser.arms, self.arms)
        
        # Check that trial directory and config file are created
        trial_dir = os.path.join(self.test_dir, self.trial_id)
        self.assertTrue(os.path.exists(trial_dir))
        self.assertTrue(os.path.exists(os.path.join(trial_dir, "config.json")))
        
        # Check that audit trail has an entry
        audit_dir = os.path.join(trial_dir, "audit")
        self.assertTrue(os.path.exists(audit_dir))
        audit_files = os.listdir(audit_dir)
        self.assertTrue(len(audit_files) > 0)
        
    def test_list_trials(self):
        """Test listing all trials."""
        # Create multiple trials
        self.data_manager.create_trial(
            trial_id="trial1",
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed1"
        )
        
        self.data_manager.create_trial(
            trial_id="trial2",
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed2"
        )
        
        # List trials
        trials = self.data_manager.list_trials()
        
        # Check that both trials are listed
        self.assertEqual(len(trials), 2)
        trial_ids = [t['trial_id'] for t in trials]
        self.assertIn("trial1", trial_ids)
        self.assertIn("trial2", trial_ids)
        
    def test_load_trial(self):
        """Test loading a trial."""
        # Create a trial with specific settings
        original_minimiser = self.data_manager.create_trial(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed",
            user="test_user"
        )
        
        # Load the trial
        loaded_minimiser = self.data_manager.load_trial(self.trial_id)
        
        # Check that all properties are correctly loaded
        self.assertEqual(loaded_minimiser.trial_id, original_minimiser.trial_id)
        
        # Compare each variable separately since JSON serialization may convert tuples to lists
        for key in original_minimiser.minimisation_vars.keys():
            self.assertEqual(
                set(loaded_minimiser.minimisation_vars[key]), 
                set(original_minimiser.minimisation_vars[key])
            )
            
        self.assertEqual(set(loaded_minimiser.arms), set(original_minimiser.arms))
        self.assertEqual(loaded_minimiser.minimisation_weight, original_minimiser.minimisation_weight)
        self.assertEqual(loaded_minimiser.seed, original_minimiser.seed)
        self.assertEqual(loaded_minimiser.strict_mode, original_minimiser.strict_mode)
        
    def test_add_patient(self):
        """Test adding a patient to a trial."""
        # Create a trial
        self.data_manager.create_trial(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed"
        )
        
        # Add a patient
        characteristics = {'gender': 'male', 'age_group': '<=50'}
        arm = self.data_manager.add_patient(
            trial_id=self.trial_id,
            patient_id="patient1",
            characteristics=characteristics,
            user="test_user"
        )
        
        # Check that arm is returned
        self.assertIn(arm, self.arms)
        
        # Load the trial and check that patient is added
        minimiser = self.data_manager.load_trial(self.trial_id)
        self.assertEqual(minimiser.get_n_patients(), 1)
        self.assertTrue("patient1" in minimiser.df_patients.index)
        
        # Check that audit trail has an entry
        trial_dir = os.path.join(self.test_dir, self.trial_id)
        audit_dir = os.path.join(trial_dir, "audit")
        audit_files = [f for f in os.listdir(audit_dir) if f.endswith('.json')]
        self.assertTrue(len(audit_files) >= 2)  # create_trial + add_patient
        
    def test_change_patient_status(self):
        """Test changing a patient's active status."""
        # Create a trial and add a patient
        self.data_manager.create_trial(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed"
        )
        
        self.data_manager.add_patient(
            trial_id=self.trial_id,
            patient_id="patient1",
            characteristics={'gender': 'male', 'age_group': '<=50'}
        )
        
        # Deactivate the patient
        self.data_manager.change_patient_status(
            trial_id=self.trial_id,
            patient_id="patient1",
            active=False,
            user="test_user"
        )
        
        # Load the trial and check that patient is deactivated
        minimiser = self.data_manager.load_trial(self.trial_id)
        self.assertFalse(minimiser.df_patients.loc["patient1", "active"])
        
        # Reactivate the patient
        self.data_manager.change_patient_status(
            trial_id=self.trial_id,
            patient_id="patient1",
            active=True,
            user="test_user"
        )
        
        # Load the trial and check that patient is reactivated
        minimiser = self.data_manager.load_trial(self.trial_id)
        self.assertTrue(minimiser.df_patients.loc["patient1", "active"])
        
    def test_reassign_arm(self):
        """Test reassigning a patient to a different arm."""
        # Create a non-strict trial and add a patient
        self.data_manager.create_trial(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed",
            strict_mode=False
        )
        
        initial_arm = self.data_manager.add_patient(
            trial_id=self.trial_id,
            patient_id="patient1",
            characteristics={'gender': 'male', 'age_group': '<=50'}
        )
        
        # Reassign to the other arm
        new_arm = "B" if initial_arm == "A" else "A"
        self.data_manager.reassign_arm(
            trial_id=self.trial_id,
            patient_id="patient1",
            new_arm=new_arm,
            user="test_user"
        )
        
        # Load the trial and check that arm is updated
        minimiser = self.data_manager.load_trial(self.trial_id)
        self.assertEqual(minimiser.df_patients.loc["patient1", "arm"], new_arm)
        
    def test_get_audit_trail(self):
        """Test retrieving the audit trail for a trial."""
        # Create a trial and perform several actions
        self.data_manager.create_trial(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed",
            user="test_user"
        )
        
        self.data_manager.add_patient(
            trial_id=self.trial_id,
            patient_id="patient1",
            characteristics={'gender': 'male', 'age_group': '<=50'},
            user="test_user"
        )
        
        self.data_manager.change_patient_status(
            trial_id=self.trial_id,
            patient_id="patient1",
            active=False,
            user="test_user"
        )
        
        # Get the audit trail
        audit_entries = self.data_manager.get_audit_trail(self.trial_id)
        
        # Check that all actions are recorded
        self.assertEqual(len(audit_entries), 3)  # create_trial + add_patient + change_status
        
        # Check that the entries have the expected structure
        for entry in audit_entries:
            self.assertIn('timestamp', entry)
            self.assertIn('action', entry)
            self.assertIn('data', entry)
            self.assertIn('user', entry)
            self.assertEqual(entry['user'], 'test_user')

if __name__ == '__main__':
    unittest.main() 