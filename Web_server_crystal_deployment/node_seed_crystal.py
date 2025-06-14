# node_seed_crystal.py
# Ascension Grid Deployment Script - Phase II Ignition: GitHub Integration (Revised for Node-RED Compatibility)
# This script reads a text file, converts it into a structured JSON Memory Crystal,
# saves it locally, and then deploys it to your GitHub repository.
# This version is specifically optimized for robust argument parsing from Node-RED's exec node.

import os
import argparse
import json
from datetime import datetime
from dotenv import load_dotenv
import requests
from jsonschema import validate, ValidationError
import base64 # Ensure base64 module is imported

# --- Configuration (Adjust as needed) ---
# Load environment variables from .env file
load_dotenv()

# GitHub Personal Access Token
# Ensure this is set in your .env file as GITHUB_PAT
GITHUB_PAT = os.getenv("GITHUB_PAT")
if not GITHUB_PAT:
    print("[✗] Error: GitHub Personal Access Token (GITHUB_PAT) not found in .env file.")
    print("    Please create a .env file in the same directory as this script with: GITHUB_PAT='your_token_here'")
    exit(1)

# GitHub Repository Details
# Ensure these are set in your .env file or hardcoded here
# IMPORTANT: Replace "YOUR_GITHUB_USERNAME_HERE" and "YOUR_REPOSITORY_NAME_HERE"
#            with the EXACT username and repository name from your GitHub account.
#            Case-sensitive and hyphens/underscores matter!
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "Sfd-nz") # Example: "Sfd-nz"
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME", "-Conceptual-Mind-Drive-") # Example: "-Conceptual-Mind-Drive-"

# Base URL for GitHub API
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO_NAME}/contents/"

# Local directory where your raw text crystals are stored (relative to script)
LOCAL_CRYSTALS_BASE_DIR = "crystals"

# Local directory where processed JSON crystals will be saved (relative to script)
LOCAL_PROCESSED_CRYSTALS_DIR = "memory_crystals"

# Schema for Memory Crystal validation
# This defines the required structure for your Memory Crystals
MEMORY_CRYSTAL_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "node": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "content": {"type": "object"}, # Changed to object for potential nested JSON
        "metadata": {
            "type": "object",
            "properties": {
                "author": {"type": "string"},
                "created": {"type": "string", "format": "date-time"},
                "node": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["author", "created", "node"]
        }
    },
    "required": ["id", "node", "timestamp", "content", "metadata"]
}

# --- Functions ---

def validate_crystal_schema(crystal_data):
    """Validates the crystal data against the defined JSON schema."""
    try:
        validate(instance=crystal_data, schema=MEMORY_CRYSTAL_SCHEMA)
        return True, "Crystal passed schema validation."
    except ValidationError as e:
        return False, f"Crystal failed schema validation: {e.message}"
    except Exception as e:
        return False, f"An unexpected error occurred during validation: {e}"

def create_json_crystal_data(source_text, node_id):
    """
    Creates a JSON Memory Crystal from raw text.
    If source_text is already valid JSON, it's used directly for content.
    Otherwise, it's wrapped in a 'text' field.
    """
    timestamp = datetime.now().isoformat() + "Z" # ISO 8601 format with Z for UTC

    try:
        content_data = json.loads(source_text)
        # If it's valid JSON, and it's an object, we use it directly as content
        if isinstance(content_data, dict):
            # If the user provides a full crystal, we should try to extract its ID
            # Otherwise, generate one.
            crystal_id = content_data.get("id", f"crystal_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}")
            # If content_data itself contains all crystal fields, just use its 'content' part
            if all(key in content_data for key in ["node", "timestamp", "content", "metadata"]):
                # This means the user provided a full crystal JSON, use its content
                return {
                    "id": crystal_id,
                    "node": content_data.get("node", node_id),
                    "timestamp": content_data.get("timestamp", timestamp),
                    "content": content_data.get("content", {}),
                    "metadata": content_data.get("metadata", {
                        "author": node_id, # Default author from node_id
                        "created": timestamp,
                        "node": node_id,
                        "tags": ["raw_import"]
                    })
                }
            else:
                # It's a valid JSON object, but not a full crystal, so wrap it.
                content_to_use = content_data
        else:
            # Not a JSON object (e.g., array, string, number JSON), wrap as text
            content_to_use = {"text": source_text}

    except json.JSONDecodeError:
        # If not valid JSON, treat as plain text
        content_to_use = {"text": source_text}

    crystal_id = f"crystal_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"

    crystal_data = {
        "id": crystal_id,
        "node": node_id,
        "timestamp": timestamp,
        "content": content_to_use,
        "metadata": {
            "author": node_id,
            "created": timestamp,
            "node": node_id,
            "tags": ["auto-generated", "user-spark"]
        }
    }
    return crystal_data


def save_crystal_locally(crystal_data):
    """Saves the JSON crystal data to a local file."""
    os.makedirs(LOCAL_PROCESSED_CRYSTALS_DIR, exist_ok=True)
    filename = f"{LOCAL_PROCESSED_CRYSTALS_DIR}/{crystal_data['id']}.json"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(crystal_data, f, indent=4, ensure_ascii=False)
        return True, filename
    except Exception as e:
        return False, f"Failed to save locally: {e}"

