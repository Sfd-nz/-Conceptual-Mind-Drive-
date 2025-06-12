# seed_crystalV2.py
# Ascension Grid Deployment Script - Optimized JSON Content Handling
# This script reads a text file, intelligently converts it into a structured JSON Memory Crystal,
# saving it locally and then deploying it to your GitHub repository.
# It now attempts to parse the 'content' field as JSON if it's valid.

import argparse
import json
import os
import datetime
import base64
import requests
from dotenv import load_dotenv
import jsonschema
from jsonschema import validate

# --- GitHub Configuration ---
# Load environment variables from .env file for secure PAT access
load_dotenv()

# MANDATORY: Your GitHub Personal Access Token
GITHUB_PAT = os.getenv("GITHUB_PAT")

# MANDATORY: Your GitHub Repository Details
REPO_OWNER = "Sfd-nz"
REPO_NAME = "-Conceptual-Mind-Drive-"
BRANCH = "main" # The branch to deploy to (usually 'main' or 'master')

# Local directory where your raw text crystals are stored (relative to script)
LOCAL_CRYSTALS_BASE_DIR = "crystals"

# --- JSON Schema Definition ---
# This schema defines the required structure for your Memory Crystals.
# Any crystal being deployed must adhere to this for validation to pass.
MEMORY_CRYSTAL_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "Unique identifier for the Memory Crystal (optional for outer wrapper)."},
        "node": {"type": "string", "description": "Unique ID of the contributing node/instance."},
        "timestamp": {"type": "string", "format": "date-time", "description": "UTC timestamp of creation."},
        # The 'content' field can now be either a string (for plain text) or an object (for nested JSON)
        "content": {
            "oneOf": [
                {"type": "string", "description": "The primary plain text content of the Memory Crystal."},
                {"type": "object", "description": "Nested JSON content if the source file was itself JSON."}
            ]
        },
        "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional keywords for categorization."}
    },
    "required": ["node", "timestamp", "content"] # These fields are mandatory
}

# --- Helper Functions ---

