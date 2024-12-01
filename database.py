import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from typing import Optional, List, Tuple
import os
import json


class DatabaseManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.schema_name = f"user_{self.user_id}"  # Unique schema name for the user
        self._initialize_pool()
        self.ensure_schema()
        self.create_tables()

    def _initialize_pool(self):
        """Initialize the connection pool"""
        if not hasattr(self, 'pool') or self.pool.closed:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=os.getenv('DATABASE_URL')  # Set DATABASE_URL in your environment
            )

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        self._initialize_pool()  # Ensure pool is available
        conn = None
        try:
            conn = self.pool.getconn()
            with conn.cursor() as cur:
                # Set the search_path to the user's schema for isolation
                cur.execute(f"SET search_path TO {self.schema_name}")
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
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name}")

    def create_tables(self):
        """Create required tables within the user's schema"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        context TEXT,
                        generated_text TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS email_activities (
                        id SERIAL PRIMARY KEY,
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
        """Save a conversation in the user's schema"""
        if isinstance(content, (list, dict)):
            content = json.dumps(content)

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversations (role, content, context, generated_text) 
                    VALUES (%s, %s, %s, %s)
                    """,
                    (role, content, context, generated_text)
                )

    def get_recent_conversations(self, limit: int = 10) -> List[Tuple]:
        """Retrieve recent conversations for the user"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content, context 
                    FROM conversations 
                    ORDER BY timestamp DESC LIMIT %s
                    """,
                    (limit,)
                )
                return cur.fetchall()

    def save_email_activity(self, recipient, subject, context, generated_text):
        """Save an email activity in the user's schema"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO email_activities (recipient, subject, context, generated_text) 
                    VALUES (%s, %s, %s, %s)
                    """,
                    (recipient, subject, context, generated_text)
                )

    def get_recent_email_activities(self, limit=5) -> List[Tuple]:
        """Retrieve recent email activities for the user"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT recipient, subject, context, generated_text 
                    FROM email_activities 
                    ORDER BY timestamp DESC LIMIT %s
                    """,
                    (limit,)
                )
                return cur.fetchall()

    def __del__(self):
        """Cleanup connection pool"""
        if hasattr(self, 'pool'):
            self.pool.closeall()



