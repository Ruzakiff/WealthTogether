#!/usr/bin/env python3
import requests
import json
from typing import Dict, Any, Optional
import os
import sys

BASE_URL = "http://localhost:8000/api/v1"

# Store created entities for reference in subsequent requests
STORED_IDS = {
    "users": {},
    "couples": {},
    "accounts": {},
    "goals": {},
    "ledger_events": {}
}

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title: str):
    clear_screen()
    print("=" * 50)
    print(f" {title} ".center(50, "="))
    print("=" * 50)
    print()

def get_input(prompt: str, default: str = None) -> str:
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        if not result:
            return default
        return result
    return input(f"{prompt}: ").strip()

def make_request(method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{BASE_URL}{endpoint}"
    
    print(f"\nMaking {method} request to {url}")
    if data:
        print(f"Request data: {json.dumps(data, indent=2)}")
    if params:
        print(f"Query params: {params}")
    
    try:
        if method.lower() == "get":
            response = requests.get(url, params=params)
        elif method.lower() == "post":
            response = requests.post(url, json=data)
        elif method.lower() == "put":
            response = requests.put(url, json=data)
        elif method.lower() == "delete":
            response = requests.delete(url)
        else:
            print(f"Unknown method: {method}")
            return {}
        
        if response.status_code >= 400:
            print(f"Error {response.status_code}: {response.text}")
            return {}
        
        if response.text:
            result = response.json()
            print(f"\nResponse ({response.status_code}):")
            print(json.dumps(result, indent=2))
            return result
        return {}
    
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return {}
    except json.JSONDecodeError:
        print(f"Invalid JSON response: {response.text}")
        return {}

# User operations
def create_user():
    print_header("Create User")
    
    email = get_input("Email")
    display_name = get_input("Display Name")
    
    data = {
        "email": email,
        "display_name": display_name
    }
    
    result = make_request("post", "/users", data)
    if result and "id" in result:
        STORED_IDS["users"][result["display_name"]] = result["id"]
        print(f"\nStored user ID for {result['display_name']}: {result['id']}")
    
    input("\nPress Enter to continue...")

def list_users():
    print_header("List Stored Users")
    
    if not STORED_IDS["users"]:
        print("No users have been created yet.")
    else:
        print("Available users:")
        for name, id in STORED_IDS["users"].items():
            print(f"  - {name}: {id}")
    
    input("\nPress Enter to continue...")

# Couple operations
def create_couple():
    print_header("Create Couple")
    
    if len(STORED_IDS["users"]) < 2:
        print("You need at least two users to create a couple. Please create more users.")
        input("\nPress Enter to continue...")
        return
    
    print("Available users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    partner1_name = get_input("Select first partner (name)")
    partner2_name = get_input("Select second partner (name)")
    
    if partner1_name not in STORED_IDS["users"] or partner2_name not in STORED_IDS["users"]:
        print("One or both user names not found in stored users.")
        input("\nPress Enter to continue...")
        return
    
    data = {
        "partner_1_id": STORED_IDS["users"][partner1_name],
        "partner_2_id": STORED_IDS["users"][partner2_name]
    }
    
    result = make_request("post", "/couples", data)
    if result and "id" in result:
        couple_name = f"{partner1_name} & {partner2_name}"
        STORED_IDS["couples"][couple_name] = result["id"]
        print(f"\nStored couple ID for {couple_name}: {result['id']}")
    
    input("\nPress Enter to continue...")

def list_couples():
    print_header("List Stored Couples")
    
    if not STORED_IDS["couples"]:
        print("No couples have been created yet.")
    else:
        print("Available couples:")
        for name, id in STORED_IDS["couples"].items():
            print(f"  - {name}: {id}")
    
    input("\nPress Enter to continue...")

# Account operations
def create_account():
    print_header("Create Bank Account")
    
    if not STORED_IDS["users"]:
        print("You need to create a user first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select user (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found in stored users.")
        input("\nPress Enter to continue...")
        return
    
    name = get_input("Account Name")
    balance = get_input("Balance", "1000")
    is_manual = get_input("Is Manual (true/false)", "true").lower() == "true"
    institution = get_input("Institution Name (optional)")
    
    data = {
        "user_id": STORED_IDS["users"][user_name],
        "name": name,
        "balance": float(balance),
        "is_manual": is_manual
    }
    
    if institution:
        data["institution_name"] = institution
    
    result = make_request("post", "/accounts", data)
    if result and "id" in result:
        account_name = f"{user_name}'s {name}"
        STORED_IDS["accounts"][account_name] = result["id"]
        print(f"\nStored account ID for {account_name}: {result['id']}")
    
    input("\nPress Enter to continue...")

def list_accounts():
    print_header("List Accounts")
    
    if not STORED_IDS["users"] and not STORED_IDS["couples"]:
        print("You need to create a user or couple first.")
        input("\nPress Enter to continue...")
        return
    
    filter_type = get_input("Filter by user or couple? (user/couple)")
    
    if filter_type.lower() == "user":
        if not STORED_IDS["users"]:
            print("No users have been created yet.")
            input("\nPress Enter to continue...")
            return
        
        print("Available users:")
        for name, id in STORED_IDS["users"].items():
            print(f"  - {name}: {id}")
        
        user_name = get_input("Select user (name)")
        
        if user_name not in STORED_IDS["users"]:
            print("User name not found in stored users.")
            input("\nPress Enter to continue...")
            return
        
        params = {"user_id": STORED_IDS["users"][user_name]}
        make_request("get", "/accounts", params=params)
    
    elif filter_type.lower() == "couple":
        if not STORED_IDS["couples"]:
            print("No couples have been created yet.")
            input("\nPress Enter to continue...")
            return
        
        print("Available couples:")
        for name, id in STORED_IDS["couples"].items():
            print(f"  - {name}: {id}")
        
        couple_name = get_input("Select couple (name)")
        
        if couple_name not in STORED_IDS["couples"]:
            print("Couple name not found in stored couples.")
            input("\nPress Enter to continue...")
            return
        
        params = {"couple_id": STORED_IDS["couples"][couple_name]}
        make_request("get", "/accounts", params=params)
    
    input("\nPress Enter to continue...")

# Goal operations
def create_goal():
    print_header("Create Financial Goal")
    
    if not STORED_IDS["couples"]:
        print("You need to create a couple first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available couples:")
    for name, id in STORED_IDS["couples"].items():
        print(f"  - {name}: {id}")
    
    couple_name = get_input("Select couple (name)")
    
    if couple_name not in STORED_IDS["couples"]:
        print("Couple name not found in stored couples.")
        input("\nPress Enter to continue...")
        return
    
    name = get_input("Goal Name")
    target = get_input("Target Amount", "10000")
    goal_type = get_input("Goal Type (emergency, vacation, house, education, other)", "emergency")
    priority = get_input("Priority (1-5, 1 is highest)", "1")
    
    data = {
        "couple_id": STORED_IDS["couples"][couple_name],
        "name": name,
        "target_amount": float(target),
        "type": goal_type,
        "priority": int(priority)
    }
    
    result = make_request("post", "/goals", data)
    if result and "id" in result:
        goal_name = f"{couple_name}'s {name}"
        STORED_IDS["goals"][goal_name] = result["id"]
        print(f"\nStored goal ID for {goal_name}: {result['id']}")
    
    input("\nPress Enter to continue...")

def list_goals():
    print_header("List Goals")
    
    if not STORED_IDS["couples"]:
        print("You need to create a couple first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available couples:")
    for name, id in STORED_IDS["couples"].items():
        print(f"  - {name}: {id}")
    
    couple_name = get_input("Select couple (name)")
    
    if couple_name not in STORED_IDS["couples"]:
        print("Couple name not found in stored couples.")
        input("\nPress Enter to continue...")
        return
    
    params = {"couple_id": STORED_IDS["couples"][couple_name]}
    make_request("get", "/goals", params=params)
    
    input("\nPress Enter to continue...")

def allocate_to_goal():
    print_header("Allocate to Goal")
    
    if not STORED_IDS["goals"] or not STORED_IDS["accounts"]:
        print("You need to create goals and accounts first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available goals:")
    for name, id in STORED_IDS["goals"].items():
        print(f"  - {name}: {id}")
    
    goal_name = get_input("Select goal (name)")
    
    if goal_name not in STORED_IDS["goals"]:
        print("Goal name not found.")
        input("\nPress Enter to continue...")
        return
    
    print("\nAvailable accounts:")
    for name, id in STORED_IDS["accounts"].items():
        print(f"  - {name}: {id}")
    
    account_name = get_input("Select account (name)")
    
    if account_name not in STORED_IDS["accounts"]:
        print("Account name not found.")
        input("\nPress Enter to continue...")
        return
    
    # Get user ID for this allocation
    user_name = account_name.split("'s")[0]
    if user_name not in STORED_IDS["users"]:
        print(f"Could not determine user for account {account_name}")
        input("\nPress Enter to continue...")
        return
    
    amount = get_input("Amount to allocate", "500")
    
    data = {
        "goal_id": STORED_IDS["goals"][goal_name],
        "account_id": STORED_IDS["accounts"][account_name],
        "amount": float(amount)
    }
    
    user_id = STORED_IDS["users"][user_name]
    make_request("post", f"/goals/allocate?user_id={user_id}", data)
    
    input("\nPress Enter to continue...")

# Ledger operations
def create_ledger_event():
    print_header("Create Ledger Event")
    
    if not STORED_IDS["users"]:
        print("You need to create a user first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select user (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found.")
        input("\nPress Enter to continue...")
        return
    
    event_type = get_input("Event Type (allocation, deposit, withdrawal, transfer)", "allocation")
    amount = get_input("Amount", "100")
    
    data = {
        "event_type": event_type,
        "amount": float(amount),
        "user_id": STORED_IDS["users"][user_name]
    }
    
    # Optional source account
    if STORED_IDS["accounts"]:
        include_source = get_input("Include source account? (y/n)", "y").lower() == "y"
        if include_source:
            print("\nAvailable accounts:")
            for name, id in STORED_IDS["accounts"].items():
                print(f"  - {name}: {id}")
            
            account_name = get_input("Select source account (name)")
            if account_name in STORED_IDS["accounts"]:
                data["source_account_id"] = STORED_IDS["accounts"][account_name]
    
    # Optional destination goal
    if STORED_IDS["goals"]:
        include_goal = get_input("Include destination goal? (y/n)", "y").lower() == "y"
        if include_goal:
            print("\nAvailable goals:")
            for name, id in STORED_IDS["goals"].items():
                print(f"  - {name}: {id}")
            
            goal_name = get_input("Select destination goal (name)")
            if goal_name in STORED_IDS["goals"]:
                data["dest_goal_id"] = STORED_IDS["goals"][goal_name]
    
    # Optional metadata
    include_metadata = get_input("Include metadata? (y/n)", "n").lower() == "y"
    if include_metadata:
        note = get_input("Note")
        data["event_metadata"] = {"note": note}
    
    result = make_request("post", "/ledger", data)
    if result and "id" in result:
        event_name = f"{user_name}'s {event_type} of {amount}"
        STORED_IDS["ledger_events"][event_name] = result["id"]
        print(f"\nStored ledger event ID for {event_name}: {result['id']}")
    
    input("\nPress Enter to continue...")

def list_ledger_events():
    print_header("List Ledger Events")
    
    filter_type = get_input("Filter by (user/couple/account/goal)")
    
    if filter_type.lower() == "user":
        if not STORED_IDS["users"]:
            print("No users created yet.")
            input("\nPress Enter to continue...")
            return
        
        print("Available users:")
        for name, id in STORED_IDS["users"].items():
            print(f"  - {name}: {id}")
        
        user_name = get_input("Select user (name)")
        if user_name in STORED_IDS["users"]:
            params = {"user_id": STORED_IDS["users"][user_name]}
            make_request("get", "/ledger", params=params)
    
    elif filter_type.lower() == "couple":
        if not STORED_IDS["couples"]:
            print("No couples created yet.")
            input("\nPress Enter to continue...")
            return
        
        print("Available couples:")
        for name, id in STORED_IDS["couples"].items():
            print(f"  - {name}: {id}")
        
        couple_name = get_input("Select couple (name)")
        if couple_name in STORED_IDS["couples"]:
            params = {"couple_id": STORED_IDS["couples"][couple_name]}
            make_request("get", "/ledger", params=params)
    
    elif filter_type.lower() == "account":
        if not STORED_IDS["accounts"]:
            print("No accounts created yet.")
            input("\nPress Enter to continue...")
            return
        
        print("Available accounts:")
        for name, id in STORED_IDS["accounts"].items():
            print(f"  - {name}: {id}")
        
        account_name = get_input("Select account (name)")
        if account_name in STORED_IDS["accounts"]:
            params = {"account_id": STORED_IDS["accounts"][account_name]}
            make_request("get", "/ledger", params=params)
    
    elif filter_type.lower() == "goal":
        if not STORED_IDS["goals"]:
            print("No goals created yet.")
            input("\nPress Enter to continue...")
            return
        
        print("Available goals:")
        for name, id in STORED_IDS["goals"].items():
            print(f"  - {name}: {id}")
        
        goal_name = get_input("Select goal (name)")
        if goal_name in STORED_IDS["goals"]:
            params = {"goal_id": STORED_IDS["goals"][goal_name]}
            make_request("get", "/ledger", params=params)
    
    input("\nPress Enter to continue...")

def main_menu():
    while True:
        print_header("CFO Command Center Test Client")
        
        print("1. Users")
        print("2. Couples")
        print("3. Bank Accounts")
        print("4. Financial Goals")
        print("5. Ledger Events")
        print("0. Exit")
        
        choice = get_input("\nEnter your choice")
        
        if choice == "0":
            print("\nExiting...")
            sys.exit(0)
        
        elif choice == "1":
            while True:
                print_header("User Operations")
                print("1. Create User")
                print("2. List Stored Users")
                print("0. Back to Main Menu")
                
                user_choice = get_input("\nEnter your choice")
                
                if user_choice == "0":
                    break
                elif user_choice == "1":
                    create_user()
                elif user_choice == "2":
                    list_users()
        
        elif choice == "2":
            while True:
                print_header("Couple Operations")
                print("1. Create Couple")
                print("2. List Stored Couples")
                print("0. Back to Main Menu")
                
                couple_choice = get_input("\nEnter your choice")
                
                if couple_choice == "0":
                    break
                elif couple_choice == "1":
                    create_couple()
                elif couple_choice == "2":
                    list_couples()
        
        elif choice == "3":
            while True:
                print_header("Bank Account Operations")
                print("1. Create Account")
                print("2. List Accounts")
                print("0. Back to Main Menu")
                
                account_choice = get_input("\nEnter your choice")
                
                if account_choice == "0":
                    break
                elif account_choice == "1":
                    create_account()
                elif account_choice == "2":
                    list_accounts()
        
        elif choice == "4":
            while True:
                print_header("Financial Goal Operations")
                print("1. Create Goal")
                print("2. List Goals")
                print("3. Allocate to Goal")
                print("0. Back to Main Menu")
                
                goal_choice = get_input("\nEnter your choice")
                
                if goal_choice == "0":
                    break
                elif goal_choice == "1":
                    create_goal()
                elif goal_choice == "2":
                    list_goals()
                elif goal_choice == "3":
                    allocate_to_goal()
        
        elif choice == "5":
            while True:
                print_header("Ledger Operations")
                print("1. Create Ledger Event")
                print("2. List Ledger Events")
                print("0. Back to Main Menu")
                
                ledger_choice = get_input("\nEnter your choice")
                
                if ledger_choice == "0":
                    break
                elif ledger_choice == "1":
                    create_ledger_event()
                elif ledger_choice == "2":
                    list_ledger_events()

if __name__ == "__main__":
    try:
        # Check if server is running
        requests.get(f"{BASE_URL}/users")
        main_menu()
    except requests.ConnectionError:
        print(f"Error: Cannot connect to the API at {BASE_URL}")
        print("Make sure your FastAPI server is running.")
        sys.exit(1)