"""
Database utilities for congressional coalition tracking.
"""

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self, database_url: Optional[str] = None):
        # Use the congressional user that was previously set up
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable must be set. Example: mysql://user:password@localhost/database")
        self.engine = None
        self.SessionLocal = None
        self._setup_engine()
    
    def _setup_engine(self):
        """Set up the SQLAlchemy engine with appropriate configuration."""
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    @contextmanager
    def get_session(self) -> Session:
        """Get a database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_table_count(self, table_name: str) -> int:
        """Get the number of records in a table."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                return result.scalar()
        except Exception as e:
            logger.error(f"Failed to get count for table {table_name}: {e}")
            return 0
    
    def execute_raw_sql(self, sql: str, params: Optional[dict] = None):
        """Execute raw SQL with optional parameters."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                return result
        except Exception as e:
            logger.error(f"Failed to execute SQL: {e}")
            raise

# Global database manager instance
db_manager = DatabaseManager()

def get_db_session():
    """Get a database session using the global manager."""
    return db_manager.get_session()

def get_db_engine():
    """Get the database engine."""
    return db_manager.engine


