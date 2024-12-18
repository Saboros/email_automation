import psycopg2
from psycopg2 import pool
import json
from contextlib import contextmanager
from typing import Optional, List, Tuple
import os
import time



#Json schema separates the users session database when logged in.
#login function soon.
class DatabaseManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._initialize_pool()
        self.schema_name = f"user_{self.user_id.replace('-', '_')}"

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
        self._initialize_pool() 
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

    def get_email_metrics(self):
        """Get email sending metrics"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get total emails
                cur.execute(f"""
                    SELECT 
                        COUNT(*) as total_emails,
                        COUNT(DISTINCT recipient) as unique_recipients,
                        COUNT(DISTINCT DATE(timestamp)) as active_days,
                        MAX(timestamp) as last_sent
                    FROM {self.schema_name}.email_activities
                    WHERE user_id = %s
                """, (self.user_id,))
                return cur.fetchone()
        
    def get_daily_email_counts(self):
        """Get daily email sending counts"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                        SELECT
                            DATE(timestamp) as date,
                            COUNT(*) as count
                        FROM {self.schema_name}.email_activities
                        WHERE user_id = %s
                        GROUP BY DATE(timestamp)
                        ORDER BY date DESC
                        LIMIT 30
                """, (self.user_id,))
                return cur.fetchall()

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
                        email_body TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
    
    def create_user_schema(self):
        """Create a schema for the user if it doesn't exist with proper error handling"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            with self.get_connection() as conn:
                # Start a transaction
                conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
                
                with conn.cursor() as cur:
                    try:
                        # Try to acquire an advisory lock
                        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (self.schema_name,))
                        
                        # Check if schema exists
                        cur.execute("""
                            SELECT schema_name 
                            FROM information_schema.schemata 
                            WHERE schema_name = %s
                        """, (self.schema_name,))
                        
                        if not cur.fetchone():
                            # Create schema if not exists
                            cur.execute(f"""
                                CREATE SCHEMA IF NOT EXISTS {self.schema_name};
                                GRANT USAGE ON SCHEMA {self.schema_name} TO PUBLIC;
                                ALTER DEFAULT PRIVILEGES IN SCHEMA {self.schema_name} 
                                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO PUBLIC;
                            """)
                        return True
                        
                    except psycopg2.Error as e:
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        print(f"Schema creation error: {e}")
                        raise

    def init_database(self):
        """Initialize database with user schema and tables"""
        try:
            self.create_user_schema()
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                        DROP TABLE IF EXISTS {self.schema_name}.conversations CASCADE;
                        DROP TABLE IF EXISTS {self.schema_name}.email_activities CASCADE;
                        
                        CREATE TABLE {self.schema_name}.conversations (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            role TEXT NOT NULL,
                            content TEXT NOT NULL,
                            context TEXT,
                            generated_text TEXT,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );

                        CREATE TABLE {self.schema_name}.email_activities (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            recipient TEXT NOT NULL,
                            subject TEXT NOT NULL,
                            context TEXT,
                            email_body TEXT,
                            generated_text TEXT,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );

                        CREATE TABLE IF NOT EXISTS {self.schema_name}.token_usage (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            tokens_used INTEGER NOT NULL,
                            operation_type TEXT NOT NULL,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    conn.commit()
        except Exception as e:
            print(f"Schema creation error: {e}")
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
        """Get recent email activities with improved error handling and logging"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT schema_name 
                        FROM information_schema.schemata 
                        WHERE schema_name = %s
                    """, (self.schema_name,))
                    
                    if not cur.fetchone():
                        print(f"Schema {self.schema_name} does not exist")
                        self.create_user_schema() 
                    
                    # Check if table exists
                    cur.execute(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = %s 
                            AND table_name = 'email_activities'
                        )
                    """, (self.schema_name,))
                    
                    if not cur.fetchone()[0]:
                        print(f"Table email_activities does not exist in schema {self.schema_name}")
                        return []

                    # Query with better error handling
                    try:
                        cur.execute(f"""
                            SELECT recipient, subject, context, email_body, generated_text, timestamp
                            FROM {self.schema_name}.email_activities 
                            WHERE user_id = %s
                            ORDER BY timestamp DESC 
                            LIMIT %s
                        """, (self.user_id, limit))
                        
                        results = cur.fetchall()
                        if not results:
                            print(f"No email activities found for user {self.user_id}")
                        return results
                        
                    except psycopg2.Error as e:
                        print(f"Query error: {e.pgerror}")
                        return []
                    
        except Exception as e:
            print(f"Database connection error: {str(e)}")
            return []

    def save_email_activity(self, recipient, subject, context, email_body):
        """Save email activity to the database with better error handling"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # First ensure schema exists
                    cur.execute("""
                        SELECT schema_name 
                        FROM information_schema.schemata 
                        WHERE schema_name = %s
                    """, (self.schema_name,))
                    
                    if not cur.fetchone():
                        self.create_user_schema()
                    
                    # Insert the email activity
                    cur.execute(f"""
                        INSERT INTO {self.schema_name}.email_activities 
                        (user_id, recipient, subject, context, email_body)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (self.user_id, recipient, subject, context, email_body))
                    
                    inserted_id = cur.fetchone()[0]
                    conn.commit()
                    print(f"Successfully saved email activity with ID: {inserted_id}")
                    return inserted_id
        except Exception as e:
            print(f"Error saving email activity: {str(e)}")
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

    def create_token_tracking_table(self):
        """Create token tracking table"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema_name}.token_usage (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        tokens_used INTEGER NOT NULL,
                        operation_type TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

    def save_token_usage(self, tokens_used: int, operation_type: str):
        """Save token usage data"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.schema_name}.token_usage 
                    (user_id, tokens_used, operation_type)
                    VALUES (%s, %s, %s)
                """, (self.user_id, tokens_used, operation_type))

    def get_token_metrics(self):
        """Get token usage metrics"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT 
                        SUM(tokens_used) as total_tokens,
                        AVG(tokens_used) as avg_tokens,
                        COUNT(*) as total_operations,
                        MAX(timestamp) as last_operation
                    FROM {self.schema_name}.token_usage
                    WHERE user_id = %s
                """, (self.user_id,))
                return cur.fetchone()

    def get_daily_token_usage(self, days: int = 30):
        """Get daily token usage"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT 
                        DATE(timestamp) as date,
                        SUM(tokens_used) as tokens,
                        COUNT(*) as operations
                    FROM {self.schema_name}.token_usage
                    WHERE user_id = %s
                    AND timestamp >= NOW() - INTERVAL '%s days'
                    GROUP BY DATE(timestamp)
                    ORDER BY date DESC
                """, (self.user_id, days))
                return cur.fetchall()
