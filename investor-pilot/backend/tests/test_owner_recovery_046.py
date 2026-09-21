import sqlite3
import pytest
from argon2 import PasswordHasher
from app.services.local_owner_recovery import reset_owner

def test_recovery_preserves_account_and_rejects_wrong_target(tmp_path):
 db=tmp_path/"accounts.db"
 with sqlite3.connect(db) as c:
  c.execute("CREATE TABLE users (id TEXT,email TEXT,role TEXT,is_active INT,hashed_password TEXT)")
  c.execute("INSERT INTO users VALUES ('owner','owner@example.test','admin',1,'original')")
 for email,password,confirm in [("missing@example.test","new-secure-pass","new-secure-pass"),("owner@example.test","short","short"),("owner@example.test","new-secure-pass","mismatch")]:
  with pytest.raises(ValueError):reset_owner(db,email,password,confirm)
  with sqlite3.connect(db) as c:assert c.execute("SELECT hashed_password FROM users").fetchone()[0]=="original"
 reset_owner(db,"OWNER@example.test","new-secure-pass","new-secure-pass")
 with sqlite3.connect(db) as c:
  row=c.execute("SELECT id,role,is_active,hashed_password FROM users").fetchone()
 assert row[:3]==("owner","admin",1) and PasswordHasher().verify(row[3],"new-secure-pass")
