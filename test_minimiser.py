import unittest
import pandas as pd
import numpy as np
from minimiser import Minimiser

class TestMinimiser(unittest.TestCase):
    def setUp(self):
        # Standard test variables
        self.minimisation_vars = {
            'gender': ('male', 'female'),
            'age_group': ('<=50', '>50')
        }
        self.arms = ('A', 'B')
        self.trial_id = "test_trial"
        
    def test_initialization(self):
        """Test that minimiser initializes correctly."""
        minimiser = Minimiser(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            minimisation_weight=0.8,
            seed="test_seed",
            strict_mode=True
        )
        
        self.assertEqual(minimiser.trial_id, self.trial_id)
        self.assertEqual(minimiser.minimisation_vars, self.minimisation_vars)
        self.assertEqual(minimiser.arms, self.arms)
        self.assertEqual(minimiser.minimisation_weight, 0.8)
        self.assertEqual(minimiser.seed, "test_seed")
        self.assertTrue(minimiser.strict_mode)
        self.assertTrue(minimiser.df_patients.empty)
        
    def test_deterministic_random(self):
        """Test that deterministic_random produces consistent results."""
        minimiser = Minimiser(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed"
        )
        
        # Same inputs should produce same outputs
        value1 = minimiser.deterministic_random("patient1")
        value2 = minimiser.deterministic_random("patient1")
        self.assertEqual(value1, value2)
        
        # Different inputs should (very likely) produce different outputs
        value3 = minimiser.deterministic_random("patient2")
        self.assertNotEqual(value1, value3)
        
        # Different seeds should produce different outputs
        minimiser2 = Minimiser(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="different_seed"
        )
        value4 = minimiser2.deterministic_random("patient1")
        self.assertNotEqual(value1, value4)
        
    def test_randomise_patient(self):
        """Test randomising a patient."""
        minimiser = Minimiser(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed"
        )
        
        # First patient
        characteristics = {'gender': 'male', 'age_group': '<=50'}
        arm = minimiser.randomise_patient("patient1", characteristics)
        
        # Check that arm is valid
        self.assertIn(arm, minimiser.arms)
        
        # Check that patient is added to dataframe
        self.assertEqual(minimiser.get_n_patients(), 1)
        self.assertTrue("patient1" in minimiser.df_patients.index)
        self.assertEqual(minimiser.df_patients.loc["patient1", "gender"], "male")
        self.assertEqual(minimiser.df_patients.loc["patient1", "age_group"], "<=50")
        self.assertEqual(minimiser.df_patients.loc["patient1", "arm"], arm)
        self.assertTrue(minimiser.df_patients.loc["patient1", "active"])
        
    def test_duplicate_patient_error(self):
        """Test that adding a duplicate patient ID raises an error."""
        minimiser = Minimiser(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed"
        )
        
        # Add first patient successfully
        characteristics = {'gender': 'male', 'age_group': '<=50'}
        minimiser.randomise_patient("patient1", characteristics)
        
        # Attempt to add a second patient with the same ID
        with self.assertRaises(ValueError):
            # The error message might vary, so we just check for any ValueError
            minimiser.randomise_patient("patient1", characteristics)
            
    def test_invalid_characteristics(self):
        """Test that invalid characteristics raise errors."""
        minimiser = Minimiser(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed"
        )
        
        # Missing characteristic
        with self.assertRaises(ValueError):
            minimiser.randomise_patient("patient1", {'gender': 'male'})
            
        # Invalid value
        with self.assertRaises(ValueError):
            minimiser.randomise_patient("patient1", {'gender': 'unknown', 'age_group': '<=50'})
            
    def test_get_minimised_arm(self):
        """Test the minimisation algorithm logic."""
        minimiser = Minimiser(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed",
            minimisation_weight=1.0  # Always use minimisation
        )
        
        # Add some patients to create imbalance
        minimiser.randomise_patient("patient1", {'gender': 'male', 'age_group': '<=50'})
        minimiser.randomise_patient("patient2", {'gender': 'male', 'age_group': '>50'})
        minimiser.randomise_patient("patient3", {'gender': 'female', 'age_group': '<=50'})
        
        # Force all to arm A for testing
        minimiser.df_patients.loc["patient1", "arm"] = "A"
        minimiser.df_patients.loc["patient2", "arm"] = "A"
        minimiser.df_patients.loc["patient3", "arm"] = "A"
        
        # Now a new male patient should go to arm B to balance
        characteristics = {'gender': 'male', 'age_group': '<=50'}
        arm = minimiser.get_minimised_arm(characteristics)
        self.assertEqual(arm, "B")
        
    def test_deactivate_reactivate_patient(self):
        """Test deactivating and reactivating patients."""
        minimiser = Minimiser(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed"
        )
        
        # Add a patient
        characteristics = {'gender': 'male', 'age_group': '<=50'}
        minimiser.randomise_patient("patient1", characteristics)
        
        # Check that patient is active
        self.assertTrue(minimiser.df_patients.loc["patient1", "active"])
        self.assertEqual(minimiser.get_active_patients(), 1)
        
        # Deactivate patient
        minimiser.deactivate_patient("patient1")
        self.assertFalse(minimiser.df_patients.loc["patient1", "active"])
        self.assertEqual(minimiser.get_active_patients(), 0)
        
        # Reactivate patient
        minimiser.reactivate_patient("patient1")
        self.assertTrue(minimiser.df_patients.loc["patient1", "active"])
        self.assertEqual(minimiser.get_active_patients(), 1)
        
    def test_reassign_arm(self):
        """Test reassigning a patient to a different arm."""
        minimiser = Minimiser(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed",
            strict_mode=False  # Allow manual reassignment
        )
        
        # Add a patient normally first
        characteristics = {'gender': 'male', 'age_group': '<=50'}
        original_arm = minimiser.randomise_patient("patient1", characteristics)
        
        # Make sure it's not already in the target arm for the test
        new_arm = "B" if original_arm == "A" else "A"
        
        # Now reassign
        minimiser.reassign_arm("patient1", new_arm)
        
        # Check that arm is updated
        self.assertEqual(minimiser.df_patients.loc["patient1", "arm"], new_arm)
        
        # Check that we can't reassign in strict mode
        minimiser.strict_mode = True
        with self.assertRaises(ValueError):
            minimiser.reassign_arm("patient1", original_arm)
            
    def test_to_from_dict(self):
        """Test serialization and deserialization."""
        minimiser = Minimiser(
            trial_id=self.trial_id,
            minimisation_vars=self.minimisation_vars,
            arms=self.arms,
            seed="test_seed"
        )
        
        # Add some patients
        minimiser.randomise_patient("patient1", {'gender': 'male', 'age_group': '<=50'})
        minimiser.randomise_patient("patient2", {'gender': 'female', 'age_group': '>50'})
        
        # Convert to dict
        data = minimiser.to_dict()
        
        # Create a new minimiser from dict
        minimiser2 = Minimiser.from_dict(data)
        
        # Check that all properties are preserved
        self.assertEqual(minimiser2.trial_id, minimiser.trial_id)
        self.assertEqual(minimiser2.minimisation_vars, minimiser.minimisation_vars)
        self.assertEqual(minimiser2.arms, minimiser.arms)
        self.assertEqual(minimiser2.seed, minimiser.seed)
        self.assertEqual(minimiser2.strict_mode, minimiser.strict_mode)
        
        # Check that patient data is preserved
        self.assertEqual(minimiser2.get_n_patients(), minimiser.get_n_patients())
        self.assertTrue("patient1" in minimiser2.df_patients.index)
        self.assertTrue("patient2" in minimiser2.df_patients.index)
        self.assertEqual(
            minimiser2.df_patients.loc["patient1", "gender"], 
            minimiser.df_patients.loc["patient1", "gender"]
        )

if __name__ == '__main__':
    unittest.main() 