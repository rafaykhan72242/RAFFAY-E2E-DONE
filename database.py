import sqlite3
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet
import os
import time
from datetime import datetime

# MongoDB Import with Safe Handling
try:
    import pymongo
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
    print("✅ MongoDB libraries imported successfully")
except ImportError as e:
    MONGODB_AVAILABLE = False
    print(f"⚠️ MongoDB not available: {e}")

DB_PATH = Path(__file__).parent / 'users.db'
ENCRYPTION_KEY_FILE = Path(__file__).parent / '.encryption_key'

def get_encryption_key():
    """Get or create encryption key for cookie storage"""
    if ENCRYPTION_KEY_FILE.exists():
        with open(ENCRYPTION_KEY_FILE, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(ENCRYPTION_KEY_FILE, 'wb') as f:
            f.write(key)
        return key

ENCRYPTION_KEY = get_encryption_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

def init_db():
    """Initialize database with tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            approval_status TEXT DEFAULT 'pending',
            approval_key TEXT,
            real_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id TEXT,
            name_prefix TEXT,
            delay INTEGER DEFAULT 30,
            cookies_encrypted TEXT,
            messages_file_content TEXT,
            automation_running INTEGER DEFAULT 0,
            locked_group_name TEXT,
            locked_nicknames TEXT,
            lock_enabled INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create admin notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create user logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Add new columns if they don't exist
    new_columns = [
        ('users', 'approval_status', 'TEXT DEFAULT "pending"'),
        ('users', 'approval_key', 'TEXT'),
        ('users', 'real_name', 'TEXT'),
        ('user_configs', 'automation_running', 'INTEGER DEFAULT 0'),
        ('user_configs', 'locked_group_name', 'TEXT'),
        ('user_configs', 'locked_nicknames', 'TEXT'),
        ('user_configs', 'lock_enabled', 'INTEGER DEFAULT 0'),
        ('user_configs', 'messages_file_content', 'TEXT')
    ]
    
    for table, column, definition in new_columns:
        try:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    conn.commit()
    conn.close()

def setup_mongodb_connection():
    """Setup MongoDB connection for database operations"""
    if not MONGODB_AVAILABLE:
        print("❌ MongoDB not installed - skipping MongoDB setup")
        return None
        
    try:
        connection_string = "mongodb+srv://dineshsavita76786_user_db:DEVILX0221@cluster0.3xxvjpo.mongodb.net/?retryWrites=true&w=majority"
        client = MongoClient(connection_string, serverSelectionTimeoutMS=10000)
        db = client['streamlit_db']
        
        # Test connection
        client.admin.command('ping')
        print("✅ MongoDB Database Connection Established!")
        return db
    except Exception as e:
        print(f"❌ MongoDB Connection Error: {str(e)[:100]}")
        return None

# Initialize MongoDB connection
mongodb = setup_mongodb_connection()

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def encrypt_cookies(cookies):
    """Encrypt cookies for secure storage"""
    if not cookies:
        return None
    return cipher_suite.encrypt(cookies.encode()).decode()

def decrypt_cookies(encrypted_cookies):
    """Decrypt cookies"""
    if not encrypted_cookies:
        return ""
    try:
        return cipher_suite.decrypt(encrypted_cookies.encode()).decode()
    except:
        return ""

def create_user(username, password):
    """Create new user - FIXED: Returns 3 values (success, message, user_id)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        password_hash = hash_password(password)
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                      (username, password_hash))
        user_id = cursor.lastrowid
        
        cursor.execute('''
            INSERT INTO user_configs (user_id, chat_id, name_prefix, delay, messages_file_content)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, '', '', 30, ''))
        
        conn.commit()
        conn.close()
        return True, "Account created successfully!", user_id  # FIXED: 3 values return
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists!", None  # FIXED: 3 values return
    except Exception as e:
        conn.close()
        return False, f"Error: {str(e)}", None  # FIXED: 3 values return

def verify_user(username, password):
    """Verify user credentials using SHA-256"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and user[1] == hash_password(password):
        return user[0]
    return None

def get_user_config(user_id):
    """Get user configuration"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT chat_id, name_prefix, delay, cookies_encrypted, messages_file_content, automation_running
        FROM user_configs WHERE user_id = ?
    ''', (user_id,))
    
    config = cursor.fetchone()
    conn.close()
    
    if config:
        return {
            'chat_id': config[0] or '',
            'name_prefix': config[1] or '',
            'delay': config[2] or 30,
            'cookies': decrypt_cookies(config[3]),
            'messages_file_content': config[4] or '',
            'automation_running': config[5] or 0
        }
    return None

def update_user_config(user_id, chat_id, name_prefix, delay, cookies, messages_file_content):
    """Update user configuration"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    encrypted_cookies = encrypt_cookies(cookies)
    
    cursor.execute('''
        UPDATE user_configs 
        SET chat_id = ?, name_prefix = ?, delay = ?, cookies_encrypted = ?, 
            messages_file_content = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (chat_id, name_prefix, delay, encrypted_cookies, messages_file_content, user_id))
    
    conn.commit()
    conn.close()

def get_username(user_id):
    """Get username by user ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    return user[0] if user else None

def set_automation_running(user_id, is_running):
    """Set automation running state for a user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE user_configs 
        SET automation_running = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (1 if is_running else 0, user_id))
    
    conn.commit()
    conn.close()

def get_automation_running(user_id):
    """Get automation running state for a user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT automation_running FROM user_configs WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return bool(result[0]) if result else False

# Approval system functions
def get_approval_status(user_id):
    """Get user approval status"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT approval_status FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else 'pending'

def update_approval_status(user_id, status):
    """Update user approval status"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET approval_status = ? WHERE id = ?', (status, user_id))
    conn.commit()
    conn.close()

