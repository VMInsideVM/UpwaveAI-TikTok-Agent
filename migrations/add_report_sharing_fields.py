#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database migration: Add report sharing fields
Run this script to upgrade the database structure on VPS
"""

import sqlite3
import os


def migrate_database(db_path="chatbot.db"):
    """
    Add sharing functionality fields to reports table

    Args:
        db_path: Database file path, default is chatbot.db

    New fields:
    - share_mode: Sharing mode (private/public/password)
    - share_password: Sharing password
    - share_expires_at: Sharing expiration time
    - share_created_at: Sharing creation time
    """
    print("Starting database migration: {}".format(db_path))

    if not os.path.exists(db_path):
        print("ERROR: Database file not found: {}".format(db_path))
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if reports table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='reports'
        """)

        if not cursor.fetchone():
            print("ERROR: reports table does not exist")
            conn.close()
            return False

        # Check existing columns
        cursor.execute("PRAGMA table_info(reports)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        print("Current reports table columns: {}".format(existing_columns))

        # Fields to add
        new_columns = {
            'share_mode': "VARCHAR(20) DEFAULT 'private' NOT NULL",
            'share_password': "VARCHAR(128)",
            'share_expires_at': "DATETIME",
            'share_created_at': "DATETIME"
        }

        added_count = 0

        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                print("Adding field: {} ({})".format(column_name, column_type))

                cursor.execute("""
                    ALTER TABLE reports
                    ADD COLUMN {} {}
                """.format(column_name, column_type))

                added_count += 1
            else:
                print("Field already exists, skipping: {}".format(column_name))

        # Create indexes for new fields
        if 'share_mode' not in existing_columns:
            print("Creating share_mode index...")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reports_share_mode
                ON reports(share_mode)
            """)

        if 'share_expires_at' not in existing_columns:
            print("Creating share_expires_at index...")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reports_share_expires_at
                ON reports(share_expires_at)
            """)

        # Commit changes
        conn.commit()
        conn.close()

        print("Migration completed! Added {} fields".format(added_count))

        return True

    except Exception as e:
        print("Migration failed: {}".format(e))
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


def verify_migration(db_path="chatbot.db"):
    """Verify migration success"""
    print("\nVerifying migration results...")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(reports)")
        columns = cursor.fetchall()

        required_fields = ['share_mode', 'share_password', 'share_expires_at', 'share_created_at']
        found_fields = [col[1] for col in columns if col[1] in required_fields]

        print("Sharing functionality fields: {}".format(found_fields))

        if len(found_fields) == len(required_fields):
            print("SUCCESS: All fields have been added correctly!")

            # Show a sample record
            cursor.execute("SELECT report_id, share_mode FROM reports LIMIT 1")
            sample = cursor.fetchone()
            if sample:
                print("Sample record: report_id={}, share_mode={}".format(sample[0], sample[1]))
        else:
            missing = set(required_fields) - set(found_fields)
            print("WARNING: Missing fields: {}".format(missing))

        conn.close()
        return len(found_fields) == len(required_fields)

    except Exception as e:
        print("Verification failed: {}".format(e))
        return False


if __name__ == "__main__":
    import sys

    # Get database path from command line args, default to chatbot.db
    db_path = sys.argv[1] if len(sys.argv) > 1 else "chatbot.db"

    print("=" * 60)
    print("Database Migration: Add Report Sharing Functionality")
    print("=" * 60)
    print()

    # Execute migration
    success = migrate_database(db_path)

    if success:
        # Verify migration
        verify_migration(db_path)

        print()
        print("=" * 60)
        print("Migration completed! You can now restart the service")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("Migration failed, please check the error messages")
        print("=" * 60)
        sys.exit(1)
