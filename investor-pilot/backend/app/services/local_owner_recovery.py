"""Interactive, local-only owner password recovery. No HTTP recovery endpoint."""
import argparse
import getpass
import sqlite3
import sys
from pathlib import Path
from argon2 import PasswordHasher

def reset_owner(database,email,password,confirm):
 if password!=confirm:raise ValueError("Passwords do not match.")
 if len(password)<12 or len(password)>256:raise ValueError("Use 12 to 256 characters.")
 database=Path(database).resolve()
 if not database.is_file():raise ValueError("Existing account database not found.")
 with sqlite3.connect(database.as_uri()+"?mode=rw",uri=True) as connection:
  connection.execute("BEGIN IMMEDIATE")
  user=connection.execute("SELECT id,role,is_active FROM users WHERE lower(email)=?",(email.strip().lower(),)).fetchone()
  if not user or user[1]!="admin" or not user[2]:raise ValueError("An active administrator with that email was not found.")
  hashed=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2,hash_len=32,salt_len=16).hash(password)
  connection.execute("UPDATE users SET hashed_password=? WHERE id=?",(hashed,user[0]))

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument("--database",required=True);parser.add_argument("--email",required=True)
 args=parser.parse_args()
 if not sys.stdin.isatty():raise SystemExit("Run in an interactive local terminal; passwords are never accepted as command arguments.")
 print("Account: "+args.email+" | Database: "+str(Path(args.database).resolve()))
 if input("Type RESET to change this account password: ").strip()!="RESET":raise SystemExit("Cancelled.")
 password=getpass.getpass("New password (12+ characters, hidden): ")
 confirm=getpass.getpass("Confirm new password (hidden): ")
 try:reset_owner(args.database,args.email,password,confirm)
 except ValueError as exc:raise SystemExit(str(exc))
 print("Password updated. Sign in using the new password.")
if __name__=="__main__":main()
