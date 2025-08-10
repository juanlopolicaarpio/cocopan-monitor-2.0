#!/usr/bin/env python3
"""
CocoPan Monitor Fix Script
Applies fixes for database errors and container restart issues
"""
import os
import shutil
import subprocess
import time
from datetime import datetime

def create_backup():
    """Create backup of current files"""
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    files_to_backup = [
        'database.py',
        'monitor_service.py', 
        'docker-compose.yml'
    ]
    
    for file in files_to_backup:
        if os.path.exists(file):
            shutil.copy2(file, backup_dir)
            print(f"✅ Backed up {file}")
    
    print(f"📦 Backup created in: {backup_dir}")
    return backup_dir

def apply_database_fix():
    """Apply the fixed database module"""
    print("🔧 Applying database fixes...")
    
    fixed_database_content = '''#!/usr/bin/env python3
"""
Fixed CocoPan Database Module
Resolves boolean handling and exception issues
"""
import os
import time
import logging
from contextlib import contextmanager
from typing import List, Tuple, Optional, Dict, Any
import psycopg2
import sqlite3
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import pandas as pd
from config import config

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.connection_pool = None
        self.db_type = "sqlite" if config.USE_SQLITE else "postgresql"
        self._initialize_database()
    
    def _initialize_database(self):
        if self.db_type == "postgresql":
            self._init_postgresql()
        else:
            self._init_sqlite()
        self._create_tables()
        logger.info(f"✅ Database initialized ({self.db_type})")
    
    def _init_postgresql(self):
        try:
            db_url = config.DATABASE_URL
            if db_url.startswith('postgresql://'):
                self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1, maxconn=20, dsn=db_url, cursor_factory=RealDictCursor
                )
                logger.info("✅ PostgreSQL connection pool created")
            else:
                raise ValueError("Invalid PostgreSQL URL format")
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            logger.info("📝 Falling back to SQLite")
            self.db_type = "sqlite"
            self._init_sqlite()
    
    def _init_sqlite(self):
        self.sqlite_path = config.SQLITE_PATH
        try:
            conn = sqlite3.connect(self.sqlite_path)
            conn.close()
            logger.info(f"✅ SQLite database: {self.sqlite_path}")
        except Exception as e:
            logger.error(f"❌ SQLite connection failed: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        if self.db_type == "postgresql":
            conn = None
            try:
                conn = self.connection_pool.getconn()
                yield conn
            except Exception as e:
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                logger.error(f"PostgreSQL error: {str(e)}")
                raise e
            finally:
                if conn:
                    try:
                        self.connection_pool.putconn(conn)
                    except:
                        pass
        else:
            conn = None
            try:
                conn = sqlite3.connect(self.sqlite_path, timeout=30)
                conn.row_factory = sqlite3.Row
                yield conn
            except Exception as e:
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                logger.error(f"SQLite error: {str(e)}")
                raise e
            finally:
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
    
    def _create_tables(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if self.db_type == "postgresql":
                cursor.execute(\'\'\'
                    CREATE TABLE IF NOT EXISTS stores (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        url TEXT NOT NULL UNIQUE,
                        platform VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                \'\'\')
                
                cursor.execute(\'\'\'
                    CREATE TABLE IF NOT EXISTS status_checks (
                        id SERIAL PRIMARY KEY,
                        store_id INTEGER REFERENCES stores(id),
                        is_online BOOLEAN NOT NULL,
                        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        response_time_ms INTEGER,
                        error_message TEXT
                    )
                \'\'\')
                
                cursor.execute(\'\'\'
                    CREATE TABLE IF NOT EXISTS summary_reports (
                        id SERIAL PRIMARY KEY,
                        total_stores INTEGER NOT NULL,
                        online_stores INTEGER NOT NULL,
                        offline_stores INTEGER NOT NULL,
                        online_percentage REAL NOT NULL,
                        report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                \'\'\')
            else:
                cursor.execute(\'\'\'
                    CREATE TABLE IF NOT EXISTS stores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL UNIQUE,
                        platform TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                \'\'\')
                
                cursor.execute(\'\'\'
                    CREATE TABLE IF NOT EXISTS status_checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        store_id INTEGER,
                        is_online BOOLEAN NOT NULL,
                        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        response_time_ms INTEGER,
                        error_message TEXT,
                        FOREIGN KEY (store_id) REFERENCES stores (id)
                    )
                \'\'\')
                
                cursor.execute(\'\'\'
                    CREATE TABLE IF NOT EXISTS summary_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        total_stores INTEGER NOT NULL,
                        online_stores INTEGER NOT NULL,
                        offline_stores INTEGER NOT NULL,
                        online_percentage REAL NOT NULL,
                        report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                \'\'\')
            
            conn.commit()
    
    def get_or_create_store(self, name: str, url: str) -> int:
        """Get or create store with proper error handling"""
        platform = "foodpanda" if "foodpanda.ph" in url else "grabfood"
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.db_type == "postgresql":
                    # Check existing store
                    cursor.execute("SELECT id FROM stores WHERE url = %s", (url,))
                    result = cursor.fetchone()
                    
                    if result:
                        return result[0]
                    
                    # Create new store
                    cursor.execute(
                        "INSERT INTO stores (name, url, platform) VALUES (%s, %s, %s) RETURNING id",
                        (name, url, platform)
                    )
                    store_id = cursor.fetchone()[0]
                else:
                    # SQLite version
                    cursor.execute("SELECT id FROM stores WHERE url = ?", (url,))
                    result = cursor.fetchone()
                    
                    if result:
                        return result["id"]
                    
                    cursor.execute(
                        "INSERT INTO stores (name, url, platform) VALUES (?, ?, ?)",
                        (name, url, platform)
                    )
                    store_id = cursor.lastrowid
                
                conn.commit()
                return store_id
                
        except Exception as e:
            logger.error(f"Failed to get_or_create_store for {name}: {str(e)}")
            raise
    
    def save_status_check(self, store_id: int, is_online: bool, 
                         response_time_ms: Optional[int] = None, 
                         error_message: Optional[str] = None) -> bool:
        """Save status check with proper boolean and error handling"""
        try:
            # Ensure boolean conversion for PostgreSQL
            is_online_value = bool(is_online)
            
            # Ensure response_time is properly handled
            if response_time_ms is not None:
                response_time_ms = int(response_time_ms)
            
            # Truncate error message if too long
            if error_message and len(error_message) > 500:
                error_message = error_message[:500] + "..."
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.db_type == "postgresql":
                    cursor.execute(\'\'\'
                        INSERT INTO status_checks (store_id, is_online, response_time_ms, error_message)
                        VALUES (%s, %s, %s, %s)
                    \'\'\', (store_id, is_online_value, response_time_ms, error_message))
                else:
                    cursor.execute(\'\'\'
                        INSERT INTO status_checks (store_id, is_online, response_time_ms, error_message)
                        VALUES (?, ?, ?, ?)
                    \'\'\', (store_id, is_online_value, response_time_ms, error_message))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save status check for store_id {store_id}: {str(e)}")
            logger.error(f"  Parameters: is_online={is_online}, response_time={response_time_ms}, error=\'{error_message}\'")
            return False
    
    def save_summary_report(self, total_stores: int, online_stores: int, offline_stores: int) -> bool:
        """Save summary report with proper error handling"""
        try:
            online_percentage = (online_stores / total_stores * 100) if total_stores > 0 else 0
            
            # Ensure all values are proper integers/floats
            total_stores = int(total_stores)
            online_stores = int(online_stores)
            offline_stores = int(offline_stores)
            online_percentage = float(online_percentage)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.db_type == "postgresql":
                    cursor.execute(\'\'\'
                        INSERT INTO summary_reports (total_stores, online_stores, offline_stores, online_percentage)
                        VALUES (%s, %s, %s, %s)
                    \'\'\', (total_stores, online_stores, offline_stores, online_percentage))
                else:
                    cursor.execute(\'\'\'
                        INSERT INTO summary_reports (total_stores, online_stores, offline_stores, online_percentage)
                        VALUES (?, ?, ?, ?)
                    \'\'\', (total_stores, online_stores, offline_stores, online_percentage))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save summary report: {str(e)}")
            logger.error(f"  Parameters: total={total_stores}, online={online_stores}, offline={offline_stores}")
            return False
    
    def get_latest_status(self) -> pd.DataFrame:
        """Get latest status with error handling"""
        try:
            with self.get_connection() as conn:
                query = \'\'\'
                    SELECT 
                        s.name,
                        s.url,
                        s.platform,
                        sc.is_online,
                        sc.checked_at,
                        sc.response_time_ms
                    FROM stores s
                    INNER JOIN status_checks sc ON s.id = sc.store_id
                    INNER JOIN (
                        SELECT store_id, MAX(checked_at) as latest_check
                        FROM status_checks
                        GROUP BY store_id
                    ) latest ON sc.store_id = latest.store_id AND sc.checked_at = latest.latest_check
                    ORDER BY s.name
                \'\'\'
                return pd.read_sql_query(query, conn)
        except Exception as e:
            logger.error(f"Failed to get latest status: {str(e)}")
            return pd.DataFrame()
    
    def get_hourly_data(self) -> pd.DataFrame:
        """Get hourly data with proper error handling"""
        try:
            with self.get_connection() as conn:
                if self.db_type == "postgresql":
                    query = \'\'\'
                        SELECT 
                            EXTRACT(HOUR FROM report_time AT TIME ZONE \'Asia/Manila\')::integer as hour,
                            ROUND(AVG(online_percentage)::numeric, 0)::integer as online_pct,
                            ROUND(AVG(100 - online_percentage)::numeric, 0)::integer as offline_pct,
                            COUNT(*) as data_points
                        FROM summary_reports
                        WHERE DATE(report_time AT TIME ZONE \'Asia/Manila\') = CURRENT_DATE
                        GROUP BY EXTRACT(HOUR FROM report_time AT TIME ZONE \'Asia/Manila\')
                        ORDER BY hour
                    \'\'\'
                else:
                    query = \'\'\'
                        SELECT 
                            strftime(\'%H\', report_time) as hour,
                            ROUND(AVG(online_percentage), 0) as online_pct,
                            ROUND(AVG(100 - online_percentage), 0) as offline_pct,
                            COUNT(*) as data_points
                        FROM summary_reports
                        WHERE DATE(report_time, \'+8 hours\') = DATE(\'now\', \'+8 hours\')
                        GROUP BY strftime(\'%H\', report_time)
                        ORDER BY hour
                    \'\'\'
                return pd.read_sql_query(query, conn)
        except Exception as e:
            logger.error(f"Failed to get hourly data: {str(e)}")
            return pd.DataFrame()
    
    def get_store_logs(self, limit: int = 50) -> pd.DataFrame:
        """Get store logs with error handling"""
        try:
            with self.get_connection() as conn:
                if self.db_type == "postgresql":
                    query = \'\'\'
                        SELECT 
                            s.name,
                            s.platform,
                            sc.is_online,
                            sc.checked_at,
                            sc.response_time_ms
                        FROM stores s
                        INNER JOIN status_checks sc ON s.id = sc.store_id
                        WHERE DATE(sc.checked_at AT TIME ZONE \'Asia/Manila\') = CURRENT_DATE
                        ORDER BY sc.checked_at DESC
                        LIMIT %s
                    \'\'\'
                    return pd.read_sql_query(query, conn, params=(limit,))
                else:
                    query = \'\'\'
                        SELECT 
                            s.name,
                            s.platform,
                            sc.is_online,
                            sc.checked_at,
                            sc.response_time_ms
                        FROM stores s
                        INNER JOIN status_checks sc ON s.id = sc.store_id
                        WHERE DATE(sc.checked_at, \'+8 hours\') = DATE(\'now\', \'+8 hours\')
                        ORDER BY sc.checked_at DESC
                        LIMIT ?
                    \'\'\'
                    return pd.read_sql_query(query, conn, params=(limit,))
        except Exception as e:
            logger.error(f"Failed to get store logs: {str(e)}")
            return pd.DataFrame()
    
    def get_daily_uptime(self) -> pd.DataFrame:
        """Get daily uptime with error handling"""
        try:
            with self.get_connection() as conn:
                if self.db_type == "postgresql":
                    query = \'\'\'
                        SELECT 
                            s.name,
                            s.platform,
                            COUNT(sc.id) as total_checks,
                            SUM(CASE WHEN sc.is_online = true THEN 1 ELSE 0 END) as online_checks,
                            ROUND(
                                (SUM(CASE WHEN sc.is_online = true THEN 1 ELSE 0 END) * 100.0 / COUNT(sc.id))::numeric, 
                                0
                            )::integer as uptime_percentage
                        FROM stores s
                        INNER JOIN status_checks sc ON s.id = sc.store_id
                        WHERE DATE(sc.checked_at AT TIME ZONE \'Asia/Manila\') = CURRENT_DATE
                        GROUP BY s.id, s.name, s.platform
                        ORDER BY uptime_percentage DESC
                    \'\'\'
                else:
                    query = \'\'\'
                        SELECT 
                            s.name,
                            s.platform,
                            COUNT(sc.id) as total_checks,
                            SUM(CASE WHEN sc.is_online = 1 THEN 1 ELSE 0 END) as online_checks,
                            ROUND(
                                (SUM(CASE WHEN sc.is_online = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(sc.id)), 
                                0
                            ) as uptime_percentage
                        FROM stores s
                        INNER JOIN status_checks sc ON s.id = sc.store_id
                        WHERE DATE(sc.checked_at, \'+8 hours\') = DATE(\'now\', \'+8 hours\')
                        GROUP BY s.id, s.name, s.platform
                        ORDER BY uptime_percentage DESC
                    \'\'\'
                return pd.read_sql_query(query, conn)
        except Exception as e:
            logger.error(f"Failed to get daily uptime: {str(e)}")
            return pd.DataFrame()
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database stats with error handling"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(\'SELECT COUNT(*) FROM stores\')
                store_count = cursor.fetchone()[0]
                
                cursor.execute(\'SELECT platform, COUNT(*) FROM stores GROUP BY platform\')
                platforms = dict(cursor.fetchall())
                
                cursor.execute(\'SELECT COUNT(*) FROM status_checks\')
                total_checks = cursor.fetchone()[0]
                
                cursor.execute(\'SELECT * FROM summary_reports ORDER BY report_time DESC LIMIT 1\')
                latest_summary = cursor.fetchone()
                
                return {
                    \'store_count\': store_count,
                    \'platforms\': platforms,
                    \'total_checks\': total_checks,
                    \'latest_summary\': dict(latest_summary) if latest_summary else None,
                    \'db_type\': self.db_type
                }
        except Exception as e:
            logger.error(f"Failed to get database stats: {str(e)}")
            return {
                \'store_count\': 0,
                \'platforms\': {},
                \'total_checks\': 0,
                \'latest_summary\': None,
                \'db_type\': self.db_type
            }
    
    def close(self):
        if self.connection_pool:
            try:
                self.connection_pool.closeall()
            except:
                pass

# Global database instance
db = DatabaseManager()
'''

    with open('database.py', 'w') as f:
        f.write(fixed_database_content)
    
    print("✅ Applied database fixes")

