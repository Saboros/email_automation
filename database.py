import psycopg2
from datetime import datetime
import json
import os

class DatabaseManager:
    def __init__(self, user_id):
        self.conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        self.user_id = user_id
        self.check_tables()
        
    def create_conversations_table(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE conversations (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT,
                    generated_text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()
            
    def create_email_activities_table(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE email_activities (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    context TEXT,
                    generated_text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()

    def save_conversation(self, role, content, context=None, generated_text=None):
        if isinstance(content, (list, dict)):
            content = json.dumps(content)

        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO conversations 
                   (user_id, role, content, context, generated_text) 
                   VALUES (%s, %s, %s, %s, %s)""",
                (self.user_id, role, content, context, generated_text)
            )
            self.conn.commit()
        
    def get_recent_conversation(self, limit=10):
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT role, content, context 
                   FROM conversations 
                   WHERE user_id = %s 
                   ORDER BY timestamp DESC LIMIT %s""",
                (self.user_id, limit)
            )
            return cur.fetchall()
    
    def get_recent_email_activities(self, limit=5):
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT recipient, subject, context, generated_text 
                   FROM email_activities 
                   WHERE user_id = %s
                   ORDER BY timestamp DESC LIMIT %s""",
                (self.user_id, limit)
            )
            return cur.fetchall()
