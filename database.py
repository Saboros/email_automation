import sqlite3
import psycopg2
from datetime import datetime
import json
import os

class DatabaseManager:
    def __init__(self):
        self.conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        

    def init_database(self):
        with self.conn.cursor() as cur:
            # Drop existing tables if they exist
            cur.execute("DROP TABLE IF EXISTS conversations")
            cur.execute("DROP TABLE IF EXISTS email_activities")
            
            # Create new tables
            cur.execute("""CREATE TABLE conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT,
                    generated_text TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""CREATE TABLE email_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    context TEXT,
                    generated_text TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def save_conversation(self, role, content, context=None, generated_text=None):
        if isinstance(content, (list, dict)):
            content = json.dumps(content)

        with self.conn.cursor(self) as cur:
            cur.execute(
                "INSERT INTO conversations (role, content, context, generated_text) VALUES (?, ?, ?, ?)",
                (role, content, context, generated_text)
            )   
        
    def get_recent_conversation(self, limit = 10):
        with self.conn.cursor() as cur:
            cursor = cur.execute(
                "SELECT role, content, context FROM conversations ORDER BY timestamp DESC LIMIT ?",
                (limit,)

            )
            return cursor.fetchall()
    
    def get_recent_email_activities(self, limit = 5):
        with self.conn.cursor() as cur:
            cursor = cur.execute(
                "SELECT recipient, subject, context, generated_text FROM email_activities ORDER BY timestamp DESC LIMIT ?",
                (limit,)

            )
        return cur.fetchall()


    
    def save_email_activity(self, recipient, subject, context, generated_text):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO email_activities (recipient, subject, context, generated_text) VALUES (?, ?, ?, ?)",
                (recipient, subject, context, generated_text)
            )
    
    def execute_query(self, query):
        try:
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            return results
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []