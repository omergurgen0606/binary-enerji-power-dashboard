import getpass
import os
import sys

import bcrypt
import psycopg2

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "timescaledb"),
    "port": 5432,
    "dbname": "postgres",
    "user": "postgres",
    "password": os.environ["POSTGRES_PASSWORD"]
}

def main():
    if len(sys.argv) != 2:
        print("Kullanim: python create_user.py <kullanici_adi>")
        sys.exit(1)

    username = sys.argv[1]
    password = getpass.getpass("Sifre: ")
    if password != getpass.getpass("Sifre (tekrar): "):
        print("Sifreler eslesmiyor.")
        sys.exit(1)

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
        (username, password_hash),
    )
    cur.close()
    conn.close()
    print(f"Kullanici olusturuldu: {username}")

if __name__ == "__main__":
    main()
