#!/usr/bin/env python3
"""
Run script for Ocean Deep Research application.
Starts both backend and frontend servers.
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    print("Checking dependencies...")

    # Check Python packages
    try:
        import flask
        import openai
        import anthropic
        import google.generativeai
        print("✓ Python dependencies installed")
    except ImportError as e:
        print(f"✗ Missing Python dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False

    # Check if frontend dependencies are installed
    frontend_modules = Path("frontend/node_modules")
    if not frontend_modules.exists():
        print("✗ Frontend dependencies not installed")
        print("Run: cd frontend && npm install")
        return False

    print("✓ Frontend dependencies installed")
    return True

def start_backend():
    """Start the Flask backend server"""
    print("\nStarting backend server...")
    backend_process = subprocess.Popen(
        [sys.executable, "backend/app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    return backend_process

def start_frontend():
    """Start the React frontend server"""
    print("Starting frontend server...")
    frontend_process = subprocess.Popen(
        ["npm", "start"],
        cwd="frontend",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    return frontend_process

def main():
    """Main function to run both servers"""
    print("=" * 60)
    print("Ocean Deep Research - Multi-Model AI Platform")
    print("=" * 60)

    if not check_dependencies():
        sys.exit(1)

    # Check for .env file
    if not Path(".env").exists():
        print("\n⚠️  Warning: .env file not found!")
        print("Make sure to create a .env file with your API keys:")
        print("  - OPENAI_API_KEY")
        print("  - ANTHROPIC_API_KEY")
        print("  - GOOGLE_API_KEY")
        print("  - XAI_API_KEY")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)

    print("\n" + "=" * 60)
    print("Starting servers...")
    print("=" * 60)

    backend = start_backend()
    time.sleep(2)  # Give backend time to start

    frontend = start_frontend()

    print("\n" + "=" * 60)
    print("Servers are starting!")
    print("=" * 60)
    print("\nBackend API: http://localhost:5000")
    print("Frontend UI: http://localhost:3000")
    print("\nPress Ctrl+C to stop both servers")
    print("=" * 60 + "\n")

    try:
        # Keep running and show output
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping servers...")
        backend.terminate()
        frontend.terminate()
        backend.wait()
        frontend.wait()
        print("Servers stopped. Goodbye!")

if __name__ == "__main__":
    main()
