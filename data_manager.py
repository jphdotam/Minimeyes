import os
import json
import pandas as pd
from datetime import datetime
from minimiser import Minimiser

class DataManager:
    def __init__(self, base_dir="trials"):
        """Initialize the data manager with a base directory for storing trials."""
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        
    def create_trial(self, trial_id, minimisation_vars, arms=('A', 'B'), 
                    minimisation_weight=0.8, seed=None, strict_mode=True, user=None):
        """Create a new trial and save its configuration."""
        # Check if trial already exists
        trial_dir = os.path.join(self.base_dir, trial_id)
        if os.path.exists(trial_dir):
            raise ValueError(f"Trial with ID '{trial_id}' already exists.")
        
        # Create trial directory
        os.makedirs(trial_dir, exist_ok=True)
        os.makedirs(os.path.join(trial_dir, "audit"), exist_ok=True)
        
        # Create minimiser instance
        minimiser = Minimiser(
            trial_id=trial_id,
            minimisation_vars=minimisation_vars,
            arms=arms,
            minimisation_weight=minimisation_weight,
            seed=seed,
            strict_mode=strict_mode
        )
        
        # Save trial configuration
        config = {
            'trial_id': trial_id,
            'minimisation_vars': minimisation_vars,
            'arms': arms,
            'minimisation_weight': minimisation_weight,
            'seed': seed,
            'strict_mode': strict_mode,
            'created_at': datetime.now().isoformat(),
            'created_by': user
        }
        
        with open(os.path.join(trial_dir, "config.json"), 'w') as f:
            json.dump(config, f, indent=2)
            
        # Create audit entry for trial creation
        self._create_audit_entry(
            trial_id=trial_id,
            action="create_trial",
            data=config,
            user=user
        )
        
        return minimiser
    
    def list_trials(self):
        """List all trials with their basic information."""
        trials = []
        
        for trial_id in os.listdir(self.base_dir):
            trial_dir = os.path.join(self.base_dir, trial_id)
            if os.path.isdir(trial_dir):
                config_file = os.path.join(trial_dir, "config.json")
                if os.path.exists(config_file):
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    
                    # Load minimiser to get patient counts
                    minimiser = self.load_trial(trial_id)
                    
                    trials.append({
                        'trial_id': trial_id,
                        'minimisation_vars': config['minimisation_vars'],
                        'arms': config['arms'],
                        'strict_mode': config['strict_mode'],
                        'total_patients': minimiser.get_n_patients(),
                        'active_patients': minimiser.get_active_patients()
                    })
                    
        return trials
    
    def load_trial(self, trial_id):
        """Load a trial's minimiser instance."""
        trial_dir = os.path.join(self.base_dir, trial_id)
        if not os.path.exists(trial_dir):
            raise ValueError(f"Trial with ID '{trial_id}' does not exist.")
            
        config_file = os.path.join(trial_dir, "config.json")
        with open(config_file, 'r') as f:
            config = json.load(f)
            
        minimiser = Minimiser(
            trial_id=config['trial_id'],
            minimisation_vars=config['minimisation_vars'],
            arms=config['arms'],
            minimisation_weight=config['minimisation_weight'],
            seed=config['seed'],
            strict_mode=config['strict_mode']
        )
        
        # Load patients from the latest state
        state_file = os.path.join(trial_dir, "current_state.json")
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
                if 'patients' in state and state['patients']:
                    patients_df = pd.DataFrame(state['patients'])
                    patients_df.set_index('id', inplace=True)
                    minimiser.df_patients = patients_df
                    
        return minimiser
    
    def save_trial_state(self, minimiser, user=None):
        """Save the current state of a trial."""
        trial_id = minimiser.trial_id
        trial_dir = os.path.join(self.base_dir, trial_id)
        
        # Prepare state data
        state = minimiser.to_dict()
        state['updated_at'] = datetime.now().isoformat()
        state['updated_by'] = user
        
        # Save current state
        with open(os.path.join(trial_dir, "current_state.json"), 'w') as f:
            json.dump(state, f, indent=2)
            
        return state
    
    def add_patient(self, trial_id, patient_id, characteristics, manual_arm=None, user=None):
        """Add a new patient to a trial."""
        minimiser = self.load_trial(trial_id)
        
        # Randomise the patient
        arm = minimiser.randomise_patient(patient_id, characteristics, manual_arm)
        
        # Create audit entry
        self._create_audit_entry(
            trial_id=trial_id,
            action="add_patient",
            data={
                'patient_id': patient_id,
                'characteristics': characteristics,
                'assigned_arm': arm,
                'manual_arm': manual_arm
            },
            user=user
        )
        
        # Save updated state
        self.save_trial_state(minimiser, user)
        
        return arm
    
    def change_patient_status(self, trial_id, patient_id, active, user=None):
        """Activate or deactivate a patient."""
        minimiser = self.load_trial(trial_id)
        
        if active:
            minimiser.reactivate_patient(patient_id)
            action = "reactivate_patient"
        else:
            minimiser.deactivate_patient(patient_id)
            action = "deactivate_patient"
            
        # Create audit entry
        self._create_audit_entry(
            trial_id=trial_id,
            action=action,
            data={'patient_id': patient_id},
            user=user
        )
        
        # Save updated state
        self.save_trial_state(minimiser, user)
    
    def reassign_arm(self, trial_id, patient_id, new_arm, user=None):
        """Reassign a patient to a different arm."""
        minimiser = self.load_trial(trial_id)
        
        # Get current arm before reassignment
        current_arm = None
        if patient_id in minimiser.df_patients.index:
            current_arm = minimiser.df_patients.at[patient_id, 'arm']
            
        # Reassign arm
        minimiser.reassign_arm(patient_id, new_arm)
        
        # Create audit entry
        self._create_audit_entry(
            trial_id=trial_id,
            action="reassign_arm",
            data={
                'patient_id': patient_id,
                'previous_arm': current_arm,
                'new_arm': new_arm
            },
            user=user
        )
        
        # Save updated state
        self.save_trial_state(minimiser, user)
    
    def _create_audit_entry(self, trial_id, action, data, user=None):
        """Create an audit entry for an action."""
        trial_dir = os.path.join(self.base_dir, trial_id)
        audit_dir = os.path.join(trial_dir, "audit")
        
        # Ensure audit directory exists
        os.makedirs(audit_dir, exist_ok=True)
        
        # Create audit entry
        timestamp = datetime.now()
        entry = {
            'timestamp': timestamp.isoformat(),
            'action': action,
            'data': data,
            'user': user
        }
        
        # Generate filename with timestamp
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}_{action}.json"
        
        # Save audit entry
        with open(os.path.join(audit_dir, filename), 'w') as f:
            json.dump(entry, f, indent=2)
            
        return entry
    
    def get_audit_trail(self, trial_id):
        """Get the audit trail for a trial."""
        trial_dir = os.path.join(self.base_dir, trial_id)
        audit_dir = os.path.join(trial_dir, "audit")
        
        if not os.path.exists(audit_dir):
            return []
            
        audit_entries = []
        for filename in sorted(os.listdir(audit_dir)):
            if filename.endswith('.json'):
                with open(os.path.join(audit_dir, filename), 'r') as f:
                    entry = json.load(f)
                    audit_entries.append(entry)
                    
        return audit_entries 