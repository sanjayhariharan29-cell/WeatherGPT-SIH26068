#!/usr/bin/env python3
"""
scripts/promote_developer.py - Admin CLI tool to promote or assign user roles.

Usage:
    # Promote by email to developer (default role: developer)
    python scripts/promote_developer.py --email user@example.com

    # Promote by user ID
    python scripts/promote_developer.py --id <user-uuid>

    # Assign specific role (developer, admin, user)
    python scripts/promote_developer.py --email user@example.com --role developer
    python scripts/promote_developer.py --email user@example.com --role user  # (demote)

    # List all developers and admins
    python scripts/promote_developer.py --list

Direct Database SQL Alternative:
    sqlite3 weathergpt.db "UPDATE users SET role = 'developer' WHERE email = 'user@example.com';"
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func
from backend.db.session import SessionLocal
from backend.db.init_db import init_db
from backend.db.models import User

ALLOWED_ROLES = ("user", "developer", "admin")


def promote_user(
    identifier: str,
    by: str = "email",
    target_role: str = "developer",
    db_session=None
) -> Dict[str, Any]:
    """Promotes or changes the role of a user identified by email or ID.

    Args:
        identifier: The email or user ID to search for.
        by: Search by "email" or "id".
        target_role: The role to set ("user", "developer", "admin").
        db_session: Optional SQLAlchemy session; creates a new one if not provided.

    Returns:
        Dict with status and user details.

    Raises:
        ValueError: If role is invalid or user is not found.
    """
    target_role = target_role.strip().lower()
    if target_role not in ALLOWED_ROLES:
        raise ValueError(f"Invalid role '{target_role}'. Must be one of: {', '.join(ALLOWED_ROLES)}")

    identifier_clean = identifier.strip()
    if not identifier_clean:
        raise ValueError("Identifier (email or user ID) cannot be empty.")

    close_session = False
    if db_session is None:
        init_db()
        db_session = SessionLocal()
        close_session = True

    try:
        if by == "id":
            user = db_session.query(User).filter(User.id == identifier_clean).first()
        else:
            user = db_session.query(User).filter(func.lower(User.email) == identifier_clean.lower()).first()

        if not user:
            raise ValueError(f"User not found with {by}: '{identifier_clean}'")

        previous_role = user.role or "user"
        updated = False

        if previous_role == target_role:
            message = f"User '{user.email}' already has role '{target_role}'. No update required."
        else:
            user.role = target_role
            db_session.commit()
            db_session.refresh(user)
            updated = True
            message = f"Successfully updated user '{user.email}' role: {previous_role} -> {target_role}"

        return {
            "success": True,
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "previous_role": previous_role,
            "new_role": user.role,
            "updated": updated,
            "message": message,
        }
    finally:
        if close_session:
            db_session.close()


def list_users(role_filter: Optional[str] = None, db_session=None) -> List[Dict[str, Any]]:
    """Lists registered users and their roles."""
    close_session = False
    if db_session is None:
        init_db()
        db_session = SessionLocal()
        close_session = True

    try:
        query = db_session.query(User)
        if role_filter:
            query = query.filter(User.role == role_filter.strip().lower())
        users = query.order_by(User.created_at.desc()).all()

        return [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": u.role or "user",
                "is_verified": u.is_verified,
            }
            for u in users
        ]
    finally:
        if close_session:
            db_session.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Internal admin/CLI tool to promote or modify user roles in WeatherGPT.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/promote_developer.py --email developer@example.com
  python scripts/promote_developer.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890
  python scripts/promote_developer.py --email user@example.com --role developer
  python scripts/promote_developer.py --list
  python scripts/promote_developer.py --list --role developer
        """
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-e", "--email",
        type=str,
        help="Email address of the user account to update."
    )
    group.add_argument(
        "-i", "--id", "--user-id",
        dest="user_id",
        type=str,
        help="UUID/ID of the user account to update."
    )
    group.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all users (optionally filtered by --role)."
    )

    parser.add_argument(
        "-r", "--role",
        type=str,
        default="developer",
        choices=ALLOWED_ROLES,
        help="Target role to assign (default: 'developer'). Choices: %(choices)s"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Handle --list
    if args.list:
        users = list_users(role_filter=args.role if args.role != "developer" else None)
        print(f"\nRegistered Users ({len(users)} found):")
        print(f"{'ID':<38} | {'Name':<20} | {'Email':<30} | {'Role':<12} | {'Verified'}")
        print("-" * 115)
        for u in users:
            print(f"{u['id']:<38} | {u['name'][:18]:<20} | {u['email'][:28]:<30} | {u['role']:<12} | {u['is_verified']}")
        print()
        sys.exit(0)

    # Prompt interactively if neither email nor user_id was given
    email = args.email
    user_id = args.user_id

    if not email and not user_id:
        print("No user specified via command line arguments.")
        try:
            choice = input("Enter email or user ID to promote to developer (or Ctrl+C to cancel): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            sys.exit(1)

        if not choice:
            print("[ERROR] No identifier provided. Aborting.")
            sys.exit(1)

        if "@" in choice:
            email = choice
        else:
            user_id = choice

    # Perform the role promotion
    try:
        if email:
            result = promote_user(identifier=email, by="email", target_role=args.role)
        else:
            result = promote_user(identifier=user_id, by="id", target_role=args.role)

        print("\n========================================================")
        print(f" [SUCCESS] Role Assignment Completed")
        print("========================================================")
        print(f" User ID:       {result['user_id']}")
        print(f" Name:          {result['name']}")
        print(f" Email:         {result['email']}")
        print(f" Previous Role: {result['previous_role']}")
        print(f" New Role:      {result['new_role']}")
        print(f" Updated:       {result['updated']}")
        print(f" Details:       {result['message']}")
        print("========================================================\n")
        sys.exit(0)

    except ValueError as err:
        print(f"\n[ERROR] {err}\n", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[UNEXPECTED ERROR] {exc}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
