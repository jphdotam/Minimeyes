import os
import json
import pandas as pd
from datetime import datetime
from minimiser import Minimiser
import shutil

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
            raise ValueError(f"Trial with ID '{trial_id}' already exists. Please choose a different trial ID.")
        
        # Create trial directory
        os.makedirs(trial_dir, exist_ok=False)  # Using exist_ok=False for clarity
        
        # Create audit directory
        audit_dir = os.path.join(trial_dir, "audit")
        os.makedirs(audit_dir, exist_ok=True)
        
        # Create the minimiser instance
        minimiser = Minimiser(
            trial_id=trial_id,
            minimisation_vars=minimisation_vars,
            arms=arms,
            minimisation_weight=minimisation_weight,
            seed=seed,
            strict_mode=strict_mode
        )
        
        # Save configuration
        config_file = os.path.join(trial_dir, "config.json")
        with open(config_file, 'w') as f:
            json.dump(minimiser.to_dict(), f, indent=2)
        
        # Save initial state
        state_file = os.path.join(trial_dir, "current_state.json")
        with open(state_file, 'w') as f:
            json.dump(minimiser.to_dict(), f, indent=2)
        
        # Add initial audit entry
        self._create_audit_entry(
            trial_id=trial_id,
            action="create_trial",
            data={
                "minimisation_vars": minimisation_vars,
                "arms": arms,
                "minimisation_weight": minimisation_weight,
                "seed": seed,
                "strict_mode": strict_mode
            },
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
        """Add a patient to a trial."""
        # Load the trial
        minimiser = self.load_trial(trial_id)
        
        # Randomise the patient
        if manual_arm:
            if minimiser.strict_mode:
                raise ValueError("Cannot manually assign arm in strict mode")
            arm = minimiser.add_patient(patient_id, characteristics, manual_arm)
        else:
            arm = minimiser.randomise_patient(patient_id, characteristics)
        
        # Save the updated state
        trial_dir = os.path.join(self.base_dir, trial_id)
        state_file = os.path.join(trial_dir, "current_state.json")
        with open(state_file, 'w') as f:
            json.dump(minimiser.to_dict(), f, indent=2)
        
        # Create audit entry
        self._create_audit_entry(
            trial_id=trial_id,
            action="add_patient",
            data={
                "patient_id": patient_id,
                "characteristics": characteristics,
                "arm": arm,
                "manual": manual_arm is not None
            },
            user=user
        )
        
        return arm
    
    def change_patient_status(self, trial_id, patient_id, active, user=None):
        """Change a patient's active status."""
        # Load the trial
        minimiser = self.load_trial(trial_id)
        
        # Change status
        minimiser.change_patient_status(patient_id, active)
        
        # Save the updated state
        trial_dir = os.path.join(self.base_dir, trial_id)
        state_file = os.path.join(trial_dir, "current_state.json")
        with open(state_file, 'w') as f:
            json.dump(minimiser.to_dict(), f, indent=2)
        
        # Create audit entry
        self._create_audit_entry(
            trial_id=trial_id,
            action="change_status",
            data={
                "patient_id": patient_id,
                "active": active
            },
            user=user
        )
    
    def reassign_arm(self, trial_id, patient_id, new_arm, user=None):
        """Reassign a patient to a different arm."""
        # Load the trial
        minimiser = self.load_trial(trial_id)
        
        # Reassign arm
        minimiser.reassign_arm(patient_id, new_arm)
        
        # Save the updated state
        trial_dir = os.path.join(self.base_dir, trial_id)
        state_file = os.path.join(trial_dir, "current_state.json")
        with open(state_file, 'w') as f:
            json.dump(minimiser.to_dict(), f, indent=2)
        
        # Create audit entry
        self._create_audit_entry(
            trial_id=trial_id,
            action="reassign_arm",
            data={
                "patient_id": patient_id,
                "new_arm": new_arm
            },
            user=user
        )
    
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
    
    def archive_trial(self, trial_id, archived_trial_id=None):
        """Archive a trial by moving it to the archived directory."""
        # Generate an archived trial ID if none provided
        if archived_trial_id is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archived_trial_id = f"{trial_id}_{timestamp}"
        
        # Create archives directory if it doesn't exist
        archives_dir = os.path.join(os.path.dirname(self.base_dir), "trials_archived")
        os.makedirs(archives_dir, exist_ok=True)
        
        # Source and destination paths
        src_dir = os.path.join(self.base_dir, trial_id)
        dst_dir = os.path.join(archives_dir, archived_trial_id)
        
        # Check if trial exists
        if not os.path.exists(src_dir):
            raise ValueError(f"Trial '{trial_id}' does not exist.")
        
        # Check if destination already exists
        if os.path.exists(dst_dir):
            raise ValueError(f"Archived trial '{archived_trial_id}' already exists.")
        
        # Move the directory (this preserves all files and subdirectories)
        shutil.move(src_dir, dst_dir)
        
        # Return the archived trial ID
        return archived_trial_id 