def set_approval_key(user_id, approval_key):
    """Set approval key for user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET approval_key = ? WHERE id = ?', (approval_key, user_id))
    conn.commit()
    conn.close()

def get_approval_key(user_id):
    """Get approval key for user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT approval_key FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

def update_user_real_name(user_id, real_name):
    """Update user's real name"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET real_name = ? WHERE id = ?', (real_name, user_id))
    conn.commit()
    conn.close()

# Admin functions - YEH NAYE FUNCTIONS ADD KIYE HAIN
def get_pending_approvals():
    """Get all users with pending approval"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, approval_key, real_name 
        FROM users 
        WHERE approval_status = 'pending' OR approval_status IS NULL
    ''')
    
    users = cursor.fetchall()
    conn.close()
    
    return users

def get_all_users():
    """Get all users for admin panel"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, approval_status, real_name, approval_key 
        FROM users 
        ORDER BY created_at DESC
    ''')
    
    users = cursor.fetchall()
    conn.close()
    
    return users

def get_approved_users():
    """Get all approved users with their automation status - YEH NAYA FUNCTION"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.id, u.username, u.approval_key, u.real_name, uc.automation_running
        FROM users u
        LEFT JOIN user_configs uc ON u.id = uc.user_id
        WHERE u.approval_status = 'approved'
    ''')
    
    users = cursor.fetchall()
    conn.close()
    
    return users

def get_user_real_name(user_id):
    """Get user's real name - YEH NAYA FUNCTION"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT real_name FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else ""

# NEW FUNCTIONS FOR ADMIN NOTIFICATIONS - YEH ADD KIYE HAIN
def store_admin_notification(user_id, message):
    """Store admin notifications in database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO admin_notifications (user_id, message) VALUES (?, ?)",
            (user_id, message)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error storing admin notification: {e}")
        return False

def get_admin_notifications():
    """Get all admin notifications"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, message, created_at FROM admin_notifications ORDER BY created_at DESC LIMIT 10"
        )
        notifications = cursor.fetchall()
        conn.close()
        return notifications
    except Exception as e:
        print(f"Error getting admin notifications: {e}")
        return []

def create_admin_notifications_table():
    """Create admin notifications table if not exists"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.commit()
        conn.close()
        print("Admin notifications table created successfully")
    except Exception as e:
        print(f"Error creating admin notifications table: {e}")

# NEW FUNCTIONS FOR USER LOGS - YEH ADD KIYE HAIN JO MISSING THE
def log_user_activity(user_id, log_message):
    """Log user activity to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_logs (user_id, log_message) 
            VALUES (?, ?)
        ''', (user_id, log_message))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error logging user activity: {e}")
        return False

def get_user_logs(user_id, limit=20):
    """Get user activity logs from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT log_message, timestamp 
            FROM user_logs 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (user_id, limit))
        
        logs = cursor.fetchall()
        conn.close()
        
        # Format: [log_message1, log_message2, ...]
        return [log[0] for log in logs]
        
    except Exception as e:
        print(f"Error getting user logs: {e}")
        return []

def get_active_automations():
    """Get list of users with active automations"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username 
            FROM users u
            JOIN user_configs uc ON u.id = uc.user_id
            WHERE uc.automation_running = 1 AND u.approval_status = 'approved'
        ''')
        
        users = cursor.fetchall()
        conn.close()
        return users
        
    except Exception as e:
        print(f"Error getting active automations: {e}")
        return []

def log_admin_notification(user_id, message):
    """Log admin notifications - YEH BHI ADD KIYA"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO admin_notifications (user_id, message) 
            VALUES (?, ?)
        ''', (user_id, message))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error logging admin notification: {e}")
        return False

# Lock system functions (if needed)
def get_lock_config(user_id):
    """Get lock configuration for a user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT chat_id, locked_group_name, locked_nicknames, lock_enabled, cookies_encrypted
        FROM user_configs WHERE user_id = ?
    ''', (user_id,))
    
    config = cursor.fetchone()
    conn.close()
    
    if config:
        import json
        try:
            nicknames = json.loads(config[2]) if config[2] else {}
        except:
            nicknames = {}
        
        return {
            'chat_id': config[0] or '',
            'locked_group_name': config[1] or '',
            'locked_nicknames': nicknames,
            'lock_enabled': bool(config[3]),
            'cookies': decrypt_cookies(config[4])
        }
    return None

def update_lock_config(user_id, chat_id, locked_group_name, locked_nicknames, cookies=None):
    """Update complete lock configuration including chat_id and cookies"""
    import json
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    nicknames_json = json.dumps(locked_nicknames)
    
    if cookies is not None:
        encrypted_cookies = encrypt_cookies(cookies)
        cursor.execute('''
            UPDATE user_configs 
            SET chat_id = ?, locked_group_name = ?, locked_nicknames = ?, 
                cookies_encrypted = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (chat_id, locked_group_name, nicknames_json, encrypted_cookies, user_id))
    else:
        cursor.execute('''
            UPDATE user_configs 
            SET chat_id = ?, locked_group_name = ?, locked_nicknames = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (chat_id, locked_group_name, nicknames_json, user_id))
    
    conn.commit()
    conn.close()

def set_lock_enabled(user_id, enabled):
    """Enable or disable the lock system"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE user_configs 
        SET lock_enabled = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (1 if enabled else 0, user_id))
    
    conn.commit()
    conn.close()

def get_lock_enabled(user_id):
    """Check if lock is enabled for a user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT lock_enabled FROM user_configs WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return bool(result[0]) if result else False

# Initialize database and create admin notifications table
init_db()
create_admin_notifications_table()
