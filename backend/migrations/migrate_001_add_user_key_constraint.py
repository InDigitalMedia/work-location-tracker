"""
Migration: Add user_key field, unique constraint, and updated_at field.

This migration:
1. Adds user_key column (normalized user identifier)
2. Backfills user_key from existing user_name data
3. Adds unique constraint on (user_key, date)
4. Adds updated_at column
5. Deduplicates any existing (user_key, date) pairs, keeping latest by created_at
"""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


def is_postgres(engine):
    """Check if database is PostgreSQL."""
    return "postgresql" in str(engine.url).lower()


def migrate(engine):
    """Run migration."""
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            if is_postgres(engine):
                migrate_postgres(conn)
            else:
                migrate_sqlite(conn)
            
            trans.commit()
            logger.info("Migration 001 completed successfully")
        except Exception as e:
            trans.rollback()
            logger.error(f"Migration 001 failed: {str(e)}")
            raise


def migrate_postgres(conn):
    """PostgreSQL migration."""
    logger.info("Running PostgreSQL migration...")
    
    # Check if user_key already exists (idempotent)
    try:
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'entry' AND column_name = 'user_key'
        """))
        
        if result.fetchone():
            logger.info("user_key column already exists, skipping migration")
            return
    except Exception:
        # Table might not exist yet (first run), continue
        pass
    
    # Step 1: Add user_key column (nullable initially)
    logger.info("Adding user_key column...")
    conn.execute(text("ALTER TABLE entry ADD COLUMN user_key TEXT"))
    
    # Step 2: Backfill user_key from user_name (normalize: lower(trim))
    logger.info("Backfilling user_key from user_name...")
    conn.execute(text("""
        UPDATE entry 
        SET user_key = lower(trim(user_name))
        WHERE user_key IS NULL
    """))
    
    # Step 3: Deduplicate - keep the row with the highest id for each (user_key, date).
    # (Matches migrate_sqlite's approach below; a created_at-based comparison can leave
    # ties unresolved when duplicates share the same created_at, e.g. from batch inserts.)
    logger.info("Deduplicating entries...")
    conn.execute(text("""
        DELETE FROM entry
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM entry
            WHERE user_key IS NOT NULL AND user_key != ''
            GROUP BY user_key, date
        )
    """))
    
    # Step 4: Set user_key NOT NULL
    logger.info("Setting user_key NOT NULL...")
    conn.execute(text("ALTER TABLE entry ALTER COLUMN user_key SET NOT NULL"))
    
    # Step 5: Add updated_at column (nullable)
    logger.info("Adding updated_at column...")
    conn.execute(text("ALTER TABLE entry ADD COLUMN updated_at TIMESTAMPTZ"))
    
    # Step 6: Create unique constraint
    logger.info("Creating unique constraint on (user_key, date)...")
    conn.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_entries_userkey_date 
        ON entry (user_key, date)
    """))


def migrate_sqlite(conn):
    """SQLite migration (ALTER TABLE limitations)."""
    logger.info("Running SQLite migration...")
    
    # Check if user_key exists
    result = conn.execute(text("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='entry'
    """))
    
    if not result.fetchone():
        logger.info("Entry table does not exist, skipping migration")
        return
    
    # Check if migration already applied
    result = conn.execute(text("PRAGMA table_info(entry)"))
    columns = [row[1] for row in result.fetchall()]
    
    if "user_key" in columns:
        logger.info("user_key column already exists, skipping migration")
        return
    
    # SQLite approach: Add nullable columns, backfill, then create index
    logger.info("Adding user_key column (SQLite)...")
    try:
        conn.execute(text("ALTER TABLE entry ADD COLUMN user_key TEXT"))
    except Exception as e:
        if "duplicate column" not in str(e).lower():
            raise
        logger.info("user_key column already exists")
    
    logger.info("Backfilling user_key from user_name...")
    conn.execute(text("""
        UPDATE entry 
        SET user_key = lower(trim(user_name))
        WHERE user_key IS NULL OR user_key = ''
    """))
    
    logger.info("Adding updated_at column...")
    try:
        conn.execute(text("ALTER TABLE entry ADD COLUMN updated_at TIMESTAMP"))
    except Exception as e:
        if "duplicate column" not in str(e).lower():
            raise
        logger.info("updated_at column already exists")
    
    # Deduplicate before creating constraint (keep latest by created_at)
    logger.info("Deduplicating entries...")
    conn.execute(text("""
        DELETE FROM entry
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM entry
            WHERE user_key IS NOT NULL AND user_key != ''
            GROUP BY user_key, date
        )
    """))
    
    # SQLite: Create unique index (enforces uniqueness)
    logger.info("Creating unique index on (user_key, date)...")
    conn.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_entries_userkey_date 
        ON entry (user_key, date)
    """))


if __name__ == "__main__":
    from db import engine
    migrate(engine)

