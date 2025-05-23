#!/usr/bin/env python3
import requests
import json
from typing import Dict, Any, Optional
import os
import sys
from datetime import date

BASE_URL = "http://localhost:8000/api/v1"

# Store created entities for reference in subsequent requests
STORED_IDS = {
    "users": {},
    "couples": {},
    "accounts": {},
    "goals": {},
    "ledger_events": {},
    "categories": {},
    "transactions": {},
    "budgets": {}
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

def make_request(method, endpoint, data=None, params=None):
    """Helper function to make requests to the API"""
    url = f"{BASE_URL}{endpoint}"
    
    # Debug output
    print(f"\nMaking {method.upper()} request to {url}")
    if data:
        print(f"Request data: {json.dumps(data, indent=2)}")
    if params:
        print(f"Query params: {params}")
    
    try:
        if method.lower() == 'get':
            response = requests.get(url, params=params)
        elif method.lower() == 'post':
            response = requests.post(url, json=data, params=params)
        elif method.lower() == 'put':
            response = requests.put(url, json=data, params=params)
        elif method.lower() == 'delete':
            response = requests.delete(url, params=params)
        else:
            print(f"Unsupported method: {method}")
            return None
        
        # Check for successful response
        if response.status_code >= 200 and response.status_code < 300:
            if response.text:
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2)}")
                return result
            return {}
        else:
            print(f"Error {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
        return None
    except json.JSONDecodeError:
        print(f"Warning: Response was not valid JSON: {response.text}")
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
    
    # Get user (for created_by field)
    if not STORED_IDS["users"]:
        print("You need to create a user first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available couples:")
    for name, id in STORED_IDS["couples"].items():
        print(f"  - {name}: {id}")
    
    couple_name = get_input("Select couple (name)")
    
    if couple_name not in STORED_IDS["couples"]:
        print("Couple name not found.")
        input("\nPress Enter to continue...")
        return
    
    # Select user for the created_by field
    print("\nAvailable users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select user creating the goal (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found.")
        input("\nPress Enter to continue...")
        return
    
    name = get_input("Goal Name")
    
    try:
        target_amount = float(get_input("Target Amount"))
        if target_amount <= 0:
            print("Target amount must be positive.")
            input("\nPress Enter to continue...")
            return
    except ValueError:
        print("Invalid amount.")
        input("\nPress Enter to continue...")
        return
    
    print("\nAvailable goal types:")
    print("  - generic")
    print("  - emergency")
    print("  - retirement")
    print("  - vacation")
    print("  - education")
    print("  - home")
    print("  - car")
    print("  - debt")
    print("  - other")
    
    goal_type = get_input("Goal Type", "generic")
    priority = int(get_input("Priority (1-5, 1 is highest)", "3"))
    deadline_str = get_input("Deadline (YYYY-MM-DD, optional)")
    
    deadline = None
    if deadline_str:
        try:
            year, month, day = map(int, deadline_str.split('-'))
            deadline = date(year, month, day).isoformat()
        except (ValueError, TypeError):
            print("Invalid date format. Using no deadline.")
    
    notes = get_input("Notes (optional)")
    
    data = {
        "couple_id": STORED_IDS["couples"][couple_name],
        "name": name,
        "target_amount": target_amount,
        "type": goal_type,
        "priority": priority,
        "created_by": STORED_IDS["users"][user_name]  # Add the created_by field
    }
    
    if deadline:
        data["deadline"] = deadline
    
    if notes:
        data["notes"] = notes
    
    result = make_request("post", "/goals", data)
    if result and "id" in result:
        STORED_IDS["goals"][result["name"]] = result["id"]
        print(f"\nStored goal ID for {result['name']}: {result['id']}")
    
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
    
    if not STORED_IDS["goals"]:
        print("You need to create a goal first.")
        input("\nPress Enter to continue...")
        return
    
    if not STORED_IDS["accounts"]:
        print("You need to create a bank account first.")
        input("\nPress Enter to continue...")
        return
    
    # First, select a user who is performing the allocation
    if not STORED_IDS["users"]:
        print("You need to create a user first.")
        input("\nPress Enter to continue...")
        return
    
    print("Select the user who is performing the allocation:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select user (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found.")
        input("\nPress Enter to continue...")
        return
    
    user_id = STORED_IDS["users"][user_name]
    
    # Then, select the goal
    print("\nAvailable goals:")
    for name, id in STORED_IDS["goals"].items():
        print(f"  - {name}: {id}")
    
    goal_name = get_input("Select goal (name)")
    
    if goal_name not in STORED_IDS["goals"]:
        print("Goal name not found.")
        input("\nPress Enter to continue...")
        return
    
    # Show accounts
    print("\nAvailable accounts:")
    for name, id in STORED_IDS["accounts"].items():
        print(f"  - {name}: {id}")
    
    account_name = get_input("Select account (name)")
    
    if account_name not in STORED_IDS["accounts"]:
        print("Account name not found.")
        input("\nPress Enter to continue...")
        return
    
    amount = get_input("Amount to allocate", "100.00")
    try:
        amount = float(amount)
    except ValueError:
        print("Invalid amount. Please enter a number.")
        input("\nPress Enter to continue...")
        return
    
    # We'll try two approaches:
    
    # 1. First, try with query parameter
    data = {
        "goal_id": STORED_IDS["goals"][goal_name],
        "account_id": STORED_IDS["accounts"][account_name],
        "amount": amount
    }
    
    params = {"user_id": user_id}
    
    result = make_request("post", "/goals/allocate", data, params)
    
    # 2. If the first approach fails, try with the user_id in the body
    if not result:
        print("\nRetrying with user_id in request body...")
        data["user_id"] = user_id
        result = make_request("post", "/goals/allocate", data)
    
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

# Transaction operations
def create_transaction():
    print_header("Create Transaction")
    
    if not STORED_IDS["accounts"]:
        print("You need to create an account first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available accounts:")
    for name, id in STORED_IDS["accounts"].items():
        print(f"  - {name}: {id}")
    
    account_name = get_input("Select account (name)")
    
    if account_name not in STORED_IDS["accounts"]:
        print("Account name not found.")
        input("\nPress Enter to continue...")
        return
    
    amount = get_input("Amount", "50.00")
    description = get_input("Description", "Test Transaction")
    merchant = get_input("Merchant Name (optional)")
    transaction_date = get_input("Date (YYYY-MM-DD)", date.today().isoformat())
    is_pending = get_input("Is Pending (true/false)", "false").lower() == "true"
    
    data = {
        "account_id": STORED_IDS["accounts"][account_name],
        "amount": float(amount),
        "description": description,
        "date": transaction_date,
        "is_pending": is_pending
    }
    
    if merchant:
        data["merchant_name"] = merchant
    
    # Optional category if we have categories
    if STORED_IDS["categories"]:
        include_category = get_input("Include category? (y/n)", "n").lower() == "y"
        if include_category:
            print("\nAvailable categories:")
            for name, id in STORED_IDS["categories"].items():
                print(f"  - {name}: {id}")
            
            category_name = get_input("Select category (name)")
            if category_name in STORED_IDS["categories"]:
                data["category_id"] = STORED_IDS["categories"][category_name]
    
    result = make_request("post", "/transactions", data)
    if result and "id" in result:
        trans_name = f"{account_name} - {description} (${amount})"
        STORED_IDS["transactions"][trans_name] = result["id"]
        print(f"\nStored transaction ID for {trans_name}: {result['id']}")
    
    input("\nPress Enter to continue...")

def list_transactions():
    print_header("List Transactions")
    
    filter_type = get_input("Filter by account or user? (account/user)", "account")
    
    if filter_type.lower() == "account":
        if not STORED_IDS["accounts"]:
            print("You need to create an account first.")
            input("\nPress Enter to continue...")
            return
        
        print("Available accounts:")
        for name, id in STORED_IDS["accounts"].items():
            print(f"  - {name}: {id}")
        
        account_name = get_input("Select account (name)")
        
        if account_name not in STORED_IDS["accounts"]:
            print("Account name not found.")
            input("\nPress Enter to continue...")
            return
        
        params = {"account_id": STORED_IDS["accounts"][account_name]}
    
    else:  # user
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
        
        params = {"user_id": STORED_IDS["users"][user_name]}
    
    # Optional date filtering
    add_dates = get_input("Add date filtering? (y/n)", "n").lower() == "y"
    if add_dates:
        start_date = get_input("Start date (YYYY-MM-DD)", (date.today().replace(day=1)).isoformat())
        end_date = get_input("End date (YYYY-MM-DD)", date.today().isoformat())
        params["start_date"] = start_date
        params["end_date"] = end_date
    
    # Optional category filtering
    if STORED_IDS["categories"] and filter_type.lower() == "user":
        add_category = get_input("Filter by category? (y/n)", "n").lower() == "y"
        if add_category:
            print("\nAvailable categories:")
            for name, id in STORED_IDS["categories"].items():
                print(f"  - {name}: {id}")
            
            category_name = get_input("Select category (name)")
            if category_name in STORED_IDS["categories"]:
                params["category_id"] = STORED_IDS["categories"][category_name]
    
    make_request("get", "/transactions", params=params)
    input("\nPress Enter to continue...")

def categorize_transaction():
    print_header("Categorize Transaction")
    
    if not STORED_IDS["transactions"]:
        print("You need to create a transaction first.")
        input("\nPress Enter to continue...")
        return
    
    if not STORED_IDS["categories"]:
        print("You need to create categories first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available transactions:")
    for name, id in STORED_IDS["transactions"].items():
        print(f"  - {name}: {id}")
    
    trans_name = get_input("Select transaction (name)")
    
    if trans_name not in STORED_IDS["transactions"]:
        print("Transaction name not found.")
        input("\nPress Enter to continue...")
        return
    
    print("\nAvailable categories:")
    for name, id in STORED_IDS["categories"].items():
        print(f"  - {name}: {id}")
    
    category_name = get_input("Select category (name)")
    
    if category_name not in STORED_IDS["categories"]:
        print("Category name not found.")
        input("\nPress Enter to continue...")
        return
    
    # We need a user ID for the categorization
    if not STORED_IDS["users"]:
        print("You need to create a user first.")
        input("\nPress Enter to continue...")
        return
    
    print("\nAvailable users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select user (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found.")
        input("\nPress Enter to continue...")
        return
    
    data = {
        "transaction_id": STORED_IDS["transactions"][trans_name],
        "category_id": STORED_IDS["categories"][category_name]
    }
    
    params = {"user_id": STORED_IDS["users"][user_name]}
    
    make_request("post", "/transactions/categorize", data, params)
    input("\nPress Enter to continue...")

# Category operations
def create_category():
    print_header("Create Category")
    
    name = get_input("Category Name")
    icon = get_input("Icon (optional)")
    
    data = {
        "name": name
    }
    
    if icon:
        data["icon"] = icon
    
    # If we have existing categories, ask if this is a subcategory
    if STORED_IDS["categories"]:
        is_subcategory = get_input("Is this a subcategory? (y/n)", "n").lower() == "y"
        if is_subcategory:
            print("\nAvailable parent categories:")
            for name, id in STORED_IDS["categories"].items():
                print(f"  - {name}: {id}")
            
            parent_name = get_input("Select parent category (name)")
            if parent_name in STORED_IDS["categories"]:
                data["parent_category_id"] = STORED_IDS["categories"][parent_name]
    
    result = make_request("post", "/categories", data)
    if result and "id" in result:
        STORED_IDS["categories"][result["name"]] = result["id"]
        print(f"\nStored category ID for {result['name']}: {result['id']}")
    
    input("\nPress Enter to continue...")

def list_categories():
    print_header("List Categories")
    
    filter_type = get_input("Filter categories? (all/top-level/subcategories)", "all")
    
    params = {}
    
    if filter_type.lower() == "top-level":
        params["top_level_only"] = "true"
    elif filter_type.lower() == "subcategories":
        if not STORED_IDS["categories"]:
            print("You need to create categories first.")
            input("\nPress Enter to continue...")
            return
        
        print("Available categories:")
        for name, id in STORED_IDS["categories"].items():
            print(f"  - {name}: {id}")
        
        parent_name = get_input("Select parent category (name)")
        
        if parent_name not in STORED_IDS["categories"]:
            print("Category name not found.")
            input("\nPress Enter to continue...")
            return
        
        params["parent_id"] = STORED_IDS["categories"][parent_name]
    
    make_request("get", "/categories", params=params)
    input("\nPress Enter to continue...")

# Plaid operations
def generate_link_token():
    print_header("Generate Plaid Link Token")
    
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
    
    # Use the user_id in the request body instead of path
    user_id = STORED_IDS["users"][user_name]
    data = {"user_id": user_id}
    
    # Call the updated endpoint
    result = make_request("post", "/plaid/link", data)
    
    input("\nPress Enter to continue...")

def create_sandbox_token():
    print_header("Create Plaid Sandbox Token")
    
    institution_id = get_input("Institution ID", "ins_109508")  # Default for Chase
    
    # List of available products: auth, transactions, identity, income, assets, etc.
    products_input = get_input("Initial Products (comma-separated)", "transactions")
    initial_products = [p.strip() for p in products_input.split(",")]
    
    data = {
        "institution_id": institution_id,
        "initial_products": initial_products
    }
    
    result = make_request("post", "/plaid/sandbox/create_token", data)
    
    if result and "public_token" in result:
        print("\nPublic Token created successfully!")
        print("You can now use this token with the /plaid/exchange endpoint")
        print(f"Public Token: {result['public_token']}")
        
        # Ask if user wants to immediately exchange this token
        proceed = get_input("Exchange this token now? (y/n)", "y").lower() == "y"
        if proceed:
            exchange_public_token(result["public_token"])
    
    input("\nPress Enter to continue...")

def exchange_public_token(public_token=None):
    print_header("Exchange Public Token")
    
    if not STORED_IDS["users"]:
        print("You need to create a user first.")
        input("\nPress Enter to continue...")
        return
    
    # Get public token if not provided
    if not public_token:
        public_token = get_input("Public Token")
    else:
        print(f"Using public token: {public_token}")
    
    # Select user
    print("\nAvailable users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select user (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found.")
        input("\nPress Enter to continue...")
        return
    
    # Create the metadata (minimal for sandbox)
    metadata = {
        "institution": {
            "name": "Sandbox Bank",
            "institution_id": "ins_sandbox"
        }
    }
    
    data = {
        "public_token": public_token,
        "metadata": metadata,
        "user_id": STORED_IDS["users"][user_name]
    }
    
    result = make_request("post", "/plaid/exchange", data)
    
    if result and "accounts" in result:
        print("\nAccounts created successfully!")
        for account in result["accounts"]:
            account_name = f"{account['name']} (Plaid)"
            STORED_IDS["accounts"][account_name] = account["id"]
            print(f"  - Added account: {account_name}")
    
    input("\nPress Enter to continue...")

def plaid_menu():
    while True:
        print_header("Plaid Integration")
        print("1. Generate Link Token")
        print("2. Create Sandbox Token")
        print("3. Exchange Public Token")
        print("4. Sync Transactions")
        print("0. Back to Main Menu")
        
        plaid_choice = get_input("\nEnter your choice")
        
        if plaid_choice == "0":
            break
        elif plaid_choice == "1":
            generate_link_token()
        elif plaid_choice == "2":
            create_sandbox_token()
        elif plaid_choice == "3":
            exchange_public_token()
        elif plaid_choice == "4":
            sync_transactions()

def sync_transactions():
    print_header("Sync Plaid Transactions")
    
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
    
    user_id = STORED_IDS["users"][user_name]
    data = {"user_id": user_id}
    
    # Call the updated endpoint for syncing transactions
    result = make_request("post", "/plaid/transactions/sync", data)
    
    if result and result.get("status") == "success":
        print("\nTransactions synced successfully!")
        if "accounts_synced" in result:
            print(f"Synced {result['accounts_synced']} accounts")
        if "sync_results" in result:
            print("\nSync results by institution:")
            for item_result in result["sync_results"]:
                if "error" in item_result:
                    print(f"  - {item_result['institution']}: Error: {item_result['error']}")
                else:
                    print(f"  - {item_result['institution']}: Success")
                    details = item_result.get("result", {})
                    print(f"    Added: {details.get('added', 0)} transactions")
                    print(f"    Updated: {details.get('modified', 0)} transactions")
                    print(f"    Removed: {details.get('removed', 0)} transactions")

        # After sync, fetch the transactions to get their IDs
        print("\nFetching transactions to store their IDs...")
        transactions = make_request("get", "/transactions", params={"user_id": user_id})
        
        if transactions:
            STORED_IDS["transactions"] = STORED_IDS.get("transactions", {})
            for transaction in transactions:
                # Generate a meaningful name for each transaction
                amount_str = "${:.2f}".format(abs(transaction["amount"]))
                direction = "Payment" if transaction["amount"] > 0 else "Charge"
                date_str = transaction["date"]
                desc = transaction["description"][:20]  # Truncate long descriptions
                
                transaction_name = f"{date_str} {direction} {amount_str} - {desc}"
                STORED_IDS["transactions"][transaction_name] = transaction["id"]
                print(f"  - Stored transaction: {transaction_name}")
        
        # Also fetch and store any new categories that were created
        print("\nFetching categories to store their IDs...")
        categories = make_request("get", "/categories")
        
        if categories:
            STORED_IDS["categories"] = STORED_IDS.get("categories", {})
            for category in categories:
                if category["name"] not in STORED_IDS["categories"]:
                    STORED_IDS["categories"][category["name"]] = category["id"]
                    print(f"  - Stored new category: {category['name']}")
    
    input("\nPress Enter to continue...")

# Budget operations
def create_budget():
    print_header("Create Budget")
    
    if not STORED_IDS["couples"]:
        print("You need to create a couple first.")
        input("\nPress Enter to continue...")
        return
    
    if not STORED_IDS["categories"]:
        print("You need to create a category first.")
        input("\nPress Enter to continue...")
        return
    
    if not STORED_IDS["users"]:
        print("You need to create a user first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available couples:")
    for name, id in STORED_IDS["couples"].items():
        print(f"  - {name}: {id}")
    
    couple_name = get_input("Select a couple (name)")
    
    if couple_name not in STORED_IDS["couples"]:
        print("Couple name not found.")
        input("\nPress Enter to continue...")
        return
    
    print("\nAvailable categories:")
    for name, id in STORED_IDS["categories"].items():
        print(f"  - {name}: {id}")
    
    category_name = get_input("Select a category (name)")
    
    if category_name not in STORED_IDS["categories"]:
        print("Category name not found.")
        input("\nPress Enter to continue...")
        return
    
    print("\nAvailable users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select a user for created_by (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found.")
        input("\nPress Enter to continue...")
        return
    
    amount = float(get_input("Amount", "100.0"))
    period = get_input("Period (monthly, weekly, etc.)", "monthly")
    
    # Get today's date as default
    import datetime
    today = datetime.date.today().isoformat()
    start_date = get_input("Start Date (YYYY-MM-DD)", today)
    
    data = {
        "couple_id": STORED_IDS["couples"][couple_name],
        "category_id": STORED_IDS["categories"][category_name],
        "amount": amount,
        "period": period,
        "start_date": start_date,
        "created_by": STORED_IDS["users"][user_name]
    }
    
    result = make_request("post", "/budgets", data)
    if result and "id" in result:
        budget_name = f"{couple_name} - {category_name} (${amount})"
        STORED_IDS["budgets"][budget_name] = result["id"]
        print(f"\nStored budget ID for {budget_name}: {result['id']}")
    
    input("\nPress Enter to continue...")

def update_budget():
    print_header("Update Budget")
    
    if not STORED_IDS["budgets"]:
        print("No budgets have been created yet.")
        input("\nPress Enter to continue...")
        return
    
    if not STORED_IDS["users"]:
        print("You need a user to update the budget.")
        input("\nPress Enter to continue...")
        return
    
    print("Available budgets:")
    for name, id in STORED_IDS["budgets"].items():
        print(f"  - {name}: {id}")
    
    budget_name = get_input("Select a budget (name)")
    
    if budget_name not in STORED_IDS["budgets"]:
        print("Budget name not found.")
        input("\nPress Enter to continue...")
        return
    
    print("\nAvailable users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select a user for updated_by (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found.")
        input("\nPress Enter to continue...")
        return
    
    # Get current budget details to capture previous amount
    budget_id = STORED_IDS["budgets"][budget_name]
    current_budget = make_request("get", f"/budgets/{budget_id}")
    
    if not current_budget:
        print("Could not retrieve current budget details.")
        input("\nPress Enter to continue...")
        return
    
    previous_amount = current_budget.get("amount", 0)
    
    amount = float(get_input("New Amount", str(previous_amount)))
    period = get_input("New Period (monthly, weekly, etc.)", current_budget.get("period", "monthly"))
    
    data = {
        "amount": amount,
        "period": period,
        "updated_by": STORED_IDS["users"][user_name],
        "previous_amount": previous_amount
    }
    
    result = make_request("put", f"/budgets/{budget_id}", data)
    
    input("\nPress Enter to continue...")

def delete_budget():
    print_header("Delete Budget")
    
    if not STORED_IDS["budgets"]:
        print("No budgets have been created yet.")
        input("\nPress Enter to continue...")
        return
    
    if not STORED_IDS["users"]:
        print("You need a user to delete the budget.")
        input("\nPress Enter to continue...")
        return
    
    print("Available budgets:")
    for name, id in STORED_IDS["budgets"].items():
        print(f"  - {name}: {id}")
    
    budget_name = get_input("Select a budget to delete (name)")
    
    if budget_name not in STORED_IDS["budgets"]:
        print("Budget name not found.")
        input("\nPress Enter to continue...")
        return
    
    print("\nAvailable users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select a user performing the deletion (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found.")
        input("\nPress Enter to continue...")
        return
    
    budget_id = STORED_IDS["budgets"][budget_name]
    
    # Add user_id as a query parameter
    params = {
        "user_id": STORED_IDS["users"][user_name]
    }
    
    result = make_request("delete", f"/budgets/{budget_id}", params=params)
    
    if result and result.get("success"):
        print(f"\nBudget {budget_name} deleted successfully.")
        # Remove from stored IDs
        del STORED_IDS["budgets"][budget_name]
    
    input("\nPress Enter to continue...")

def list_budgets():
    print_header("List Stored Budgets")
    
    if not STORED_IDS["budgets"]:
        print("No budgets have been created yet.")
    else:
        print("Available budgets:")
        for name, id in STORED_IDS["budgets"].items():
            print(f"  - {name}: {id}")
    
    input("\nPress Enter to continue...")

def budget_menu():
    while True:
        print_header("Budget Operations")
        print("1. Create Budget")
        print("2. List Budgets")
        print("3. Update Budget")
        print("4. Delete Budget")
        print("5. Get Budget Analysis")
        print("0. Back to Main Menu")
        
        budget_choice = get_input("\nEnter your choice")
        
        if budget_choice == "0":
            break
        elif budget_choice == "1":
            create_budget()
        elif budget_choice == "2":
            list_budgets()
        elif budget_choice == "3":
            update_budget()
        elif budget_choice == "4":
            delete_budget()
        # elif budget_choice == "5":
        #     get_budget_analysis()

# Rebalance operations
def suggest_rebalance():
    print_header("Suggest Goal Rebalancing")
    
    if not STORED_IDS["couples"]:
        print("You need to create a couple first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available couples:")
    for name, id in STORED_IDS["couples"].items():
        print(f"  - {name}: {id}")
    
    couple_name = get_input("Select couple (name)")
    
    if couple_name not in STORED_IDS["couples"]:
        print("Couple name not found.")
        input("\nPress Enter to continue...")
        return
    
    couple_id = STORED_IDS["couples"][couple_name]
    params = {"couple_id": couple_id}
    
    result = make_request("get", "/rebalance/suggest", params=params)
    
    if result:
        print("\nRebalance suggestions:")
        if not result:  # Empty list
            print("No rebalance suggestions available.")
        else:
            for idx, suggestion in enumerate(result, 1):
                print(f"\nSuggestion {idx}:")
                print(f"  From: {suggestion['source_goal_name']} (ID: {suggestion['source_goal_id']})")
                print(f"  To: {suggestion['dest_goal_name']} (ID: {suggestion['dest_goal_id']})")
                print(f"  Amount: ${suggestion['suggested_amount']:.2f}")
    
    input("\nPress Enter to continue...")

def execute_rebalance():
    print_header("Execute Goal Rebalancing")
    
    if not STORED_IDS["users"] or not STORED_IDS["goals"]:
        print("You need users and goals first.")
        input("\nPress Enter to continue...")
        return
    
    # Get user
    print("Available users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select user (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found.")
        input("\nPress Enter to continue...")
        return
    
    user_id = STORED_IDS["users"][user_name]
    
    # Print available goals
    print("\nAvailable goals:")
    for name, id in STORED_IDS["goals"].items():
        print(f"  - {name}: {id}")
    
    # Get number of moves
    try:
        num_moves = int(get_input("How many reallocation moves to make?", "1"))
    except ValueError:
        print("Invalid number.")
        input("\nPress Enter to continue...")
        return
    
    moves = []
    for i in range(num_moves):
        print(f"\nMove {i+1}:")
        source_goal_name = get_input("Source Goal Name")
        dest_goal_name = get_input("Destination Goal Name")
        
        if source_goal_name not in STORED_IDS["goals"] or dest_goal_name not in STORED_IDS["goals"]:
            print("Source or destination goal name not found.")
            continue
        
        try:
            amount = float(get_input("Amount to move"))
            if amount <= 0:
                print("Amount must be positive.")
                continue
        except ValueError:
            print("Invalid amount.")
            continue
        
        note = get_input("Note (optional)")
        
        moves.append({
            "source_goal_id": STORED_IDS["goals"][source_goal_name],
            "dest_goal_id": STORED_IDS["goals"][dest_goal_name],
            "amount": amount,
            "note": note
        })
    
    if not moves:
        print("No valid moves specified.")
        input("\nPress Enter to continue...")
        return
    
    data = {
        "rebalance_id": get_input("Rebalance ID (optional)", None),
        "moves": moves
    }
    
    params = {"user_id": user_id}
    result = make_request("post", "/rebalance/commit", data, params)
    
    input("\nPress Enter to continue...")

# Surplus operations
def calculate_surplus():
    print_header("Calculate Surplus")
    
    if not STORED_IDS["couples"] or not STORED_IDS["accounts"]:
        print("You need couples and accounts first.")
        input("\nPress Enter to continue...")
        return
    
    print("Available couples:")
    for name, id in STORED_IDS["couples"].items():
        print(f"  - {name}: {id}")
    
    couple_name = get_input("Select couple (name)")
    
    if couple_name not in STORED_IDS["couples"]:
        print("Couple name not found.")
        input("\nPress Enter to continue...")
        return
    
    couple_id = STORED_IDS["couples"][couple_name]
    
    # Print available accounts
    print("\nAvailable accounts:")
    for name, id in STORED_IDS["accounts"].items():
        print(f"  - {name}: {id}")
    
    # Get accounts to consider
    account_names = []
    while True:
        account_name = get_input("\nEnter account name (or leave blank to finish)")
        if not account_name:
            break
        
        if account_name not in STORED_IDS["accounts"]:
            print("Account name not found.")
            continue
            
        account_names.append(account_name)
    
    if not account_names:
        print("No valid accounts specified.")
        input("\nPress Enter to continue...")
        return
    
    account_ids = [STORED_IDS["accounts"][name] for name in account_names]
    
    # Get buffer percentage
    try:
        buffer_percent = float(get_input("Buffer percentage", "30"))
        if buffer_percent < 0 or buffer_percent > 100:
            print("Buffer percentage must be between 0 and 100.")
            input("\nPress Enter to continue...")
            return
    except ValueError:
        print("Invalid buffer percentage.")
        input("\nPress Enter to continue...")
        return
    
    data = {
        "account_ids": account_ids,
        "buffer_percent": buffer_percent
    }
    
    params = {"couple_id": couple_id}
    result = make_request("post", "/surplus/calculate", data, params)
    
    input("\nPress Enter to continue...")

def allocate_surplus():
    print_header("Allocate Surplus")
    
    if not STORED_IDS["users"] or not STORED_IDS["accounts"] or not STORED_IDS["goals"]:
        print("You need users, accounts, and goals first.")
        input("\nPress Enter to continue...")
        return
    
    # Get user
    print("Available users:")
    for name, id in STORED_IDS["users"].items():
        print(f"  - {name}: {id}")
    
    user_name = get_input("Select user (name)")
    
    if user_name not in STORED_IDS["users"]:
        print("User name not found.")
        input("\nPress Enter to continue...")
        return
    
    user_id = STORED_IDS["users"][user_name]
    
    # Print available accounts
    print("\nAvailable accounts:")
    for name, id in STORED_IDS["accounts"].items():
        print(f"  - {name}: {id}")
    
    # Print available goals
    print("\nAvailable goals:")
    for name, id in STORED_IDS["goals"].items():
        print(f"  - {name}: {id}")
    
    # Get number of allocations
    try:
        num_allocations = int(get_input("How many surplus allocations to make?", "1"))
    except ValueError:
        print("Invalid number.")
        input("\nPress Enter to continue...")
        return
    
    allocations = []
    for i in range(num_allocations):
        print(f"\nAllocation {i+1}:")
        account_name = get_input("Source account name")
        goal_name = get_input("Destination goal name")
        
        if account_name not in STORED_IDS["accounts"] or goal_name not in STORED_IDS["goals"]:
            print("Account or goal name not found.")
            continue
        
        try:
            amount = float(get_input("Amount to allocate"))
            if amount <= 0:
                print("Amount must be positive.")
                continue
        except ValueError:
            print("Invalid amount.")
            continue
        
        note = get_input("Note (optional)")
        
        allocations.append({
            "account_id": STORED_IDS["accounts"][account_name],
            "goal_id": STORED_IDS["goals"][goal_name],
            "amount": amount,
            "note": note
        })
    
    if not allocations:
        print("No valid allocations specified.")
        input("\nPress Enter to continue...")
        return
    
    data = {
        "surplus_id": get_input("Surplus ID (optional)", None),
        "allocations": allocations
    }
    
    params = {"user_id": user_id}
    result = make_request("post", "/surplus/allocate", data, params)
    
    input("\nPress Enter to continue...")

def main_menu():
    while True:
        print_header("CFO Command Center Test Client")
        
        print("1. Users")
        print("2. Couples")
        print("3. Bank Accounts")
        print("4. Financial Goals")
        print("5. Ledger Events")
        print("6. Transactions")
        print("7. Categories")
        print("8. Plaid Integration")
        print("9. Budgets")
        print("10. Rebalance & Surplus")
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
        
        elif choice == "6":
            while True:
                print_header("Transaction Operations")
                print("1. Create Transaction")
                print("2. List Transactions")
                print("3. Categorize Transaction")
                print("0. Back to Main Menu")
                
                transaction_choice = get_input("\nEnter your choice")
                
                if transaction_choice == "0":
                    break
                elif transaction_choice == "1":
                    create_transaction()
                elif transaction_choice == "2":
                    list_transactions()
                elif transaction_choice == "3":
                    categorize_transaction()
        
        elif choice == "7":
            while True:
                print_header("Category Operations")
                print("1. Create Category")
                print("2. List Categories")
                print("0. Back to Main Menu")
                
                category_choice = get_input("\nEnter your choice")
                
                if category_choice == "0":
                    break
                elif category_choice == "1":
                    create_category()
                elif category_choice == "2":
                    list_categories()
        
        elif choice == "8":
            plaid_menu()
        
        elif choice == "9":
            budget_menu()
        
        elif choice == "10":
            while True:
                print_header("Rebalance & Surplus Operations")
                print("1. Suggest Goal Rebalancing")
                print("2. Execute Goal Rebalancing")
                print("3. Calculate Surplus")
                print("4. Allocate Surplus")
                print("0. Back to Main Menu")
                
                rebalance_choice = get_input("\nEnter your choice")
                
                if rebalance_choice == "0":
                    break
                elif rebalance_choice == "1":
                    suggest_rebalance()
                elif rebalance_choice == "2":
                    execute_rebalance()
                elif rebalance_choice == "3":
                    calculate_surplus()
                elif rebalance_choice == "4":
                    allocate_surplus()

if __name__ == "__main__":
    try:
        # Check if server is running
        requests.get(f"{BASE_URL}/users")
        main_menu()
    except requests.ConnectionError:
        print(f"Error: Cannot connect to the API at {BASE_URL}")
        print("Make sure your FastAPI server is running.")
        sys.exit(1)
