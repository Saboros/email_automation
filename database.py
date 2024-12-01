import psycopg2
from psycopg2 import pool
import json
from contextlib import contextmanager
from typing import Optional, List, Tuple
import os


class DatabaseManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.schema_name = f"user_{self.user_id.replace('-', '_')}"  # Replace invalid characters
        self._initialize_pool()
        self.ensure_schema()
        self.init_database()  # Initialize the database tables for the schema

    def _initialize_pool(self):
        """Initialize the connection pool"""
        if not hasattr(self, 'pool') or self.pool.closed:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=os.getenv('DATABASE_URL')
            )

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        self._initialize_pool()  # Ensure pool is available
        conn = None
        try:
            conn = self.pool.getconn()
            with conn.cursor() as cur:
                # Set the schema for this connection
                cur.execute(f'SET search_path TO "{self.schema_name}"')
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.commit()
                self.pool.putconn(conn)

    def ensure_schema(self):
        """Create schema for the user if it doesn't exist"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Use double quotes around schema name for safety
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema_name}"')

    def init_database(self):
        """Initialize tables in the user's schema"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Create the conversations table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        context TEXT,
                        generated_text TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Create the email_activities table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS email_activities (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        recipient TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        context TEXT,
                        generated_text TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

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

    def __del__(self):
        """Cleanup connection pool"""
        if hasattr(self, 'pool'):
            self.pool.closeall()
