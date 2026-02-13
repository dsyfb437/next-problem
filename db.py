"""
Database abstraction layer for the intelligent question system.

Supports both SQLite (development) and PostgreSQL (production).
Uses environment variable DATABASE_URL to determine the database type.
"""

import os
import sqlite3
from typing import Optional, Dict, List, Tuple
from datetime import datetime

# psycopg2 is optional (for PostgreSQL production)
try:
    import psycopg2
    from psycopg2 import sql
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


def get_db_connection():
    """
    Get a database connection based on DATABASE_URL environment variable.

    Returns:
        Database connection object (sqlite3 or psycopg2 connection)

    Raises:
        ValueError: If DATABASE_URL is not set
    """
    db_url = os.environ.get('DATABASE_URL')

    if db_url and db_url.startswith('postgres'):
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("PostgreSQL URL provided but psycopg2 is not installed. "
                          "Add 'psycopg2-binary' to requirements.txt.")
        # PostgreSQL connection
        conn = psycopg2.connect(db_url, sslmode='require')
        conn.autocommit = True
        return conn
    else:
        # SQLite connection (default for development)
        db_path = os.environ.get('SQLITE_PATH', 'data.db')
        return sqlite3.connect(db_path)


def init_db():
    """Initialize database tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    table_sql = """
    CREATE TABLE IF NOT EXISTS interactions (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(255) NOT NULL,
        question_id VARCHAR(255) NOT NULL,
        is_correct BOOLEAN NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    if PSYCOPG2_AVAILABLE and isinstance(conn, psycopg2.extensions.connection):
        cursor.execute(sql.SQL(table_sql))
    else:
        cursor.execute(table_sql.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT'))

    conn.commit()
    cursor.close()
    conn.close()


def record_interaction(user_id: str, question_id: str, is_correct: bool,
                        timestamp: Optional[str] = None) -> bool:
    """
    Record a user interaction with a question.

    Args:
        user_id: User identifier
        question_id: Question identifier
        is_correct: Whether the answer was correct
        timestamp: ISO format timestamp string (uses current time if None)

    Returns:
        True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if timestamp is None:
            timestamp = datetime.now().isoformat()

        query = 'INSERT INTO interactions (user_id, question_id, is_correct, timestamp) VALUES (?, ?, ?, ?)'
        if PSYCOPG2_AVAILABLE and isinstance(conn, psycopg2.extensions.connection):
            query = 'INSERT INTO interactions (user_id, question_id, is_correct, timestamp) VALUES (%s, %s, %s, %s)'

        cursor.execute(query, (user_id, question_id, 1 if is_correct else 0, timestamp))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error recording interaction: {e}")
        return False


def get_user_interactions(user_id: str, limit: Optional[int] = None) -> List[Dict]:
    """
    Get interaction history for a specific user.

    Args:
        user_id: User identifier
        limit: Maximum number of records to return (None for all)

    Returns:
        List of interaction dictionaries
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM interactions WHERE user_id = ? ORDER BY timestamp DESC'
        params = [user_id]

        if PSYCOPG2_AVAILABLE and isinstance(conn, psycopg2.extensions.connection):
            query = 'SELECT * FROM interactions WHERE user_id = %s ORDER BY timestamp DESC'

        if limit:
            query += ' LIMIT ?'
            if PSYCOPG2_AVAILABLE and isinstance(conn, psycopg2.extensions.connection):
                query = query.replace('LIMIT ?', 'LIMIT %s')
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, row)) for row in rows]

        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Error getting user interactions: {e}")
        return []


def get_wrong_questions(user_id: str) -> List[str]:
    """
    Get list of question IDs that the user answered incorrectly.

    Args:
        user_id: User identifier

    Returns:
        List of question IDs
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        placeholder = '?'
        query = f'SELECT DISTINCT question_id FROM interactions WHERE user_id = ? AND is_correct = 0'

        if PSYCOPG2_AVAILABLE and isinstance(conn, psycopg2.extensions.connection):
            placeholder = '%s'
            query = 'SELECT DISTINCT question_id FROM interactions WHERE user_id = %s AND is_correct = 0'

        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row[0] for row in rows]
    except Exception as e:
        print(f"Error getting wrong questions: {e}")
        return []


def get_statistics() -> Dict:
    """
    Get overall statistics about the system.

    Returns:
        Dictionary containing total_users, total_interactions, correct_rate
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(DISTINCT user_id) FROM interactions')
        total_users = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*), SUM(is_correct) FROM interactions')
        total, correct = cursor.fetchone()

        cursor.close()
        conn.close()

        return {
            'total_users': total_users or 0,
            'total_interactions': total or 0,
            'correct_rate': (correct / total) if total > 0 else 0
        }
    except Exception as e:
        print(f"Error getting statistics: {e}")
        return {'total_users': 0, 'total_interactions': 0, 'correct_rate': 0}
