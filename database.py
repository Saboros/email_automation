import psycopg2
from psycopg2 import pool
import json
from contextlib import contextmanager
from typing import Optional, List, Tuple
import os

class DatabaseManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        # Create connection pool
        self.pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=os.getenv('DATABASE_URL')
        )

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = self.pool.getconn()
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def check_tables(self):
        """Check if required tables exist and create them if missing"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
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
        """Create conversations table with user_id field"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
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
    
    def create_email_activities_table(self):
        """Create email_activities table with user_id field"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
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
    
    def init_database(self):
        """Initialize database by dropping and recreating tables"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Drop existing tables
                    cur.execute("DROP TABLE IF EXISTS conversations CASCADE")
                    cur.execute("DROP TABLE IF EXISTS email_activities CASCADE")
                    
                    # Create conversations table
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
                    
                    # Create email_activities table
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
        except Exception as e:
            print(f"Error initializing database: {e}")
            raise

    def save_conversation(self, role: str, content: any, 
                         context: Optional[str] = None, 
                         generated_text: Optional[str] = None) -> None:
        if isinstance(content, (list, dict)):
            content = json.dumps(content)

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """INSERT INTO conversations 
                           (user_id, role, content, context, generated_text) 
                           VALUES (%s, %s, %s, %s, %s)""",
                        (self.user_id, role, content, context, generated_text)
                    )
                except psycopg2.Error as e:
                    print(f"Database error: {e}")
                    raise

    def get_recent_conversation(self, limit: int = 10) -> List[Tuple]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """SELECT role, content, context 
                           FROM conversations 
                           WHERE user_id = %s
                           ORDER BY timestamp DESC LIMIT %s""",
                        (self.user_id, limit)
                    )
                    return cur.fetchall()
                except psycopg2.Error as e:
                    print(f"Database error: {e}")
                    return []

    def get_recent_email_activities(self, limit=5):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        "SELECT recipient, subject, context, generated_text FROM email_activities ORDER BY timestamp DESC LIMIT %s",
                        (limit,)
                    )
                    return cur.fetchall()
                except psycopg2.Error as e:
                    print(f"Database error: {e}")
                    return []

    def save_email_activity(self, recipient, subject, context, generated_text):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        "INSERT INTO email_activities (user_id, recipient, subject, context, generated_text) VALUES (%s, %s, %s, %s, %s)",
                        (self.user_id, recipient, subject, context, generated_text)
                    )
                except psycopg2.Error as e:
                    print(f"Database error: {e}")
                    raise
    
    def execute_query(self, query):
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    results = cur.fetchall()
                    return results
        except psycopg2.Error as e:
            print(f"Database error: {e}")
            return []

    def __del__(self):
        """Cleanup connection pool"""
        if hasattr(self, 'pool'):
            self.pool.closeall()
