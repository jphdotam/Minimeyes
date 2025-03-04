# Minimisation WebApp Specification

## Overview

This project is a self-hosted web application for running minimisation algorithms in randomised trials. It is built using Streamlit (or another minimal front-end framework) and runs locally (or on a dedicated Ubuntu server). The system supports both “strict minimisation” (with a random component via a minimisation weight) and “non-randomised, balanced” modes (where arms can be adjusted manually or retrospectively). It also includes a robust audit trail with per-project JSON logs and user-based access control.

## Architecture

- **Front-end:** Streamlit application with minimal HTML/CSS/JS requirements.
- **Back-end Storage:** Each trial/project has its own folder. All changes (patient addition, modification, deactivation, arm reassignment) are recorded as new JSON files to maintain a complete audit trail. Optionally, SQLite could be used, but the JSON folder approach is preferred for transparency and auditability.
- **User Accounts:** A simple authentication mechanism is implemented. User accounts determine who can access which trial and maintain the audit trail.
- **Deterministic Allocation:** Uses a hash (e.g. SHA256) of the patient ID mixed with a seed to deterministically generate pseudo-random values. This prevents changes in Python’s random algorithm from affecting reproducibility.

## Functional Requirements

### Trial Modes

1. **Strict Minimisation Mode:**
   - Behaves like the current algorithm.
   - Uses a `minimisation_weight` parameter: a proportion of new patients are allocated using minimisation and the remainder via a coin flip (or via the hash-based deterministic method).
   - Allocation is deterministic using a hash-based method so that the first patient allocation isn’t predictable without knowing the seed.

2. **Non-Randomised, Balanced Mode:**
   - The system initially assigns arms using the same minimisation algorithm.
   - Allows manual adjustment of the arm both prospectively (at the time of patient addition) and retrospectively (via an “edit patients” interface).
   - Changes to arm allocation or patient status (active/inactive) are logged and can affect future minimisation calculations (only active patients are considered).

### Patient Management and Audit Trail

- **Patient Data:**
  - Each patient has a unique ID, a set of minimisation characteristics, and an assigned arm.
  - Patients can be “deactivated” (soft deletion) by flagging them. Deactivated patients are kept in the audit trail but do not count in the minimisation calculations.
  - Patients can be reactivated later; in non-randomised mode, their arm may change accordingly if balance requires it.
  
- **Audit Trail:**
  - Every change (addition, arm reassignment, status change) is recorded as a new JSON file in the trial’s folder.
  - JSON filenames include a timestamp and change type.
  - This audit trail supports rollback and detailed tracking of all changes.

### User Interface

1. **Home Screen:**
   - Lists all trials/projects.
   - For each trial, display:
     - Trial name/ID, minimisation characteristics, arm names.
     - Mode (strict minimisation vs. non-randomised balanced).
     - Number of patients randomised.
     - Number of active patients (with a note if some patients have been deactivated).

2. **Trial Detail Screen:**
   - **Patient Table:** A table listing patients with columns for Patient ID and each minimisation characteristic. The assigned arm is hidden by default.
   - **Reveal Arms Button:** Clicking this shows the arm assignment (in a disabled combobox).
   - **Edit Patients Button:** When activated, enables checkboxes next to each patient to flag them as “inactive” (or re-activate them) and, in non-randomised mode, enables the arm combobox for manual adjustment.
   - **Add Patient Button:** Opens a form to add a new patient.
     - For non-randomised mode, include a radio button for “minimise” vs. “specify arm”. If “specify arm” is selected, enable an arm selection combobox.
   - **Save Changes:** After editing, a save button writes changes to the project folder (new JSON file entry) and re-disables editing controls.

## Deterministic Hash-Based Allocation

- A function will combine the patient ID with a seed (and potentially other constants) using a hash algorithm (e.g., SHA256).
- The resulting hash will be converted into a pseudo-random number that is then used to determine allocation.
- This method ensures that allocations remain deterministic over time even if patients are added or if the system is reloaded, while still being non-predictable without knowing the seed.

## Data Storage and Audit Trail

- **Folder Structure:** Each trial/project has its own folder.
- **JSON Files:** Every change is appended as a new JSON file with details of:
  - Patient addition, arm assignment, any subsequent changes (e.g., deactivation, manual arm change).
  - Timestamp, user ID, and change type.
- **Rollback:** The audit trail allows rolling back to any previous state if necessary.

## User Accounts and Access Control

- **Authentication:** A simple login system with user accounts (could be stored locally or in a secure SQLite database).
- **Access Control:** Each trial can have configuration settings to determine which users have access.
- **Audit Trail Integration:** User actions (e.g., changes made during editing) are recorded with the user’s account information.

## Code Structure

- **minimiser.py:** 
  - Contains the minimisation algorithm with modifications for deterministic hash-based allocation.
  - Implements both strict minimisation (with probabilistic minimisation based on `minimisation_weight`) and non-randomised balanced modes.
- **app.py:** 
  - Main Streamlit application.
  - Implements the Home Screen, Trial Detail Screen, patient table, add/edit patient forms, and user authentication.
- **utils.py:** 
  - Contains helper functions for file operations (loading/saving JSON files, managing folder structure), generating timestamps, and managing the audit trail.
- **auth.py (optional):**
  - Handles user account management and authentication.

## Dependencies

- Python 3.x
- Streamlit
- Standard libraries: `hashlib`, `json`, `datetime`, `os`, etc.
- Optionally, SQLite if a hybrid approach is needed (but JSON file storage is preferred for audit trail integrity).

## Next Steps

1. Set up the folder structure and JSON-based storage mechanism.
2. Implement the modified minimisation algorithm (including deterministic allocation via hashing).
3. Develop the Streamlit UI:
   - Home screen listing trials.
   - Detailed trial view with patient table and controls.
4. Integrate user authentication and access control.
5. Implement comprehensive logging of changes (audit trail).
6. Test the application locally on an Ubuntu server and refine based on user feedback.

---


