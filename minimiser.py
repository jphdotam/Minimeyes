import hashlib
import numpy as np
import pandas as pd
from collections import Counter
import json
import os
from datetime import datetime

class Minimiser:
    def __init__(self, trial_id, minimisation_vars: dict, arms=('A', 'B'), minimisation_weight=0.8,
                 seed=None, strict_mode=True):
        """Creates a minimisation instance which can be fed patients to randomise.

        Arguments:
            trial_id: Unique identifier for the trial
            minimisation_vars: a dictionary of variable names (keys) and tuples of categories (values)
            arms: A tuple containing the names of the arms
            minimisation_weight: float containing what % of the time the randomisation is governed by the minimisation
                algorithm rather than by random allocation.
            seed: A seed value to use for deterministic randomization
            strict_mode: If True, uses strict minimisation. If False, allows manual arm assignment.
        """
        assert 'arm' not in minimisation_vars
        self.trial_id = trial_id
        self.minimisation_vars = minimisation_vars
        self.arms = arms
        self.minimisation_weight = minimisation_weight
        self.seed = seed if seed is not None else "default_seed"
        self.strict_mode = strict_mode
        self.df_patients = self.create_patient_dataframe()
        
    def __repr__(self):
        return f"Minimiser for trial '{self.trial_id}' with {len(self.minimisation_vars.keys())} variables " \
               f"({', '.join(self.minimisation_vars.keys())}) - " \
               f"{self.get_active_patients()} active patients of {self.df_patients.shape[0]} total"
    
    def get_active_patients(self):
        """Returns the number of active patients."""
        if self.df_patients.empty:
            return 0
        return self.df_patients[self.df_patients['active'] == True].shape[0]
    
    def characteristics_by_arm(self) -> pd.DataFrame:
        """Returns a dataframe showing counts of each characteristic by arm, only for active patients."""
        active_patients = self.df_patients[self.df_patients['active'] == True]
        return active_patients.groupby(['arm']).aggregate(Counter)

    def create_patient_dataframe(self) -> pd.DataFrame:
        """Returns a dataframe with a column for each minimisation variable, arm and active status"""
        columns = list(self.minimisation_vars.keys())
        columns.extend(['arm', 'active'])
        dtypes = np.dtype([(k, str) for k in columns[:-1]] + [('active', bool)])
        data = np.empty(0, dtype=dtypes)
        return pd.DataFrame(data)

    def get_n_patients(self) -> int:
        return self.df_patients.shape[0]

    def check_valid_characteristics(self, characteristics: dict) -> bool:
        pt_chars = sorted(characteristics.keys())
        needed_chars = sorted(self.minimisation_vars.keys())

        if pt_chars != needed_chars:
            raise ValueError(f"Characteristics of patient do not match those needed: {pt_chars} vs {needed_chars}")

        for pt_char in pt_chars:
            if characteristics[pt_char] not in self.minimisation_vars[pt_char]:
                raise ValueError(f"Invalid value {characteristics[pt_char]} for characteristic {pt_char} - "
                                 f"Should one of {self.minimisation_vars[pt_char]}")

        return True

    def deterministic_random(self, patient_id):
        """Generate a deterministic random value based on patient ID and seed."""
        hash_input = f"{patient_id}_{self.seed}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()
        # Convert first 8 characters of hash to a number between 0 and 1
        return int(hash_value[:8], 16) / 0xffffffff

    def randomise_patient(self, id, characteristics: dict, manual_arm=None):
        """Supply with a dictionary with a key/value for every minimisation var, and also an 'id' key"""
        self.check_valid_characteristics(characteristics)
        
        # Allow manual arm assignment in non-strict mode
        if not self.strict_mode and manual_arm is not None:
            if manual_arm not in self.arms:
                raise ValueError(f"Manual arm {manual_arm} is not one of the trial arms: {self.arms}")
            arm = manual_arm
        else:
            # Determine arm algorithmically
            # See if first patient in trial
            if self.get_n_patients() == 0:
                # Use deterministic randomization instead of Python's random
                rand = self.deterministic_random(id)
                arm_index = int(rand * len(self.arms))
                arm = self.arms[arm_index]
            # If not first patient
            else:
                rand = self.deterministic_random(f"{id}_allocation")
                if rand <= self.minimisation_weight:
                    arm = self.get_minimised_arm(characteristics)
                else:
                    rand = self.deterministic_random(id)
                    arm_index = int(rand * len(self.arms))
                    arm = self.arms[arm_index]

        self._add_patient_to_arm(id, characteristics, arm)
        return arm

    def get_minimised_arm(self, characteristics: dict) -> str:
        arm_totals = {a: 0 for a in self.arms}
        active_patients = self.df_patients[self.df_patients['active'] == True]
        
        for char_name, char_val in characteristics.items():
            assert char_val in self.minimisation_vars[char_name], \
                f"Value for {char_name} must be {self.minimisation_vars[char_name]} but got {char_val}"
            for arm in self.arms:
                arm_totals[arm] += active_patients[
                    (active_patients['arm'] == arm) & 
                    (active_patients[char_name] == char_val)
                ].shape[0]

        min_arm, min_val = min(arm_totals.items(), key=lambda x: x[1])
        max_arm, max_val = max(arm_totals.items(), key=lambda x: x[1])

        if min_val == max_val:  # Either both are 0 (first patient with any of these characteristics) or a draw
            # Use deterministic hash
            rand = self.deterministic_random(f"minimisation_tie_{list(characteristics.values())}")
            arm_index = int(rand * len(self.arms))
            arm = self.arms[arm_index]
        else:
            arm = min_arm

        return arm

    def _add_patient_to_arm(self, id: str, characteristics: dict, arm: str):
        if id in list(self.df_patients.index.values):
            raise AttributeError(f"Patient {id} already in randomised list ({self.df_patients.index.values})!")
        characteristics['arm'] = arm
        characteristics['active'] = True
        df_patient = pd.DataFrame(characteristics, index=[id])
        self.df_patients = pd.concat([self.df_patients, df_patient])

    def deactivate_patient(self, patient_id):
        """Deactivate a patient (mark as inactive but keep in dataset)."""
        if patient_id not in self.df_patients.index:
            raise ValueError(f"Patient {patient_id} not found in the dataset")
        self.df_patients.at[patient_id, 'active'] = False
        
    def reactivate_patient(self, patient_id):
        """Reactivate a previously deactivated patient."""
        if patient_id not in self.df_patients.index:
            raise ValueError(f"Patient {patient_id} not found in the dataset")
        self.df_patients.at[patient_id, 'active'] = True
        
    def reassign_arm(self, patient_id, new_arm):
        """Reassign a patient to a different arm (only in non-strict mode)."""
        if self.strict_mode:
            raise ValueError("Cannot reassign arms in strict minimisation mode")
        if patient_id not in self.df_patients.index:
            raise ValueError(f"Patient {patient_id} not found in the dataset")
        if new_arm not in self.arms:
            raise ValueError(f"Arm {new_arm} is not one of the trial arms: {self.arms}")
        self.df_patients.at[patient_id, 'arm'] = new_arm
        
    def to_dict(self):
        """Convert the minimiser to a dictionary for storage."""
        return {
            'trial_id': self.trial_id,
            'minimisation_vars': self.minimisation_vars,
            'arms': self.arms,
            'minimisation_weight': self.minimisation_weight,
            'seed': self.seed,
            'strict_mode': self.strict_mode,
            'patients': self.df_patients.reset_index().rename(columns={'index': 'id'}).to_dict(orient='records')
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create a minimiser from a dictionary."""
        minimiser = cls(
            trial_id=data['trial_id'],
            minimisation_vars=data['minimisation_vars'],
            arms=data['arms'],
            minimisation_weight=data['minimisation_weight'],
            seed=data['seed'],
            strict_mode=data['strict_mode']
        )
        
        if 'patients' in data and data['patients']:
            patients_df = pd.DataFrame(data['patients'])
            patients_df.set_index('id', inplace=True)
            minimiser.df_patients = patients_df
            
        return minimiser 