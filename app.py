import streamlit as st
import pandas as pd
import numpy as np
import os
import traceback
import uuid
import random
import string
import shutil
from auth import AuthManager
from data_manager import DataManager
from minimiser import Minimiser
from datetime import datetime
import time


# Set page config first - this must be the first Streamlit command
st.set_page_config(page_title="Minimisation WebApp", layout="wide")

# Wrap everything in a try-except to catch errors
try:
    # Initialize managers
    auth_manager = AuthManager()
    data_manager = DataManager()

    # Make sure we have a default admin user
    def setup_first_run():
        """Show first-run setup screen to create initial admin account."""
        st.title("First-Time Setup - Create Admin Account")
        st.info("Welcome to Minimisation WebApp! Since this is your first time running the application, please create an administrator account.")
        
        with st.form("admin_setup_form"):
            admin_username = st.text_input("Admin Username")
            admin_name = st.text_input("Admin Name (Full Name)")
            admin_password = st.text_input("Admin Password", type="password")
            admin_password_confirm = st.text_input("Confirm Password", type="password")
            
            submit = st.form_submit_button("Create Admin Account")
            
            if submit:
                # Validate inputs
                if not admin_username or not admin_name or not admin_password:
                    st.error("All fields are required")
                    return False
                    
                if admin_password != admin_password_confirm:
                    st.error("Passwords do not match")
                    return False
                    
                # Create the admin user
                try:
                    auth_manager.create_user(admin_username, admin_password, admin_name, admin=True)
                    st.success("Admin account created successfully!")
                    time.sleep(2)  # Give user time to see success message
                    return True
                except Exception as e:
                    st.error(f"Error creating admin account: {str(e)}")
                    return False
        
        # If the form wasn't submitted, we're still in setup
        return False

    # Session state initialization
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "username" not in st.session_state:
        st.session_state.username = None
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "current_trial" not in st.session_state:
        st.session_state.current_trial = None
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False
    if "reveal_arms" not in st.session_state:
        st.session_state.reveal_arms = False
    if "confirm_archive" not in st.session_state:
        st.session_state.confirm_archive = False
    
    # Helper function to generate a random seed
    def generate_random_seed():
        return ''.join(random.choices(string.ascii_letters + string.digits, k=16))

    # Authentication
    def login_form():
        st.title("Minimisation WebApp - Login")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                session_id = auth_manager.authenticate(username, password)
                if session_id:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.session_id = session_id
                    st.rerun()
                else:
                    st.error("Invalid username or password")

    def logout():
        if st.session_state.session_id:
            auth_manager.logout(st.session_state.session_id)
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.session_id = None
        st.session_state.current_trial = None
        st.rerun()

    # Home screen
    def home_screen():
        st.title("Minimisation WebApp - Trials")
        
        # User info and logout
        st.sidebar.write(f"Logged in as: {st.session_state.username}")
        if st.sidebar.button("Logout"):
            logout()
        
        # Create new trial button
        if st.sidebar.button("Create New Trial"):
            st.session_state.current_trial = "new"
            st.rerun()
        
        # List trials
        trials = data_manager.list_trials()
        
        if not trials:
            st.info("No trials found. Create a new trial to get started.")
            return
        
        st.write("### Available Trials")
        
        # Display trials as cards
        cols = st.columns(2)
        for i, trial in enumerate(trials):
            user_info = auth_manager.get_user_info(st.session_state.username)
            if user_info["admin"] or trial["trial_id"] in user_info.get("trial_access", []):
                with cols[i % 2]:
                    st.write(f"#### {trial['trial_id']}")
                    st.write(f"**Mode:** {'Strict Minimisation' if trial['strict_mode'] else 'Non-Randomised, Balanced'}")
                    st.write(f"**Arms:** {', '.join(trial['arms'])}")
                    st.write(f"**Minimisation Variables:**")
                    for var, values in trial['minimisation_vars'].items():
                        st.write(f"- {var}: {', '.join(values)}")
                    
                    active_count = trial['active_patients']
                    total_count = trial['total_patients']
                    
                    if active_count == total_count:
                        st.write(f"**Patients:** {total_count}")
                    else:
                        st.write(f"**Patients:** {active_count} active (of {total_count} total)")
                    
                    if st.button("Open Trial", key=f"open_{trial['trial_id']}"):
                        st.session_state.current_trial = trial['trial_id']
                        st.session_state.edit_mode = False
                        st.session_state.reveal_arms = False
                        st.rerun()

    # Create new trial
    def create_trial_screen():
        st.title("Create New Trial")
        
        if st.sidebar.button("Back to Home"):
            st.session_state.current_trial = None
            st.rerun()
        
        # Initialize or retrieve form state
        if "trial_form" not in st.session_state:
            st.session_state.trial_form = {
                "n_vars": 1,
                "vars": [{"name": "", "values": ""}]
            }
        
        # Counter for minimisation variables
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("### Number of Minimisation Variables")
        with col2:
            # Create buttons for incrementing/decrementing
            col_minus, col_count, col_plus = st.columns([1, 1, 1])
            with col_minus:
                if st.button("➖", key="minus_var", disabled=st.session_state.trial_form["n_vars"] <= 1):
                    st.session_state.trial_form["n_vars"] -= 1
                    if len(st.session_state.trial_form["vars"]) > st.session_state.trial_form["n_vars"]:
                        st.session_state.trial_form["vars"] = st.session_state.trial_form["vars"][:st.session_state.trial_form["n_vars"]]
                    st.rerun()
            
            with col_count:
                st.write(f"<h3 style='text-align: center;'>{st.session_state.trial_form['n_vars']}</h3>", unsafe_allow_html=True)
            
            with col_plus:
                if st.button("➕", key="plus_var", disabled=st.session_state.trial_form["n_vars"] >= 10):
                    st.session_state.trial_form["n_vars"] += 1
                    if len(st.session_state.trial_form["vars"]) < st.session_state.trial_form["n_vars"]:
                        st.session_state.trial_form["vars"].append({"name": "", "values": ""})
                    st.rerun()
        
        with st.form("create_trial_form"):
            # Trial basic info
            trial_id = st.text_input("Trial ID", help="Unique identifier for the trial")
            
            # Generate random seed by default
            default_seed = generate_random_seed()
            seed = st.text_input(
                "Randomisation Seed", 
                value=default_seed,
                help="Seed value used for deterministic randomization. This ensures consistent results when re-running the same patients."
            )
            
            strict_mode = st.checkbox(
                "Strict Minimisation", 
                value=True,
                help="If checked, uses strict minimisation with randomisation. If unchecked, allows manual arm assignment."
            )
            
            minimisation_weight = st.slider(
                "Minimisation Weight", 
                min_value=0.0, 
                max_value=1.0, 
                value=0.8, 
                step=0.1,
                help="Percentage of time the randomisation is governed by minimisation algorithm rather than by random allocation. 1.0 means always use minimisation."
            )
            
            arms_text = st.text_input(
                "Arms (comma-separated)", 
                value="A,B",
                help="Comma-separated list of treatment arms"
            )
            
            # Create inputs for each minimisation variable
            st.write("### Minimisation Variables")
            
            var_inputs = []
            for i in range(st.session_state.trial_form["n_vars"]):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input(
                        f"Variable {i+1} Name", 
                        value=st.session_state.trial_form["vars"][i]["name"],
                        key=f"var_name_{i}"
                    )
                
                with col2:
                    values = st.text_input(
                        f"Variable {i+1} Values (comma-separated)", 
                        value=st.session_state.trial_form["vars"][i]["values"],
                        key=f"var_values_{i}"
                    )
                
                st.session_state.trial_form["vars"][i]["name"] = name
                st.session_state.trial_form["vars"][i]["values"] = values
                var_inputs.append((name, values))
            
            submitted = st.form_submit_button("Create Trial")
            
            if submitted:
                # Validate inputs
                if not trial_id:
                    st.error("Trial ID is required")
                    return
                
                if not seed:
                    st.error("Randomisation Seed is required")
                    return
                
                # Parse arms
                try:
                    arms = tuple(arm.strip() for arm in arms_text.split(",") if arm.strip())
                    if len(arms) < 2:
                        st.error("At least two arms are required")
                        return
                except:
                    st.error("Invalid arm format. Please use comma-separated values.")
                    return
                
                # Parse minimisation variables
                minimisation_vars = {}
                for var_name, var_values_str in var_inputs:
                    if not var_name or not var_values_str:
                        continue
                    
                    try:
                        values = tuple(val.strip() for val in var_values_str.split(",") if val.strip())
                        if len(values) < 2:
                            st.error(f"Variable '{var_name}' needs at least two values")
                            return
                        minimisation_vars[var_name] = values
                    except:
                        st.error(f"Invalid format for variable '{var_name}'. Please use comma-separated values.")
                        return
                
                if not minimisation_vars:
                    st.error("At least one valid minimisation variable is required")
                    return
                
                try:
                    # Create the trial
                    data_manager.create_trial(
                        trial_id=trial_id,
                        minimisation_vars=minimisation_vars,
                        arms=arms,
                        minimisation_weight=minimisation_weight,
                        seed=seed,
                        strict_mode=strict_mode,
                        user=st.session_state.username
                    )
                    
                    # Grant the user access to the trial
                    auth_manager.grant_trial_access(st.session_state.username, trial_id)
                    
                    # Reset form state
                    st.session_state.trial_form = {
                        "n_vars": 1,
                        "vars": [{"name": "", "values": ""}]
                    }
                    
                    st.success(f"Trial '{trial_id}' created successfully!")
                    st.session_state.current_trial = trial_id
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating trial: {str(e)}")

    # Archive trial
    def archive_trial(trial_id):
        """Archive a trial by moving it to the archived directory."""
        try:
            # Generate timestamp for unique archiving
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archived_trial_id = f"{trial_id}_{timestamp}"
            
            # Call data manager to archive the trial
            data_manager.archive_trial(trial_id, archived_trial_id)
            
            # Log the action
            st.success(f"Trial '{trial_id}' has been archived.")
            
            # Return to home screen
            st.session_state.current_trial = None
            st.rerun()
        except Exception as e:
            st.error(f"Error archiving trial: {str(e)}")
            st.code(traceback.format_exc())

    # Trial detail screen
    def trial_detail_screen(trial_id):
        """Display details for a specific trial."""
        try:
            # Load the trial
            minimiser = data_manager.load_trial(trial_id)
            
            st.title(f"Trial: {trial_id}")
            
            # Navigation buttons in sidebar
            if st.sidebar.button("Back to Home"):
                st.session_state.current_trial = None
                st.rerun()
            
            # Add tab navigation for different views
            tab1, tab2, tab3 = st.tabs(["Trial Info", "Patient Management", "Balance Tables"])
            
            with tab1:
                # Display trial information
                st.write("### Trial Information")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Mode:** {'Strict Minimisation' if minimiser.strict_mode else 'Non-Randomised, Balanced'}")
                    st.write(f"**Arms:** {', '.join(minimiser.arms)}")
                    st.write(f"**Minimisation Weight:** {minimiser.minimisation_weight}")
                
                with col2:
                    st.write("**Minimisation Variables:**")
                    for var_name, values in minimiser.minimisation_vars.items():
                        st.write(f"- {var_name}: {', '.join(values)}")
                
                # Add audit trail button
                if st.button("View Audit Trail"):
                    audit_entries = data_manager.get_audit_trail(trial_id)
                    
                    st.write("### Audit Trail")
                    for entry in audit_entries:
                        with st.expander(f"{entry['action']} - {entry['timestamp']} by {entry['user']}"):
                            st.json(entry['data'])
            
            with tab2:
                # Patient management section
                st.write("### Patient Management")
                
                # First check if there are patients to display
                has_patients = not minimiser.df_patients.empty
                
                # Display patients if available
                if has_patients:
                    # Patient table display controls
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Toggle Edit Mode"):
                            st.session_state.edit_mode = not st.session_state.edit_mode
                            st.rerun()
                    
                    with col2:
                        if st.button("Toggle Arms Display"):
                            st.session_state.reveal_arms = not st.session_state.reveal_arms
                            st.rerun()
                            
                    # Display patient table
                    display_patient_table(trial_id, minimiser)
                else:
                    st.info("No patients in this trial yet.")
                
                # Add patient section - always below the patient table
                if "add_patient" not in st.session_state:
                    st.session_state.add_patient = False
                    
                # Show either the Add Patient button or the form
                if st.session_state.add_patient:
                    # Don't call st.rerun() inside the form - it will be handled by form buttons
                    add_patient_form(trial_id, minimiser)
                else:
                    if st.button("Add Patient"):
                        st.session_state.add_patient = True
                        st.rerun()
                    
            with tab3:
                # Display minimisation balance tables
                display_minimisation_table(minimiser)
                    
        except Exception as e:
            st.error(f"Error loading trial: {str(e)}")
            st.code(traceback.format_exc())
            # Don't reset the current_trial state on error

    def display_patient_table(trial_id, minimiser):
        """Display a table of patients with their characteristics."""
        try:
            if minimiser.df_patients.empty:
                st.info("No patients in this trial yet.")
                return
            
            # Start with a fresh copy of the dataframe
            df = minimiser.df_patients.copy()
            
            # Reset index to create an actual ID column
            df = df.reset_index()
            df = df.rename(columns={'index': 'id'})
            
            # Determine which columns to display
            display_cols = ['id'] 
            for var_name in minimiser.minimisation_vars.keys():
                if var_name in df.columns:
                    display_cols.append(var_name)
            
            # Add arm column if needed
            if st.session_state.reveal_arms and 'arm' in df.columns:
                display_cols.append('arm')
            
            # Add active status
            if 'active' in df.columns:
                display_cols.append('active')
            
            # Ensure all required columns exist
            missing_cols = [col for col in display_cols if col not in df.columns]
            if missing_cols:
                st.error(f"Missing columns in patient data: {missing_cols}")
                return
            
            # Create the display dataframe
            df_display = df[display_cols].copy()
            
            # Format the data for display
            if 'active' in df_display.columns:
                df_display['active'] = df_display['active'].map({True: 'Active', False: 'Inactive'})
            
            # Display the table
            if st.session_state.edit_mode:
                edit_df = st.data_editor(
                    df_display,
                    key="patient_editor",
                    disabled=display_cols[:-1] if minimiser.strict_mode else [col for col in display_cols if col != 'arm' and col != 'active'],
                    column_config={
                        "active": st.column_config.SelectboxColumn(
                            options=["Active", "Inactive"],
                            required=True,
                        ),
                        "arm": st.column_config.SelectboxColumn(
                            options=minimiser.arms,
                            disabled=minimiser.strict_mode,
                            required=True,
                        ) if 'arm' in display_cols else None,
                    },
                    hide_index=True,
                )
                
                # Process changes when save is clicked
                if st.button("Save Changes"):
                    # Initialize change buffer if not exists
                    if 'change_buffer' not in st.session_state:
                        st.session_state.change_buffer = {
                            'status_changes': {},
                            'arm_changes': {}
                        }
                    
                    # Compare edit_df with original df to detect changes
                    for _, row in edit_df.iterrows():
                        patient_id = row['id']
                        
                        # Check for status changes
                        active_status = row['active'] == 'Active'
                        if active_status != df.loc[df['id'] == patient_id, 'active'].values[0]:
                            st.session_state.change_buffer['status_changes'][patient_id] = active_status
                        
                        # Check for arm changes (if in non-randomised mode)
                        if not minimiser.strict_mode and 'arm' in row:
                            if row['arm'] != df.loc[df['id'] == patient_id, 'arm'].values[0]:
                                st.session_state.change_buffer['arm_changes'][patient_id] = row['arm']
                    
                    # Process changes
                    process_changes(trial_id, st.session_state.change_buffer)
                    
                    # Clear change buffer
                    st.session_state.change_buffer = {
                        'status_changes': {},
                        'arm_changes': {}
                    }
                    
                    # Exit edit mode
                    st.session_state.edit_mode = False
                    st.rerun()
                
                if st.button("Cancel"):
                    st.session_state.edit_mode = False
                    st.rerun()
            else:
                # Just display the table
                st.dataframe(df_display, hide_index=True)
            
        except Exception as e:
            st.error(f"Error displaying patient table: {str(e)}")
            st.code(traceback.format_exc())

    def process_changes(trial_id, change_buffer):
        """Process changes from the edit buffer."""
        # Process status changes
        for patient_id, active in change_buffer['status_changes'].items():
            data_manager.change_patient_status(
                trial_id=trial_id,
                patient_id=patient_id,
                active=active,
                user=st.session_state.username
            )
        
        # Process arm changes
        for patient_id, new_arm in change_buffer['arm_changes'].items():
            data_manager.reassign_arm(
                trial_id=trial_id,
                patient_id=patient_id,
                new_arm=new_arm,
                user=st.session_state.username
            )

    def add_patient_form(trial_id, minimiser):
        st.write("### Add Patient")
        
        # Validate form flag
        valid_form = True
        
        with st.form("add_patient_form"):
            patient_id = st.text_input("Patient ID")
            
            # Create inputs for each minimisation variable
            characteristics = {}
            for var_name, var_values in minimiser.minimisation_vars.items():
                characteristics[var_name] = st.selectbox(
                    f"{var_name}", 
                    options=[""] + list(var_values),  # Add blank option first
                    index=0  # Default to blank
                )
            
            # For non-randomised mode, add option to manually specify arm
            manual_arm = None
            if not minimiser.strict_mode:
                allocation_method = st.radio("Allocation Method", ["Minimise", "Specify Arm"])
                
                if allocation_method == "Specify Arm":
                    manual_arm = st.selectbox("Arm", options=minimiser.arms)
            
            # Submit and cancel buttons
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("Add Patient")
            with col2:
                cancel = st.form_submit_button("Cancel")
            
            if submit:
                # Validate all characteristics are filled
                empty_fields = [var_name for var_name, value in characteristics.items() if value == ""]
                if empty_fields:
                    for field in empty_fields:
                        st.error(f"Please select a value for {field}")
                    return
                    
                if not patient_id:
                    st.error("Patient ID is required")
                    return
                    
                try:
                    arm = data_manager.add_patient(
                        trial_id=trial_id,
                        patient_id=patient_id,
                        characteristics=characteristics,
                        manual_arm=manual_arm,
                        user=st.session_state.username
                    )
                    
                    st.success(f"Patient {patient_id} added successfully and assigned to arm {arm}")
                    st.session_state.add_patient = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Error adding patient: {str(e)}")
            
            if cancel:
                st.session_state.add_patient = False
                st.rerun()

    def display_minimisation_table(minimiser):
        """Display a table showing the balance of characteristics across arms."""
        st.write("### Minimisation Balance Table")
        
        if minimiser.df_patients.empty:
            st.info("No patients in this trial yet. Tables will appear after adding patients.")
            return
        
        # Get tables for each characteristic
        tables = minimiser.characteristics_by_arm()
        
        if not tables:
            st.warning("No data available to display balance tables.")
            return
        
        # Display each table with an expander
        for var_name, table in tables.items():
            with st.expander(f"#### Balance for: {var_name}", expanded=True):                
                
                # If only 1 arm, or if the table doesn't have enough rows, skip
                if len(minimiser.arms) <= 1 or table.shape[0] <= 2:
                    st.info("Not enough data to calculate extra skew/imbalance.")
                    continue
                
                # We'll add two new items:
                # 1) A "Skew" column that shows (max - min) across that row
                # 2) An "Imbalance" row that shows (max - min) across that column
                
                # Identify which rows/columns are actual arms/categories (skipping 'Total')
                # If your crosstab includes a final row named 'Total' and final column named 'Total',
                # we skip them in the calculations.
                arm_rows = [r for r in table.index if r != 'Total']
                category_cols = [c for c in table.columns if c not in ('Total', 'Skew')]
                
                # 1) Create a blank "Skew" column first so we can fill it
                if 'Skew' not in table.columns:
                    table['Skew'] = ''
                
                # For each arm row, compute the row's skew: (max - min) among its categories
                for arm in arm_rows:
                    # Only consider the real category columns (skip 'Total', skip the new 'Skew' column)
                    row_vals = table.loc[arm, category_cols]
                    if row_vals.empty:
                        table.loc[arm, 'Skew'] = ''
                        continue
                    
                    difference = row_vals.max() - row_vals.min()
                    row_sum = row_vals.sum()
                    pct = round(difference / row_sum * 100) if row_sum > 0 else 0
                    table.loc[arm, 'Skew'] = f"{difference} ({pct}%)"
                
                # Make sure the "Total" row has a blank skew
                if 'Total' in table.index:
                    table.loc['Total', 'Skew'] = ''
                
                # 2) Create an "Imbalance" row for the columns
                # Initialize it with empty strings
                if 'Imbalance' not in table.index:
                    table.loc['Imbalance'] = ''
                
                for col in category_cols:
                    col_vals = table.loc[arm_rows, col]
                    if col_vals.empty:
                        table.loc['Imbalance', col] = ''
                        continue
                    
                    difference = col_vals.max() - col_vals.min()
                    col_sum = col_vals.sum()
                    pct = round(difference / col_sum * 100) if col_sum > 0 else 0
                    table.loc['Imbalance', col] = f"{difference} ({pct}%)"
                
                # Make sure we leave the intersection of 'Imbalance' row + 'Skew' column blank
                table.loc['Imbalance', 'Skew'] = ''
                # Also blank out the 'Total' cell on the 'Imbalance' row if it exists
                if 'Total' in table.columns:
                    table.loc['Imbalance', 'Total'] = ''
                
                # Finally, show the newly enhanced table
                table_for_display = table.astype(str)
                st.dataframe(table_for_display)




    # Main app flow
    def main():
        # Add a title to the sidebar
        st.sidebar.title("Minimisation WebApp")
        
        # Check if we have any users - if not, this is first run
        has_users = auth_manager.has_users()
        
        if not has_users:
            # Show first-run setup screen
            if setup_first_run():
                # If setup successful, rerun to show login screen
                st.rerun()
            return
        
        # Normal flow continues...
        if not st.session_state.authenticated:
            login_form()
            return
        
        # Navigation based on current screen
        if st.session_state.current_trial is None:
            home_screen()
        elif st.session_state.current_trial == "new":
            create_trial_screen()
        else:
            trial_detail_screen(st.session_state.current_trial)

    # Run the app
    main()

except Exception as e:
    st.error(f"Unexpected error: {str(e)}")
    st.code(traceback.format_exc()) 