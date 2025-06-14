#!/usr/bin/env python3
"""
HTTP Server wrapper for node_seed_crystal.py
Run this server, then Node-RED can make HTTP requests instead of using exec node
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import subprocess
import sys
import os
from urllib.parse import parse_qs
import threading # Not strictly necessary for this simple use, but good practice for robustness

class CrystalHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Get content length and read the POST data (JSON from Node-RED)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
                        
            # Parse JSON data from Node-RED
            data = json.loads(post_data.decode('utf-8'))
                        
            # Extract parameters that Node-RED sends
            node_id = data.get('node_id', 'gemini_orchestrator') # Default value if not provided
            file_path = data.get('file', 'node_red_flow_explanation.txt') # Default value if not provided
            validate_flag = data.get('validate', False) # Boolean for validation flag
            
            # Extract the github_subfolder parameter from the incoming data
            github_subfolder = data.get('github_subfolder', '') # Default to empty string if not provided

            # --- NEW LOGIC START: Set node_id to github_subfolder if node_id is default ---
            # If a github_subfolder is provided and the node_id is still the default,
            # set the node_id to match the subfolder name for consistency.
            if github_subfolder and node_id == 'gemini_orchestrator':
                node_id = github_subfolder 
            # --- NEW LOGIC END ---

            # Define paths to the Python executable and your script
            python_executable = "C:\\Python313\\python.exe"
            crystal_script_path = "F:\\1.LLM's\\node_seed_crystal.py"

            # Build command to run your script with arguments
            cmd = [
                python_executable,
                crystal_script_path
            ]
            # Add arguments for node_seed_crystal.py
            if validate_flag: # Add --validate if the flag is true
                cmd.append("--validate") # Although node_seed_crystal.py always validates, this can be passed
            if node_id: # Add --node-id and its value
                cmd.extend(["--node-id", node_id])
            if file_path: # Add --file and its value
                cmd.extend(["--file", file_path])
            
            # Pass the github_subfolder as an argument to node_seed_crystal.py
            if github_subfolder:
                cmd.extend(["--github-subfolder", github_subfolder])
                        
            # Set the working directory to where your scripts and 'crystals' folder are
            script_dir = "F:\\1.LLM's" # Set this to the base directory where node_seed_crystal.py and 'crystals' folder reside

            # Execute the command
            # This is where the actual Python script is run by the server
            result = subprocess.run(
                cmd,
                capture_output=True, # Capture stdout and stderr
                text=True, # Decode output as text
                cwd=script_dir,   # Set working directory for subprocess
                timeout=120   # Increased timeout for potentially long operations, 120 seconds (2 minutes)
            )
                        
            # Prepare response to send back to Node-RED
            response_data = {
                "success": result.returncode == 0, # True if command exited with 0 (success)
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command_executed": " ".join(cmd) # Show the exact command that was run
            }
                        
            # Send HTTP response back to Node-RED
            self.send_response(200) # OK
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*') # Allow CORS for Node-RED
            self.end_headers()
            self.wfile.write(json.dumps(response_data, indent=2).encode()) # Send JSON response
                    
        except Exception as e:
            # Handle any server-side errors
            error_response = {
                "success": False,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "message": "Crystal HTTP Server error occurred during processing."
            }
                        
            self.send_response(500) # Internal Server Error
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(error_response, indent=2).encode())
    
    def do_OPTIONS(self):
        # Handle CORS preflight requests
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default HTTP server logging if too verbose, or customize
        sys.stderr.write(f"[{self.date_time_string()}] {format % args}\n")

def run_server(port=8888):
    server_address = ('localhost', port)
    httpd = HTTPServer(server_address, CrystalHandler)
    print(f"Crystal HTTP Server running on http://localhost:{port}")
    print("Send POST requests to execute the Python script (Ctrl+C to stop)")
        
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown() # Properly shut down the server
    except Exception as e:
        print(f"Server crashed: {e}")

if __name__ == "__main__":
    run_server()