def stop_containers():
    """Stop running containers"""
    print("🛑 Stopping containers...")
    try:
        subprocess.run(['docker', 'compose', 'down'], check=False)
        time.sleep(5)
        print("✅ Containers stopped")
    except Exception as e:
        print(f"⚠️ Error stopping containers: {e}")

def rebuild_and_start():
    """Rebuild and start containers"""
    print("🏗️ Rebuilding and starting containers...")
    try:
        # Rebuild containers with the fixed code
        subprocess.run(['docker', 'compose', 'build', '--no-cache'], check=True)
        print("✅ Containers rebuilt")
        
        # Start services
        subprocess.run(['docker', 'compose', 'up', '-d'], check=True)
        print("✅ Services started")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error rebuilding/starting: {e}")
        return False

def check_service_status():
    """Check if services are running correctly"""
    print("🔍 Checking service status...")
    
    # Wait for services to start
    time.sleep(30)
    
    try:
        # Check container status
        result = subprocess.run(['docker', 'compose', 'ps'], 
                              capture_output=True, text=True, check=True)
        print("📊 Container Status:")
        print(result.stdout)
        
        # Check logs for any immediate errors
        print("\\n📋 Recent Monitor Logs:")
        log_result = subprocess.run(['docker', 'compose', 'logs', '--tail=10', 'monitor'], 
                                  capture_output=True, text=True, check=False)
        print(log_result.stdout)
        
    except Exception as e:
        print(f"⚠️ Error checking status: {e}")