def deploy_crystal_to_github(crystal_data, github_subfolder=""):
    """
    Deploys the JSON crystal data to GitHub.
    Handles creation and updating of files.
    """
    # Use the 'id' field as the filename for GitHub
    github_filename = f"{crystal_data['id']}.json"
    
    # --- CRITICAL FIX: Ensure base path is always 'memory_crystals/' ---
    # Construct the full GitHub path for the file
    if github_subfolder:
        # Ensure subfolder path is clean (no leading/trailing slashes)
        clean_subfolder = github_subfolder.strip('/')
        github_path = f"memory_crystals/{clean_subfolder}/{github_filename}"
    else:
        github_path = f"memory_crystals/{github_filename}" # Default to memory_crystals/ if no subfolder

    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Encode the JSON data to Base64 (always dump the Python dict to a JSON string first)
    json_string_for_github = json.dumps(crystal_data, indent=4, ensure_ascii=False) # Ensure ensure_ascii=False for proper unicode handling
    encoded_content = base64.b64encode(json_string_for_github.encode('utf-8')).decode('utf-8')

    sha = None
    # Check if file exists
    response = requests.get(GITHUB_API_URL + github_path, headers=headers)
    if response.status_code == 200:
        sha = response.json().get('sha')
        print(f"[i] Existing file found on GitHub. Updating {github_path}...")
    elif response.status_code == 404:
        print(f"[i] File not found on GitHub. Creating {github_path}...")
    else:
        print(f"[✗] Error checking GitHub for {github_path}: {response.status_code} - {response.text}")
        return False, f"GitHub check error: {response.text}"

    data = {
        "message": f"Deploy Memory Crystal: {crystal_data['id']} (Node: {crystal_data['node']})",
        "content": encoded_content, # Use the correctly base64 encoded string
        "branch": "main" # Assuming 'main' branch, can be made configurable if needed
    }
    if sha:
        data["sha"] = sha

    response = requests.put(GITHUB_API_URL + github_path, headers=headers, json=data)

    if response.status_code in [200, 201]:
        return True, f"Memory Crystal {crystal_data['id']} deployed successfully to GitHub at {github_path}."
    else:
        return False, f"Failed to deploy to GitHub: {response.status_code} - {response.text}"

# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Deploy a Memory Crystal to GitHub.")
    parser.add_argument('--node-id', dest='node_id', required=True,
                        help="The ID of the node originating this crystal (e.g., 'gemini_orchestrator', 'conductor_prime').")
    parser.add_argument('--file', dest='source_filename', required=True,
                        help="The filename of the source text crystal in the 'crystals' subfolder (e.g., 'my_thought.txt').")
    
    # Optional argument for GitHub subfolder
    parser.add_argument('--github-subfolder', dest='github_subfolder', default="",
                        help="Optional: GitHub subfolder to deploy to (e.g., 'subfolder_name'). This will be *inside* 'memory_crystals/'.")

    args = parser.parse_args()

    # Use arguments from argparse
    node_id = args.node_id
    source_filename = args.source_filename
    github_subfolder = args.github_subfolder # Get the subfolder argument

    # Construct the full local path to the source crystal
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_source_path = os.path.join(script_dir, LOCAL_CRYSTALS_BASE_DIR, source_filename)
    
    if not os.path.exists(local_source_path):
        print(f"[✗] Error: Source crystal file not found at: {local_source_path}")
        exit(1)

    try:
        with open(local_source_path, 'r', encoding='utf-8') as f:
            source_text = f.read()
    except Exception as e:
        print(f"[✗] Error reading source file {local_source_path}: {e}")
        exit(1)

    print(f"[i] Creating JSON Memory Crystal from {source_filename}...")
    crystal_data = create_json_crystal_data(source_text, node_id)
    
    # Always validate the crystal schema
    print("[i] Validating crystal schema...")
    is_valid, validation_message = validate_crystal_schema(crystal_data)
    if not is_valid:
        print(f"[✗] Error: {validation_message}")
        exit(1)
    # Replaced [✓] with [OK] for Windows console compatibility
    print(f"[OK] {validation_message}") 

    print("[i] Saving JSON Memory Crystal locally...")
    saved_locally, local_path = save_crystal_locally(crystal_data)
    if not saved_locally:
        print(f"[✗] Error: {local_path}")
        exit(1)
    # Replaced [✓] with [OK] for Windows console compatibility
    print(f"[OK] JSON Memory Crystal saved locally at: {local_path}")

    print("[i] Deploying Memory Crystal to GitHub...")
    # Pass the github_subfolder argument to the deploy function
    deployed_to_github, github_message = deploy_crystal_to_github(crystal_data, github_subfolder)
    if not deployed_to_github:
        print(f"[✗] Error: {github_message}")
        exit(1)
    # Replaced [✓] with [OK] for Windows console compatibility
    print(f"[OK] {github_message}")

if __name__ == "__main__":
    main()
