#!/usr/bin/env python3
import os
import sys
import subprocess
import glob

def run_tests():
    """
    Finds and runs all pytest test files in the tests directory and its subdirectories
    """
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Add project root to Python path
    project_root = os.path.abspath(os.path.join(current_dir, ".."))
    
    # Path to the tests directory
    tests_dir = os.path.join(current_dir, "backend", "tests")
    
    if not os.path.isdir(tests_dir):
        print(f"Error: Tests directory not found at {tests_dir}")
        return 1
    
    # Find all test_*.py files in tests directory and all subdirectories
    test_files = glob.glob(os.path.join(tests_dir, "**", "test_*.py"), recursive=True)
    
    if not test_files:
        print("No test files found in the tests directory or its subdirectories")
        return 0
    
    print(f"Found {len(test_files)} test files")
    
    # Set up environment with the project root in PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")
    
    # Run pytest on the tests directory with verbose output
    print(f"\n{'='*50}")
    print(f"Running pytest on {tests_dir} (including subdirectories)...")
    print(f"{'='*50}")
    
    # Run pytest with -v for verbose output and -s to show print statements
    # Using --collect-in-virtualenv to ensure tests in subdirectories are collected
    cmd = [sys.executable, "-m", "pytest", tests_dir, "-v", "-s", "--collect-in-virtualenv"]
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_tests())