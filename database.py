import sqlite3
import json
import uuid
import hashlib
from datetime import datetime

DB_FILE = "inventory.db"

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # пользователи
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        # товары
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                params TEXT,
                serial_number TEXT,
                model TEXT,
                individual_code TEXT,
                ssuid TEXT,
                barcodes TEXT,
                price REAL DEFAULT 0
            )
        ''')
        # транзакции Авито
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS avito_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                contact TEXT NOT NULL,
                full_name TEXT NOT NULL,
                worker_id INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # выставки Авито
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS avito_listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                listing_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                worker_id INTEGER NOT NULL
            )
        ''')
        # настройки
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        self.conn.commit()

        # администратор по умолчанию
        self.cursor.execute("SELECT COUNT(*) FROM users")
        if self.cursor.fetchone()[0] == 0:
            pwd_hash = hashlib.sha256("2910_kiRIll".encode()).hexdigest()
            self.cursor.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                ("Ushimura@pandora.biz", pwd_hash, "admin")
            )
            self.conn.commit()

        # настройки по умолчанию
        default_settings = {
            "company_name": "ООО \"Ромашка\"",
            "inn": "1234567890",
            "tax_system": "УСН",
            "city_address": "г. Москва, ул. Примерная, д.1",
            "seller_position": "Менеджер",
            "seller_name": "Иванов И.И.",
            "receipt_counter": "1"
        }
        for k, v in default_settings.items():
            if not self.get_setting(k):
                self.set_setting(k, v)

    # ----- пользователи -----
    def get_user(self, email, password):
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        self.cursor.execute("SELECT id, email, role FROM users WHERE email=? AND password_hash=?", (email, pwd_hash))
        return self.cursor.fetchone()

    def add_user(self, email, password, role):
        try:
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            self.cursor.execute("INSERT INTO users (email, password_hash, role) VALUES (?,?,?)", (email, pwd_hash, role))
            self.conn.commit()
            return True
        except:
            return False

    def get_all_users(self):
        self.cursor.execute("SELECT id, email, role FROM users")
        return self.cursor.fetchall()

    def delete_user(self, user_id):
        self.cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.conn.commit()

    def update_user_role(self, user_id, role):
        self.cursor.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
        self.conn.commit()

    # ----- товары -----
    def add_item(self, name, params, serial, model, individual, ssuid, barcodes, price):
        item_uuid = str(uuid.uuid4())
        barcodes_str = json.dumps(barcodes)
        self.cursor.execute('''
            INSERT INTO items (uuid, name, params, serial_number, model, individual_code, ssuid, barcodes, price)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (item_uuid, name, params, serial, model, individual, ssuid, barcodes_str, price))
        self.conn.commit()
        return item_uuid

    def get_items(self):
        self.cursor.execute("SELECT id, uuid, name, params, serial_number, model, individual_code, ssuid, barcodes, price FROM items")
        rows = self.cursor.fetchall()
        items = []
        for row in rows:
            items.append({
                "id": row[0], "uuid": row[1], "name": row[2], "params": row[3],
                "serial_number": row[4], "model": row[5], "individual_code": row[6],
                "ssuid": row[7], "barcodes": json.loads(row[8]), "price": row[9]
            })
        return items

    def get_item_by_id(self, item_id):
        self.cursor.execute("SELECT id, uuid, name, params, serial_number, model, individual_code, ssuid, barcodes, price FROM items WHERE id=?", (item_id,))
        row = self.cursor.fetchone()
        if row:
            return {"id": row[0], "uuid": row[1], "name": row[2], "params": row[3],
                    "serial_number": row[4], "model": row[5], "individual_code": row[6],
                    "ssuid": row[7], "barcodes": json.loads(row[8]), "price": row[9]}
        return None

    def update_item(self, item_id, name, params, serial, model, individual, ssuid, price):
        self.cursor.execute('''
            UPDATE items SET name=?, params=?, serial_number=?, model=?,
            individual_code=?, ssuid=?, price=? WHERE id=?
        ''', (name, params, serial, model, individual, ssuid, price, item_id))
        self.conn.commit()

    def delete_item(self, item_id):
        self.cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
        self.conn.commit()

    # ----- транзакции -----
    def add_avito_transaction(self, tr_id, tr_type, contact, full_name, worker_id, amount):
        try:
            self.cursor.execute('''
                INSERT INTO avito_transactions (transaction_id, type, contact, full_name, worker_id, total_amount)
                VALUES (?,?,?,?,?,?)
            ''', (tr_id, tr_type, contact, full_name, worker_id, amount))
            self.conn.commit()
            return True
        except:
            return False

    def get_avito_transactions(self, start=None, end=None):
        if start and end:
            self.cursor.execute("SELECT * FROM avito_transactions WHERE timestamp BETWEEN ? AND ?", (start, end))
        else:
            self.cursor.execute("SELECT * FROM avito_transactions")
        rows = self.cursor.fetchall()
        return [{"id": r[0], "transaction_id": r[1], "type": r[2], "contact": r[3],
                 "full_name": r[4], "worker_id": r[5], "total_amount": r[6], "timestamp": r[7]} for r in rows]

    # ----- выставки -----
    def add_avito_listing(self, item_id, status, worker_id):
        self.cursor.execute("INSERT INTO avito_listings (item_id, status, worker_id) VALUES (?,?,?)", (item_id, status, worker_id))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_avito_listings(self):
        self.cursor.execute('''
            SELECT l.id, l.item_id, i.name, l.status, l.listing_date, l.worker_id, u.email
            FROM avito_listings l
            JOIN items i ON l.item_id = i.id
            JOIN users u ON l.worker_id = u.id
        ''')
        rows = self.cursor.fetchall()
        return [{"id": r[0], "item_id": r[1], "item_name": r[2], "status": r[3],
                 "listing_date": r[4], "worker_id": r[5], "worker_email": r[6]} for r in rows]

    def update_avito_listing_status(self, listing_id, status):
        self.cursor.execute("UPDATE avito_listings SET status=? WHERE id=?", (status, listing_id))
        self.conn.commit()

    # ----- настройки -----
    def get_setting(self, key, default=None):
        self.cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = self.cursor.fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.cursor.execute("REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        self.conn.commit()

    def reset_database(self):
        self.cursor.execute("DELETE FROM items")
        self.cursor.execute("DELETE FROM avito_transactions")
        self.cursor.execute("DELETE FROM avito_listings")
        self.cursor.execute("DELETE FROM settings")
        self.cursor.execute("DELETE FROM users WHERE email != 'Ushimura@pandora.biz'")
        self.conn.commit()
        self.create_tables()
