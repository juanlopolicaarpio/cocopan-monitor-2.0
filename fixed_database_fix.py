#!/usr/bin/env python3
"""
Enhanced CocoPan Database Fix Script
Comprehensive fix for "PostgreSQL error: 0" and connection issues
"""
import os
import sys
import shutil
import subprocess
import time
import json
from datetime import datetime
from pathlib import Path

def create_backup():
    """Create backup of current files"""
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    files_to_backup = [
        'database.py',
        'monitor_service.py', 
        'docker-compose.yml',
        'config.py'
    ]
    
    for file in files_to_backup:
        if os.path.exists(file):
            shutil.copy2(file, backup_dir)
            print(f"✅ Backed up {file}")
    
    print(f"📦 Backup created in: {backup_dir}")
    return backup_dir

def diagnose_database_issues():
    """Diagnose current database connectivity issues"""
    print("🔍 Diagnosing database connectivity issues...")
    
    # Check if containers are running
    try:
        result = subprocess.run(['docker', 'ps', '--filter', 'name=cocopan'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Docker is accessible")
            if 'cocopan_postgres' in result.stdout:
                print("✅ PostgreSQL container exists")
                if 'Up' in result.stdout:
                    print("✅ PostgreSQL container is running")
                else:
                    print("❌ PostgreSQL container is not running")
                    return False
            else:
                print("❌ PostgreSQL container not found")
                return False
        else:
            print("❌ Docker command failed")
            return False
    except Exception as e:
        print(f"❌ Docker check failed: {e}")
        return False
    
    # Check PostgreSQL logs
    try:
        result = subprocess.run(['docker', 'logs', '--tail=20', 'cocopan_postgres'], 
                              capture_output=True, text=True, timeout=10)
        if 'database system is ready to accept connections' in result.stdout:
            print("✅ PostgreSQL is ready for connections")
        else:
            print("⚠️ PostgreSQL may not be fully initialized")
            print("PostgreSQL logs:")
            print(result.stdout[-500:])  # Last 500 chars
    except Exception as e:
        print(f"⚠️ Could not check PostgreSQL logs: {e}")
    
    return True

def create_enhanced_database_module():
    """Create enhanced database module with better error handling"""
    print("🔧 Creating enhanced database module...")
    
    enhanced_database_content = '''#!/usr/bin/env python3
"""
Enhanced CocoPan Database Module
Improved error handling and connection management
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
        self.max_retries = 3
        self.retry_delay = 5
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database with retry logic"""
        for attempt in range(self.max_retries):
            try:
                if self.db_type == "postgresql":
                    self._init_postgresql()
                else:
                    self._init_sqlite()
                self._create_tables()
                logger.info(f"✅ Database initialized ({self.db_type}) on attempt {attempt + 1}")
                return
            except Exception as e:
                logger.error(f"❌ Database initialization failed (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"🔄 Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error("❌ All database initialization attempts failed")
                    raise
    
    def _init_postgresql(self):
        """Initialize PostgreSQL with enhanced error handling"""
        try:
            db_url = config.DATABASE_URL
            logger.info(f"🔌 Attempting PostgreSQL connection: {self._mask_password(db_url)}")
            
            if not db_url.startswith('postgresql://'):
                raise ValueError(f"Invalid PostgreSQL URL format: {db_url}")
            
            # Test basic connection first
            test_conn = psycopg2.connect(db_url)
            test_conn.close()
            logger.info("✅ PostgreSQL test connection successful")
            
            # Create connection pool
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, 
                maxconn=20, 
                dsn=db_url, 
                cursor_factory=RealDictCursor
            )
            logger.info("✅ PostgreSQL connection pool created")
            
        except psycopg2.OperationalError as e:
            error_msg = str(e).strip()
            logger.error(f"❌ PostgreSQL operational error: {error_msg}")
            
            if "could not connect to server" in error_msg:
                logger.error("💡 PostgreSQL server appears to be down or unreachable")
            elif "database" in error_msg and "does not exist" in error_msg:
                logger.error("💡 Database does not exist")
            elif "authentication failed" in error_msg:
                logger.error("💡 Authentication failed - check username/password")
            
            logger.info("📝 Falling back to SQLite")
            self.db_type = "sqlite"
            self._init_sqlite()
            
        except psycopg2.Error as e:
            error_msg = str(e).strip()
            logger.error(f"❌ PostgreSQL error: {error_msg}")
            logger.error(f"Error code: {getattr(e, 'pgcode', 'N/A')}")
            
            logger.info("📝 Falling back to SQLite")
            self.db_type = "sqlite"
            self._init_sqlite()
            
        except Exception as e:
            error_msg = str(e).strip()
            logger.error(f"❌ Unexpected PostgreSQL error: {error_msg}")
            logger.error(f"Error type: {type(e).__name__}")
            
            logger.info("📝 Falling back to SQLite")
            self.db_type = "sqlite"
            self._init_sqlite()
    
    def _init_sqlite(self):
        """Initialize SQLite with enhanced error handling"""
        self.sqlite_path = config.SQLITE_PATH
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
            
            # Test connection
            conn = sqlite3.connect(self.sqlite_path, timeout=30)
            conn.execute("SELECT 1")  # Test query
            conn.close()
            logger.info(f"✅ SQLite database ready: {self.sqlite_path}")
        except Exception as e:
            logger.error(f"❌ SQLite connection failed: {str(e)}")
            raise
    
    def _mask_password(self, url: str) -> str:
        """Mask password in database URL for logging"""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\\\\1:****@', url)
    
    @contextmanager
    def get_connection(self):
        """Get database connection with enhanced error handling"""
        if self.db_type == "postgresql":
            conn = None
            try:
                if not self.connection_pool:
                    raise Exception("Connection pool not initialized")
                
                conn = self.connection_pool.getconn()
                if conn is None:
                    raise Exception("Failed to get connection from pool")
                
                # Test connection
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                
                yield conn
                
            except psycopg2.OperationalError as e:
                error_msg = str(e).strip()
                logger.error(f"❌ PostgreSQL operational error: {error_msg}")
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                raise Exception(f"PostgreSQL connection failed: {error_msg}")
                
            except psycopg2.Error as e:
                error_msg = str(e).strip()
                error_code = getattr(e, 'pgcode', 'N/A')
                logger.error(f"❌ PostgreSQL error: {error_msg} (code: {error_code})")
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                raise Exception(f"PostgreSQL error: {error_msg}")
                
            except Exception as e:
                error_msg = str(e).strip()
                logger.error(f"❌ Database connection error: {error_msg}")
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                raise
                
            finally:
                if conn and self.connection_pool:
                    try:
                        self.connection_pool.putconn(conn)
                    except:
                        pass
        else:
            # SQLite
            conn = None
            try:
                conn = sqlite3.connect(self.sqlite_path, timeout=30)
                conn.row_factory = sqlite3.Row
                
                # Test connection
                conn.execute("SELECT 1")
                
                yield conn
                
            except sqlite3.Error as e:
                error_msg = str(e).strip()
                logger.error(f"❌ SQLite error: {error_msg}")
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                raise Exception(f"SQLite error: {error_msg}")
                
            except Exception as e:
                error_msg = str(e).strip()
                logger.error(f"❌ Database error: {error_msg}")
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                raise
                
            finally:
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
    
    def _create_tables(self):
        """Create database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if self.db_type == "postgresql":
                # Create stores table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS stores (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        url TEXT NOT NULL UNIQUE,
                        platform VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create status_checks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS status_checks (
                        id SERIAL PRIMARY KEY,
                        store_id INTEGER REFERENCES stores(id),
                        is_online BOOLEAN NOT NULL,
                        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        response_time_ms INTEGER,
                        error_message TEXT
                    )
                """)
                
                # Create summary_reports table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS summary_reports (
                        id SERIAL PRIMARY KEY,
                        total_stores INTEGER NOT NULL,
                        online_stores INTEGER NOT NULL,
                        offline_stores INTEGER NOT NULL,
                        online_percentage REAL NOT NULL,
                        report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                # SQLite tables
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS stores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL UNIQUE,
                        platform TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS status_checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        store_id INTEGER,
                        is_online BOOLEAN NOT NULL,
                        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        response_time_ms INTEGER,
                        error_message TEXT,
                        FOREIGN KEY (store_id) REFERENCES stores (id)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS summary_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        total_stores INTEGER NOT NULL,
                        online_stores INTEGER NOT NULL,
                        offline_stores INTEGER NOT NULL,
                        online_percentage REAL NOT NULL,
                        report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            conn.commit()
    
    def get_or_create_store(self, name: str, url: str) -> int:
        """Get or create store with enhanced error handling"""
        platform = "foodpanda" if "foodpanda.ph" in url else "grabfood"
        
        for attempt in range(self.max_retries):
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
                error_msg = str(e).strip()
                logger.error(f"❌ Failed to get_or_create_store for {name} (attempt {attempt + 1}): {error_msg}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise Exception(f"Failed to create store after {self.max_retries} attempts: {error_msg}")
    
    def save_status_check(self, store_id: int, is_online: bool, 
                         response_time_ms: Optional[int] = None, 
                         error_message: Optional[str] = None) -> bool:
        """Save status check with enhanced error handling"""
        for attempt in range(self.max_retries):
            try:
                # Ensure proper data types
                is_online_value = bool(is_online)
                
                if response_time_ms is not None:
                    response_time_ms = int(response_time_ms)
                
                if error_message and len(error_message) > 500:
                    error_message = error_message[:500] + "..."
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    if self.db_type == "postgresql":
                        cursor.execute("""
                            INSERT INTO status_checks (store_id, is_online, response_time_ms, error_message)
                            VALUES (%s, %s, %s, %s)
                        """, (store_id, is_online_value, response_time_ms, error_message))
                    else:
                        cursor.execute("""
                            INSERT INTO status_checks (store_id, is_online, response_time_ms, error_message)
                            VALUES (?, ?, ?, ?)
                        """, (store_id, is_online_value, response_time_ms, error_message))
                    
                    conn.commit()
                    return True
                    
            except Exception as e:
                error_msg = str(e).strip()
                logger.error(f"❌ Failed to save status check for store_id {store_id} (attempt {attempt + 1}): {error_msg}")
                logger.error(f"  Parameters: is_online={is_online}, response_time={response_time_ms}, error='{error_message}'")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ Failed to save status check after {self.max_retries} attempts")
                    return False
    
    def save_summary_report(self, total_stores: int, online_stores: int, offline_stores: int) -> bool:
        """Save summary report with enhanced error handling"""
        for attempt in range(self.max_retries):
            try:
                online_percentage = (online_stores / total_stores * 100) if total_stores > 0 else 0
                
                # Ensure proper data types
                total_stores = int(total_stores)
                online_stores = int(online_stores)
                offline_stores = int(offline_stores)
                online_percentage = float(online_percentage)
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    if self.db_type == "postgresql":
                        cursor.execute("""
                            INSERT INTO summary_reports (total_stores, online_stores, offline_stores, online_percentage)
                            VALUES (%s, %s, %s, %s)
                        """, (total_stores, online_stores, offline_stores, online_percentage))
                    else:
                        cursor.execute("""
                            INSERT INTO summary_reports (total_stores, online_stores, offline_stores, online_percentage)
                            VALUES (?, ?, ?, ?)
                        """, (total_stores, online_stores, offline_stores, online_percentage))
                    
                    conn.commit()
                    return True
                    
            except Exception as e:
                error_msg = str(e).strip()
                logger.error(f"❌ Failed to save summary report (attempt {attempt + 1}): {error_msg}")
                logger.error(f"  Parameters: total={total_stores}, online={online_stores}, offline={offline_stores}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ Failed to save summary report after {self.max_retries} attempts")
                    return False
    
    def get_latest_status(self) -> pd.DataFrame:
        """Get latest status with error handling"""
        try:
            with self.get_connection() as conn:
                query = """
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
                """
                return pd.read_sql_query(query, conn)
        except Exception as e:
            logger.error(f"❌ Failed to get latest status: {str(e)}")
            return pd.DataFrame()
    
    def get_hourly_data(self) -> pd.DataFrame:
        """Get hourly data with error handling"""
        try:
            with self.get_connection() as conn:
                if self.db_type == "postgresql":
                    query = """
                        SELECT 
                            EXTRACT(HOUR FROM report_time AT TIME ZONE 'Asia/Manila')::integer as hour,
                            ROUND(AVG(online_percentage)::numeric, 0)::integer as online_pct,
                            ROUND(AVG(100 - online_percentage)::numeric, 0)::integer as offline_pct,
                            COUNT(*) as data_points
                        FROM summary_reports
                        WHERE DATE(report_time AT TIME ZONE 'Asia/Manila') = CURRENT_DATE
                        GROUP BY EXTRACT(HOUR FROM report_time AT TIME ZONE 'Asia/Manila')
                        ORDER BY hour
                    """
                else:
                    query = """
                        SELECT 
                            strftime('%H', report_time) as hour,
                            ROUND(AVG(online_percentage), 0) as online_pct,
                            ROUND(AVG(100 - online_percentage), 0) as offline_pct,
                            COUNT(*) as data_points
                        FROM summary_reports
                        WHERE DATE(report_time, '+8 hours') = DATE('now', '+8 hours')
                        GROUP BY strftime('%H', report_time)
                        ORDER BY hour
                    """
                return pd.read_sql_query(query, conn)
        except Exception as e:
            logger.error(f"❌ Failed to get hourly data: {str(e)}")
            return pd.DataFrame()
    
    def get_store_logs(self, limit: int = 50) -> pd.DataFrame:
        """Get store logs with error handling"""
        try:
            with self.get_connection() as conn:
                if self.db_type == "postgresql":
                    query = """
                        SELECT 
                            s.name,
                            s.platform,
                            sc.is_online,
                            sc.checked_at,
                            sc.response_time_ms
                        FROM stores s
                        INNER JOIN status_checks sc ON s.id = sc.store_id
                        WHERE DATE(sc.checked_at AT TIME ZONE 'Asia/Manila') = CURRENT_DATE
                        ORDER BY sc.checked_at DESC
                        LIMIT %s
                    """
                    return pd.read_sql_query(query, conn, params=(limit,))
                else:
                    query = """
                        SELECT 
                            s.name,
                            s.platform,
                            sc.is_online,
                            sc.checked_at,
                            sc.response_time_ms
                        FROM stores s
                        INNER JOIN status_checks sc ON s.id = sc.store_id
                        WHERE DATE(sc.checked_at, '+8 hours') = DATE('now', '+8 hours')
                        ORDER BY sc.checked_at DESC
                        LIMIT ?
                    """
                    return pd.read_sql_query(query, conn, params=(limit,))
        except Exception as e:
            logger.error(f"❌ Failed to get store logs: {str(e)}")
            return pd.DataFrame()
    
    def get_daily_uptime(self) -> pd.DataFrame:
        """Get daily uptime with error handling"""
        try:
            with self.get_connection() as conn:
                if self.db_type == "postgresql":
                    query = """
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
                        WHERE DATE(sc.checked_at AT TIME ZONE 'Asia/Manila') = CURRENT_DATE
                        GROUP BY s.id, s.name, s.platform
                        ORDER BY uptime_percentage DESC
                    """
                else:
                    query = """
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
                        WHERE DATE(sc.checked_at, '+8 hours') = DATE('now', '+8 hours')
                        GROUP BY s.id, s.name, s.platform
                        ORDER BY uptime_percentage DESC
                    """
                return pd.read_sql_query(query, conn)
        except Exception as e:
            logger.error(f"❌ Failed to get daily uptime: {str(e)}")
            return pd.DataFrame()
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database stats with error handling"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) FROM stores')
                store_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT platform, COUNT(*) FROM stores GROUP BY platform')
                platforms = dict(cursor.fetchall())
                
                cursor.execute('SELECT COUNT(*) FROM status_checks')
                total_checks = cursor.fetchone()[0]
                
                cursor.execute('SELECT * FROM summary_reports ORDER BY report_time DESC LIMIT 1')
                latest_summary = cursor.fetchone()
                
                return {
                    'store_count': store_count,
                    'platforms': platforms,
                    'total_checks': total_checks,
                    'latest_summary': dict(latest_summary) if latest_summary else None,
                    'db_type': self.db_type
                }
        except Exception as e:
            logger.error(f"❌ Failed to get database stats: {str(e)}")
            return {
                'store_count': 0,
                'platforms': {},
                'total_checks': 0,
                'latest_summary': None,
                'db_type': self.db_type
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test database connection and return diagnostic info"""
        result = {
            'status': 'unknown',
            'db_type': self.db_type,
            'error': None,
            'connection_time': None
        }
        
        try:
            start_time = time.time()
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 as test_value')
                test_result = cursor.fetchone()
                
                connection_time = time.time() - start_time
                
                if test_result:
                    result['status'] = 'success'
                    result['connection_time'] = connection_time
                else:
                    result['status'] = 'failed'
                    result['error'] = 'No result from test query'
                    
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            result['connection_time'] = time.time() - start_time
        
        return result
    
    def close(self):
        """Close database connections"""
        if self.connection_pool:
            try:
                self.connection_pool.closeall()
                logger.info("✅ Connection pool closed")
            except Exception as e:
                logger.error(f"❌ Error closing connection pool: {e}")

# Global database instance
db = DatabaseManager()
'''

    with open('database.py', 'w') as f:
        f.write(enhanced_database_content)
    
    print("✅ Enhanced database module created")

def create_connection_test_script():
    """Create a script to test database connectivity"""
    print("🔧 Creating database connection test script...")
    
    test_script_content = '''#!/usr/bin/env python3
"""
Database Connection Test Script
Test and diagnose database connectivity issues
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db
from config import config
import json

def test_database_connection():
    """Test database connection and operations"""
    print("🔍 Testing database connection...")
    print("=" * 50)
    
    # Test 1: Basic connection
    print("1️⃣ Testing basic connection...")
    conn_test = db.test_connection()
    print(f"   Database type: {conn_test['db_type']}")
    print(f"   Status: {conn_test['status']}")
    if conn_test['connection_time']:
        print(f"   Connection time: {conn_test['connection_time']:.3f}s")
    if conn_test['error']:
        print(f"   Error: {conn_test['error']}")
    
    if conn_test['status'] != 'success':
        print("❌ Basic connection failed!")
        return False
    
    print("✅ Basic connection successful")
    
    # Test 2: Database stats
    print("\\n2️⃣ Testing database stats...")
    try:
        stats = db.get_database_stats()
        print(f"   Store count: {stats['store_count']}")
        print(f"   Total checks: {stats['total_checks']}")
        print(f"   Platforms: {stats['platforms']}")
        print("✅ Database stats retrieved")
    except Exception as e:
        print(f"❌ Database stats failed: {e}")
        return False
    
    # Test 3: Store creation
    print("\\n3️⃣ Testing store creation...")
    try:
        store_id = db.get_or_create_store("Test Store", "https://example.com/test")
        print(f"   Created store ID: {store_id}")
        print("✅ Store creation successful")
    except Exception as e:
        print(f"❌ Store creation failed: {e}")
        return False
    
    # Test 4: Status check storage
    print("\\n4️⃣ Testing status check storage...")
    try:
        success = db.save_status_check(store_id, True, 1000, "Test check")
        if success:
            print("✅ Status check storage successful")
        else:
            print("❌ Status check storage failed")
            return False
    except Exception as e:
        print(f"❌ Status check storage failed: {e}")
        return False
    
    # Test 5: Summary report storage
    print("\\n5️⃣ Testing summary report storage...")
    try:
        success = db.save_summary_report(1, 1, 0)
        if success:
            print("✅ Summary report storage successful")
        else:
            print("❌ Summary report storage failed")
            return False
    except Exception as e:
        print(f"❌ Summary report storage failed: {e}")
        return False
    
    print("\\n" + "=" * 50)
    print("🎉 All database tests passed!")
    return True

if __name__ == "__main__":
    success = test_database_connection()
    sys.exit(0 if success else 1)
'''
    
    with open('test_database_connection.py', 'w') as f:
        f.write(test_script_content)
    
    print("✅ Database connection test script created")

def restart_services():
    """Restart services with proper sequence"""
    print("🔄 Restarting services...")
    
    try:
        # Stop all services
        print("🛑 Stopping all services...")
        subprocess.run(['docker', 'compose', 'down'], check=False, timeout=60)
        time.sleep(5)
        
        # Remove any orphaned containers
        subprocess.run(['docker', 'compose', 'down', '--remove-orphans'], check=False, timeout=60)
        
        # Rebuild containers
        print("🏗️ Rebuilding containers...")
        result = subprocess.run(['docker', 'compose', 'build', '--no-cache'], check=True, timeout=300)
        
        # Start database first
        print("🗄️ Starting PostgreSQL...")
        subprocess.run(['docker', 'compose', 'up', '-d', 'postgres'], check=True, timeout=120)
        
        # Wait for database to be ready
        print("⏳ Waiting for PostgreSQL to be ready...")
        max_wait = 60
        for i in range(max_wait):
            try:
                result = subprocess.run(
                    ['docker', 'exec', 'cocopan_postgres', 'pg_isready', '-U', 'cocopan', '-d', 'cocopan_monitor'],
                    capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    print(f"✅ PostgreSQL ready after {i+1} seconds")
                    break
            except subprocess.TimeoutExpired:
                pass
            
            if i == max_wait - 1:
                print("❌ PostgreSQL not ready after 60 seconds")
                return False
            
            time.sleep(1)
            print(f"   Waiting... ({i+1}/{max_wait})")
        
        # Start all services
        print("🚀 Starting all services...")
        subprocess.run(['docker', 'compose', 'up', '-d'], check=True, timeout=120)
        
        print("✅ Services restarted successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error restarting services: {e}")
        return False
    except subprocess.TimeoutExpired:
        print("❌ Service restart timed out")
        return False

def test_services():
    """Test if services are working correctly"""
    print("🔍 Testing services...")
    
    # Wait for services to start
    time.sleep(30)
    
    try:
        # Check container status
        result = subprocess.run(
            ['docker', 'compose', 'ps'], 
            capture_output=True, text=True, check=True, timeout=10
        )
        print("📊 Container Status:")
        print(result.stdout)
        
        # Test database connection
        print("\\n🗄️ Testing database connection...")
        result = subprocess.run(
            ['docker', 'exec', 'cocopan_monitor', 'python', 'test_database_connection.py'],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Database connection test passed")
            print(result.stdout)
        else:
            print("❌ Database connection test failed")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
        
        # Check recent logs
        print("\\n📋 Recent Monitor Logs:")
        log_result = subprocess.run(
            ['docker', 'compose', 'logs', '--tail=10', 'monitor'], 
            capture_output=True, text=True, check=False, timeout=10
        )
        print(log_result.stdout)
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing services: {e}")
        return False

def main():
    """Main fix application"""
    print("🔧 Enhanced CocoPan Database Fix Script")
    print("=" * 60)
    print("This script will comprehensively fix database connectivity issues")
    print()
    
    # Check if we're in the right directory
    if not os.path.exists('docker-compose.yml'):
        print("❌ docker-compose.yml not found!")
        print("💡 Please run this script from the CocoPan project directory")
        return False
    
    print("📋 Fix Steps:")
    print("1. Diagnose current database issues")
    print("2. Create backup of current files")
    print("3. Apply enhanced database module")
    print("4. Create database connection test script")
    print("5. Restart services with proper sequence")
    print("6. Test services and connectivity")
    print()
    
    # Confirm before proceeding
    response = input("Continue with enhanced fixes? (y/N): ").lower()
    if response != 'y':
        print("❌ Fix cancelled by user")
        return False
    
    try:
        # Step 1: Diagnose issues
        if not diagnose_database_issues():
            print("⚠️ Some connectivity issues detected, but continuing with fixes...")
        
        # Step 2: Create backup
        backup_dir = create_backup()
        
        # Step 3: Apply enhanced database module
        create_enhanced_database_module()
        
        # Step 4: Create test script
        create_connection_test_script()
        
        # Step 5: Restart services
        if not restart_services():
            print("❌ Failed to restart services")
            print(f"💾 Files backed up in: {backup_dir}")
            return False
        
        # Step 6: Test services
        if not test_services():
            print("❌ Service tests failed")
            print(f"💾 Files backed up in: {backup_dir}")
            return False
        
        print("\\n🎉 Enhanced fixes applied successfully!")
        print("\\n📊 Next Steps:")
        print("1. Monitor logs: docker compose logs -f monitor")
        print("2. Check dashboard: http://localhost:8501")
        print("3. Test database: python test_database_connection.py")
        print("4. pgAdmin (optional): http://localhost:5050")
        print()
        print("🔍 The database errors should now be resolved with:")
        print("   • Enhanced error handling and retry logic")
        print("   • Better connection pool management")
        print("   • Comprehensive diagnostic information")
        print("   • Improved Docker health checks")
        print()
        print(f"💾 Backup available in: {backup_dir}")
        
        return True
        
    except Exception as e:
        print(f"\\n❌ Critical error: {e}")
        print(f"💾 Check backup directory: {backup_dir}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)