import logging
import queue
import threading
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from app.config import settings

logger = logging.getLogger("fitness.db")


class Database:
    """基于 queue 的 PyMySQL 线程安全连接池，所有查询使用 %s 参数化占位符。"""

    def __init__(self):
        self._pool = queue.Queue(maxsize=settings.DB_POOL_SIZE)
        self._lock = threading.Lock()
        self._created = 0

    def _create_conn(self) -> pymysql.connections.Connection:
        return pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=DictCursor,
            connect_timeout=5,
        )

    def acquire(self) -> pymysql.connections.Connection:
        try:
            conn = self._pool.get_nowait()
        except queue.Empty:
            with self._lock:
                conn = self._create_conn()
                self._created += 1
        try:
            conn.ping(reconnect=True)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            conn = self._create_conn()
        return conn

    def release(self, conn):
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            conn.close()

    def query(self, sql: str, params=None, one: bool = False):
        conn = self.acquire()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                rows = cursor.fetchall()
            return (rows[0] if rows else None) if one else rows
        finally:
            self.release(conn)

    def execute(self, sql: str, params=None) -> int:
        """单条写操作，返回受影响行数。"""
        conn = self.acquire()
        try:
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params or ())
            conn.commit()
            return affected
        except Exception:
            conn.rollback()
            raise
        finally:
            self.release(conn)

    def insert(self, sql: str, params=None) -> int:
        """插入并返回自增主键。"""
        conn = self.acquire()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                new_id = cursor.lastrowid
            conn.commit()
            return new_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self.release(conn)

    def execute_many(self, sql: str, seq_params) -> int:
        conn = self.acquire()
        try:
            with conn.cursor() as cursor:
                affected = cursor.executemany(sql, seq_params)
            conn.commit()
            return affected
        except Exception:
            conn.rollback()
            raise
        finally:
            self.release(conn)

    @contextmanager
    def transaction(self):
        """多表写入事务：with db.transaction() as cursor: cursor.execute(...)"""
        conn = self.acquire()
        try:
            conn.begin()
            yield conn.cursor()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.release(conn)


db = Database()
