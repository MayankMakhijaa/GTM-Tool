import argparse
import sys
from app.database import db_session
from app.models.all_models import UserTable, UserRole, AuditLog
from app.services.auth_service import normalize_email

def promote_user(email: str, target_role: str = UserRole.SUPER_ADMIN.value, confirm: bool = False):
    norm_email = normalize_email(email)
    if not norm_email:
        print("Error: A valid email address is required.", file=sys.stderr)
        return False

    user = db_session.query(UserTable).filter_by(email_id=norm_email).first()
    if not user:
        print(f"Error: User with email '{norm_email}' not found.", file=sys.stderr)
        return False

    if not user.email_verified_at:
        print(f"Error: User with email '{norm_email}' is not email-verified. Only verified accounts can be promoted.", file=sys.stderr)
        return False

    if not user.is_active:
        print(f"Error: User with email '{norm_email}' is inactive.", file=sys.stderr)
        return False

    if user.role == target_role:
        print(f"Notice: User '{norm_email}' already has role '{target_role}'.")
        return True

    if not confirm:
        print(f"Confirmation required: promote user '{norm_email}' (ID: {user.user_id}) from role '{user.role}' to '{target_role}'? Run with --confirm to proceed.")
        return False

    old_role = user.role
    user.role = target_role

    audit_entry = AuditLog(
        admin_user_id=None,  # System CLI bootstrap action
        target_user_id=user.user_id,
        action="CLI_ROLE_PROMOTION",
        metadata_json={
            "old_role": old_role,
            "new_role": target_role,
            "initiated_via": "cli.promote_user"
        }
    )
    db_session.add(audit_entry)

    try:
        db_session.commit()
        print(f"Success: User '{norm_email}' successfully promoted to '{target_role}'.")
        return True
    except Exception as e:
        db_session.rollback()
        print(f"Error: Database error during promotion: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Fameweb Admin CLI Management")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    promote_parser = subparsers.add_parser("promote-user", help="Promote an existing verified user to SUPER_ADMIN")
    promote_parser.add_argument("--email", required=True, help="Verified business email of the target user")
    promote_parser.add_argument("--role", default=UserRole.SUPER_ADMIN.value, choices=[r.value for r in UserRole], help="Target role (default: SUPER_ADMIN)")
    promote_parser.add_argument("--confirm", action="store_true", help="Explicitly confirm the promotion")

    args = parser.parse_args()

    if args.command == "promote-user":
        success = promote_user(args.email, target_role=args.role, confirm=args.confirm)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
