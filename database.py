import psycopg2
from psycopg2 import pool
import json
from contextlib import contextmanager
from typing import Optional, List, Tuple
import os

class DatabaseManager:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.schema_name = f"session_{session_id.replace('-', '_')}"
        self._initialize_pool()

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
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.commit()
                self.pool.putconn(conn)

    def close_pool(self):
        """Explicitly close the connection pool"""
        if hasattr(self, 'pool') and not self.pool.closed:
            self.pool.closeall()

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
    
    def create_user_schema(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    # Drop existing schema if exists for clean slate
                    cur.execute(f"""
                        DROP SCHEMA IF EXISTS {self.schema_name} CASCADE;
                        CREATE SCHEMA {self.schema_name};
                        -- Restrict access to only the current database user
                        REVOKE ALL ON SCHEMA {self.schema_name} FROM PUBLIC;
                        GRANT USAGE ON SCHEMA {self.schema_name} TO database_q6g3_user;
                        -- Set restrictive default privileges
                        ALTER DEFAULT PRIVILEGES IN SCHEMA {self.schema_name}
                        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES 
                        TO database_q6g3_user;
                    """)
                    conn.commit()
                except psycopg2.Error as e:
                    print(f"Schema creation error: {e}")
                    raise

    def init_database(self):
        try:
            self.create_user_schema()
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Create tables in visitor's schema with all required columns
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.schema_name}.conversations (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            role TEXT NOT NULL,
                            content TEXT NOT NULL,
                            context TEXT,
                            generated_text TEXT,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );

                        CREATE TABLE IF NOT EXISTS {self.schema_name}.email_activities (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            recipient TEXT NOT NULL,
                            subject TEXT NOT NULL,
                            context TEXT,
                            generated_text TEXT,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    conn.commit()
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
                        f"""INSERT INTO {self.schema_name}.conversations 
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
                        f"""SELECT role, content, context 
                           FROM {self.schema_name}.conversations 
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
                    # Only query current user's schema
                    cur.execute(f"""
                        SELECT recipient, subject, context, generated_text 
                        FROM {self.schema_name}.email_activities 
                        WHERE user_id = %s
                        ORDER BY timestamp DESC LIMIT %s
                    """, (self.user_id, limit))
                    return cur.fetchall()
                except psycopg2.Error as e:
                    print(f"Database error: {e}")
                    return []

    def save_email_activity(self, recipient, subject, context, generated_text):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        f"""INSERT INTO {self.schema_name}.email_activities 
                           (user_id, recipient, subject, context, generated_text) 
                           VALUES (%s, %s, %s, %s, %s)""",
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

    def cleanup_old_schemas(self, hours_old=24):
        """Cleanup schemas older than specified hours"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("""
                        SELECT schema_name 
                        FROM information_schema.schemata 
                        WHERE schema_name LIKE 'visitor_%'
                        AND schema_name NOT IN (
                            SELECT DISTINCT schemaname 
                            FROM pg_stat_activity 
                            WHERE query_start > NOW() - interval '%s hours'
                        )
                    """, (hours_old,))
                    old_schemas = cur.fetchall()
                    for schema in old_schemas:
                        cur.execute(f"DROP SCHEMA IF EXISTS {schema[0]} CASCADE")
                    conn.commit()
                except psycopg2.Error as e:
                    print(f"Cleanup error: {e}")
                    raise

    def __del__(self):
        """Cleanup connection pool"""
        if hasattr(self, 'pool'):
            self.pool.closeall()

    def create_session_schema(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    CREATE SCHEMA IF NOT EXISTS {self.schema_name};
                    REVOKE ALL ON SCHEMA {self.schema_name} FROM PUBLIC;
                    GRANT USAGE ON SCHEMA {self.schema_name} TO database_q6g3_user;
                """)

    def init_session_tables(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema_name}.conversations (
                        id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS {self.schema_name}.email_activities (
                        id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        recipient TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        context TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