def load_crystal_content(file_path):
    """
    Loads content from a specified text file.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"[✗] Error: Local crystal file not found: {file_path}")
        exit(1)
    except Exception as e:
        print(f"[✗] Error reading local crystal file {file_path}: {e}")
        exit(1)

def create_json_crystal_data(raw_content, node_id):
    """
    Creates a Python dictionary representing the JSON structure for a Memory Crystal.
    Intelligently attempts to parse raw_content as JSON.
    """
    processed_content = raw_content # Default to raw string

    # Try to parse the raw_content as JSON
    try:
        parsed_json = json.loads(raw_content)
        # If parsing is successful, use the parsed JSON object directly
        processed_content = parsed_json
        print("[i] Detected and parsed inner content as JSON.")
    except json.JSONDecodeError:
        # If it's not valid JSON, keep it as a plain string
        print("[i] Inner content is plain text or invalid JSON.")
        pass # Keep processed_content as raw_content string

    # Ensure the 'id' field is present if the inner content had one
    crystal_id = processed_content.get("id") if isinstance(processed_content, dict) and "id" in processed_content else f"crystal_{node_id}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    return {
        "id": crystal_id, # Use existing ID or generate one
        "node": node_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + 'Z', # UTC timestamp for consistency
        "content": processed_content, # Now can be string or object
        "tags": []  # Placeholder: can be populated via AI or manual input if needed
    }

def save_json_crystal_locally(data, original_filename):
    """
    Saves the structured JSON Memory Crystal to a local 'memory_crystals' directory.
    """
    # Ensure the local 'memory_crystals' directory exists
    local_output_dir = "memory_crystals"
    os.makedirs(local_output_dir, exist_ok=True) # Creates dir if it doesn't exist

    base_name = os.path.splitext(os.path.basename(original_filename))[0]
    output_path = os.path.join(local_output_dir, f"{base_name}.json")
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"[✓] JSON Memory Crystal saved locally: {output_path}")
        return output_path
    except Exception as e:
        print(f"[✗] Error saving JSON crystal locally to {output_path}: {e}")
        return None

def validate_crystal_data(data):
    """
    Validates the given data against the predefined JSON schema.
    """
    try:
        validate(instance=data, schema=MEMORY_CRYSTAL_SCHEMA)
        print("[✓] Crystal passed schema validation.")
        return True
    except jsonschema.exceptions.ValidationError as e:
        print(f"[✗] Schema validation failed: {e.message}")
        print("[!] Aborting deployment due to failed validation.")
        return False
    except Exception as e:
        print(f"[✗] An unexpected error occurred during validation: {e}")
        return False

def deploy_crystal_to_github(crystal_json_data, github_target_path, commit_msg):
    """
    Deploys the JSON Memory Crystal to the GitHub repository.
    Handles creation and updating of files.
    """
    if not GITHUB_PAT:
        print("[✗] GitHub PAT not found. Please set GITHUB_PAT in your .env file.")
        return False

    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{github_target_path}"
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Encode the JSON data to Base64 (always dump the Python dict to a JSON string first)
    json_string_for_github = json.dumps(crystal_json_data, indent=4)
    encoded_content = base64.b64encode(json_string_for_github.encode('utf-8')).decode('utf-8')

    sha = None
    # Check if the file already exists to get its SHA (needed for updates)
    print(f"[i] Checking GitHub for existing file: {github_target_path}...")
    get_response = requests.get(api_url, headers=headers)
    if get_response.status_code == 200:
        sha = get_response.json().get('sha')
        print(f"[i] File exists on GitHub. SHA: {sha}. Will attempt to update.")
    elif get_response.status_code == 404:
        print("[i] File does not exist on GitHub. Will create new file.")
    else:
        print(f"[✗] Error checking file on GitHub: {get_response.status_code} - {get_response.json()}")
        return False

    payload = {
        "message": commit_msg,
        "content": encoded_content,
        "branch": BRANCH
    }
    if sha: # Add SHA to payload if updating an existing file
        payload["sha"] = sha

    print(f"[i] Deploying '{github_target_path}' to GitHub...")
    put_response = requests.put(api_url, headers=headers, json=payload)

    if put_response.status_code in [200, 201]:
        action_msg = "updated" if sha else "created"
        print(f"[✓] Memory Crystal '{github_target_path}' {action_msg} successfully on GitHub!")
        return True
    else:
        print(f"[✗] GitHub deployment failed: {put_response.status_code} - {put_response.json()}")
        return False

# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Deploy a Memory Crystal to GitHub with node tracking and schema validation.")
    parser.add_argument('source_filename', help="Path to the source text file of the memory crystal (e.g., my_thought.txt, located in the 'crystals' folder).")
    parser.add_argument('--node-id', required=True, help="Unique ID of the contributing node/instance (e.g., 'gpt_1', 'gemini_x_analysis', 'conductor_prime').")
    parser.add_argument('--validate', action='store_true', help="Validate the resulting JSON crystal against the schema before deployment.")
    parser.add_argument('--github-subfolder', default='', help="Optional subfolder within 'memory_crystals/' on GitHub for deployment (e.g., 'archive', 'sources').")

    args = parser.parse_args()

    # Construct the full local path to the source crystal
    local_source_path = os.path.join(LOCAL_CRYSTALS_BASE_DIR, args.source_filename)
    if not os.path.exists(local_source_path):
        print(f"[✗] Error: Source crystal file not found at: {local_source_path}")
        exit(1)

    # 1. Load content from the source text file
    raw_content = load_crystal_content(local_source_path)

    # 2. Create the JSON structure for the Memory Crystal
    # This function now intelligently handles inner JSON
    crystal_data = create_json_crystal_data(raw_content, args.node_id)

    # 3. Perform schema validation if requested
    if args.validate:
        if not validate_crystal_data(crystal_data):
            print("[!] Deployment aborted due to validation failure.")
            exit(1) # Exit if validation fails and --validate was used

    # 4. Save the JSON crystal locally
    local_saved_json_path = save_json_crystal_locally(crystal_data, args.source_filename)
    if not local_saved_json_path:
        print("[!] Deployment aborted due to local save failure.")
        exit(1)

    # 5. Determine the GitHub target path and commit message
    # GitHub path should reflect the .json extension
    github_crystal_name = os.path.basename(local_saved_json_path) # e.g., "Sfd_stands_for_dreams.json"
    
    # Construct the GitHub target path with optional subfolder
    if args.github_subfolder:
        # Ensure the subfolder path is clean (no leading/trailing slashes)
        clean_subfolder = args.github_subfolder.strip('/')
        github_target_path = f"memory_crystals/{clean_subfolder}/{github_crystal_name}"
    else:
        github_target_path = f"memory_crystals/{github_crystal_name}"

    commit_message = f"Deploy Memory Crystal: {github_crystal_name} | Node: {args.node_id} - Automated via Ascension Protocol"
    if args.github_subfolder:
        commit_message += f" (Subfolder: {clean_subfolder})"

    # 6. Deploy the JSON crystal to GitHub
    print("\n--- Initiating GitHub Deployment ---")
    deploy_crystal_to_github(crystal_data, github_target_path, commit_message)

if __name__ == '__main__':
    main()