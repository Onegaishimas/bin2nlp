"""
Database connection management for PostgreSQL.
"""

import asyncio
from typing import Optional
import databases
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from ..core.config import Settings, get_settings
from ..core.logging import get_logger

# Global database connection
_database: Optional[databases.Database] = None
_engine: Optional[AsyncEngine] = None

logger = get_logger(__name__)


def get_database_url(settings: Optional[Settings] = None) -> str:
    """
    Build PostgreSQL database URL from settings.
    
    Args:
        settings: Application settings
        
    Returns:
        Database URL string
    """
    if settings is None:
        settings = get_settings()
    
    # Get database configuration from environment
    db_host = settings.database.host
    db_port = settings.database.port
    db_name = settings.database.name
    db_user = settings.database.user
    db_password = settings.database.password
    
    # Build connection URL
    if db_password:
        return f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        return f"postgresql+asyncpg://{db_user}@{db_host}:{db_port}/{db_name}"


async def init_database(settings: Optional[Settings] = None) -> databases.Database:
    """
    Initialize database connection and create tables if needed.
    
    Args:
        settings: Application settings
        
    Returns:
        Database connection instance
    """
    global _database, _engine
    
    if _database is not None:
        return _database
    
    settings = settings or get_settings()
    database_url = get_database_url(settings)
    
    try:
        # Create async engine for SQLAlchemy operations
        _engine = create_async_engine(
            database_url,
            echo=getattr(settings, 'database_echo', False),
            pool_size=getattr(settings, 'database_pool_size', 10),
            max_overflow=getattr(settings, 'database_max_overflow', 20),
            pool_timeout=getattr(settings, 'database_pool_timeout', 30),
            pool_recycle=getattr(settings, 'database_pool_recycle', 3600)
        )
        
        # Create databases connection for raw SQL operations  
        _database = databases.Database(database_url)
        await _database.connect()
        
        logger.info(
            "Database connection established",
            extra={
                "database_url": database_url.split('@')[-1],  # Hide credentials
                "pool_size": getattr(settings, 'database_pool_size', 10)
            }
        )
        
        return _database
        
    except Exception as e:
        logger.error(
            "Failed to initialize database connection",
            extra={"error": str(e), "database_url": database_url.split('@')[-1]}
        )
        raise


async def get_database() -> databases.Database:
    """
    Get the global database connection.
    
    Returns:
        Database connection instance
        
    Raises:
        RuntimeError: If database not initialized
    """
    if _database is None:
        await init_database()
    
    if _database is None:
        raise RuntimeError("Database not initialized")
    
    return _database


async def get_engine() -> AsyncEngine:
    """
    Get the SQLAlchemy async engine.
    
    Returns:
        SQLAlchemy AsyncEngine
        
    Raises:
        RuntimeError: If engine not initialized
    """
    if _engine is None:
        await init_database()
    
    if _engine is None:
        raise RuntimeError("Database engine not initialized")
    
    return _engine


async def close_database() -> None:
    """Close database connections."""
    global _database, _engine
    
    if _database:
        await _database.disconnect()
        _database = None
        logger.info("Database connection closed")
    
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed")


async def health_check() -> bool:
    """
    Check database connection health.
    
    Returns:
        True if healthy, False otherwise
    """
    try:
        db = await get_database()
        
        # Simple query to check connection
        result = await db.fetch_one("SELECT 1 as health_check")
        
        return result is not None and result['health_check'] == 1
        
    except Exception as e:
        logger.warning(
            "Database health check failed",
            extra={"error": str(e)}
        )
        return False


async def execute_schema_file(schema_file_path: str) -> None:
    """
    Execute SQL schema file to create tables and functions.
    
    Args:
        schema_file_path: Path to SQL schema file
    """
    try:
        db = await get_database()
        
        # Read schema file
        with open(schema_file_path, 'r') as f:
            schema_sql = f.read()
        
        # Split into individual statements and execute
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        for statement in statements:
            if statement:
                await db.execute(statement)
        
        logger.info(
            "Schema executed successfully",
            extra={"schema_file": schema_file_path, "statements": len(statements)}
        )
        
    except Exception as e:
        logger.error(
            "Failed to execute schema",
            extra={"schema_file": schema_file_path, "error": str(e)}
        )
        raise


# Context manager for database transactions
class DatabaseTransaction:
    """Context manager for database transactions."""
    
    def __init__(self, database: Optional[databases.Database] = None):
        self.database = database
        self.transaction = None
    
    async def __aenter__(self):
        if self.database is None:
            self.database = await get_database()
        
        self.transaction = await self.database.transaction().__aenter__()
        return self.database
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.transaction:
            await self.transaction.__aexit__(exc_type, exc_val, exc_tb)


# Helper function for safe database queries
async def safe_execute(query: str, values: dict = None, fetch_one: bool = False, fetch_all: bool = False):
    """
    Safely execute database query with error handling.
    
    Args:
        query: SQL query string
        values: Query parameters
        fetch_one: Return single result
        fetch_all: Return all results
        
    Returns:
        Query result or None on error
    """
    try:
        db = await get_database()
        
        if fetch_one:
            return await db.fetch_one(query, values)
        elif fetch_all:
            return await db.fetch_all(query, values)
        else:
            return await db.execute(query, values)
            
    except Exception as e:
        logger.error(
            "Database query failed",
            extra={"query": query[:100] + "..." if len(query) > 100 else query, "error": str(e)}
        )
        return None