def main():
    """Main fix application"""
    print("🔧 CocoPan Monitor Fix Script")
    print("=" * 50)
    print("This script will fix the database error issues causing container restarts")
    print()
    
    # Check if we're in the right directory
    if not os.path.exists('docker-compose.yml'):
        print("❌ docker-compose.yml not found!")
        print("💡 Please run this script from the CocoPan project directory")
        return False
    
    print("📋 Fix Steps:")
    print("1. Create backup of current files")
    print("2. Apply database fixes")
    print("3. Stop and rebuild containers")
    print("4. Start services with fixes")
    print()
    
    # Confirm before proceeding
    response = input("Continue with fixes? (y/N): ").lower()
    if response != 'y':
        print("❌ Fix cancelled by user")
        return False
    
    try:
        # Step 1: Create backup
        backup_dir = create_backup()
        
        # Step 2: Apply fixes
        apply_database_fix()
        
        # Step 3: Stop containers
        stop_containers()
        
        # Step 4: Rebuild and start
        success = rebuild_and_start()
        
        if success:
            print("\\n🎉 Fixes applied successfully!")
            print("\\n📊 Next Steps:")
            print("1. Monitor logs: docker compose logs -f monitor")
            print("2. Check dashboard: http://localhost:8501")
            print("3. Watch for database errors (should be resolved)")
            print()
            print("🔍 Checking service status...")
            check_service_status()
            
            print(f"\\n💾 Backup available in: {backup_dir}")
            print("   (You can restore from backup if needed)")
            
        else:
            print("\\n❌ Error applying fixes")
            print(f"💾 Original files backed up in: {backup_dir}")
            print("💡 You can restore from backup and try again")
            
    except Exception as e:
        print(f"\\n❌ Critical error: {e}")
        print("💾 Check backup directory for original files")
        return False
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)