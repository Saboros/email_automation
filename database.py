import psycopg2
from datetime import datetime
import json
import os

class DatabaseManager:
    def __init__(self):
        self.conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        self.check_tables()
        
    def check_tables(self):
        """Check if required tables exist and create them if missing"""
        with self.conn.cursor() as cur:
            # Check if tables exist
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            existing_tables = {table[0] for table in cur.fetchall()}
            
            if 'conversations' not in existing_tables:
                self.create_conversations_table()
            if 'email_activities' not in existing_tables:
                self.create_email_activities_table()
    
    def create_conversations_table(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE conversations (
                    id SERIAL PRIMARY KEY,
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
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    context TEXT,
                    generated_text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()
            
    def init_database(self):
        """Initialize database by dropping and recreating all tables"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS conversations CASCADE")
                cur.execute("DROP TABLE IF EXISTS email_activities CASCADE")
                self.create_conversations_table()
                self.create_email_activities_table()
        except psycopg2.Error as e:
            print(f"Error initializing database: {e}")
            raise

    def save_conversation(self, role, content, context=None, generated_text=None):
        if isinstance(content, (list, dict)):
            content = json.dumps(content)

        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (role, content, context, generated_text) VALUES (%s, %s, %s, %s)",
                (role, content, context, generated_text)
            )
            self.conn.commit()
        
    def get_recent_conversation(self, limit=10):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, context FROM conversations ORDER BY timestamp DESC LIMIT %s",
                (limit,)
            )
            return cur.fetchall()
    
    def get_recent_email_activities(self, limit=5):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT recipient, subject, context, generated_text FROM email_activities ORDER BY timestamp DESC LIMIT %s",
                (limit,)
            )
            return cur.fetchall()
    
    def save_email_activity(self, recipient, subject, context, generated_text):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO email_activities (recipient, subject, context, generated_text) VALUES (%s, %s, %s, %s)",
                (recipient, subject, context, generated_text)
            )
            self.conn.commit()
    
    def execute_query(self, query):
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()
                return results
        except psycopg2.Error as e:
            print(f"Database error: {e}")
            return []

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
