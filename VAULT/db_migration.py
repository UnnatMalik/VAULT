import sqlite3
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_database(db_path: str) -> None:
    """
    Migrate the database to the latest schema.
    
    Args:
        db_path: Path to the SQLite database file
    """
    if not os.path.exists(db_path):
        logger.info(f"Database file {db_path} does not exist, creating new database")
        _create_new_database(db_path)
        return
    
    logger.info(f"Migrating database at {db_path}")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Remove blockchain table if it exists
            cursor.execute("DROP TABLE IF EXISTS blockchain")
            
            # Create content_analysis table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS content_analysis (
                    file_path TEXT PRIMARY KEY,
                    content_type TEXT,
                    sensitive_info TEXT,
                    keywords TEXT,
                    entities TEXT,
                    checksum TEXT,
                    metadata TEXT,
                    last_analyzed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add any other necessary tables or migrations here
            
            conn.commit()
            logger.info("Database migration completed successfully")
            
    except Exception as e:
        logger.error(f"Error during database migration: {e}")
        raise

def _create_new_database(db_path: str) -> None:
    """Create a new database with the latest schema."""
    try:
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Create content_analysis table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS content_analysis (
                    file_path TEXT PRIMARY KEY,
                    content_type TEXT,
                    sensitive_info TEXT,
                    keywords TEXT,
                    entities TEXT,
                    checksum TEXT,
                    metadata TEXT,
                    last_analyzed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create any other necessary tables here
            
            conn.commit()
            logger.info(f"Created new database at {db_path}")
            
    except Exception as e:
        logger.error(f"Error creating new database: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate the VAULT database to the latest schema.')
    parser.add_argument('--db-path', type=str, default='deleted_manifest.db',
                        help='Path to the SQLite database file')
    
    args = parser.parse_args()
    migrate_database(args.db_path)
