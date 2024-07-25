import psutil
import logging
import asyncio
import configparser
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from asyncpg import create_pool
from aiomonitor import Monitor
from concurrent.futures import ThreadPoolExecutor
import os

# 配置日志记录
logging.basicConfig(filename='process_stats.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取配置文件
config = configparser.ConfigParser()
config.read('config.ini')

DB_PATH = os.getenv('DB_PATH', config.get('Database', 'DB_PATH', fallback='postgresql+asyncpg://localhost/detailed_process_stats'))
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', config.get('Settings', 'UPDATE_INTERVAL', fallback=10)))
MONITOR_INTERVAL = int(os.getenv('MONITOR_INTERVAL', config.get('Settings', 'MONITOR_INTERVAL', fallback=60)))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', config.get('Settings', 'MAX_WORKERS', fallback=10)))

# SQLAlchemy 设置
engine = create_engine(DB_PATH, echo=False)
Session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()

# 定义数据库模型
class ProcessStats(Base):
    __tablename__ = 'process_stats'
    pid = Column(Integer, primary_key=True)
    name = Column(String)
    cmdline = Column(Text, primary_key=True)
    cpu_user_time = Column(Float)
    cpu_system_time = Column(Float)
    memory_info = Column(Text)
    threads = Column(Integer)
    open_files = Column(Text)
    connections = Column(Text)
    count = Column(Integer)
    last_update = Column(String)

Base.metadata.create_all(engine)

def serialize_list(items):
    """序列化列表，将其转为字符串以便存储在数据库中"""
    return ', '.join(str(item) for item in items)

async def collect_process_stats(queue):
    """定期收集进程信息并将其放入队列中"""
    while True:
        current_processes = {}
        for p in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_times', 'memory_info', 'num_threads', 'open_files', 'connections']):
            try:
                info = p.info
                cmdline = ' '.join(info['cmdline'])
                current_processes[p.pid] = {
                    'name': info['name'],
                    'cmdline': cmdline,
                    'cpu_user_time': info['cpu_times'].user,
                    'cpu_system_time': info['cpu_times'].system,
                    'memory_info': str(info['memory_info']),
                    'threads': info['num_threads'],
                    'open_files': serialize_list(info['open_files']),
                    'connections': serialize_list(info['connections']),
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                logging.warning(f"Could not retrieve information for process PID: {p.pid}. Reason: {str(e)}")
                continue
        
        await queue.put(current_processes)
        await asyncio.sleep(UPDATE_INTERVAL)  # 每 UPDATE_INTERVAL 秒更新一次

async def update_process_stats(pool, queue):
    """从队列中获取进程信息并更新数据库"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            while True:
                processes = await queue.get()
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                update_queries = []
                insert_queries = []

                for pid, info in processes.items():
                    result = await conn.fetchrow('''
                        SELECT cpu_user_time, cpu_system_time, count 
                        FROM process_stats 
                        WHERE pid = $1 AND cmdline = $2
                    ''', pid, info['cmdline'])
                    
                    if result:
                        old_cpu_user_time, old_cpu_system_time, count = result
                        update_queries.append((
                            info['cpu_user_time'], 
                            info['cpu_system_time'], 
                            info['memory_info'], 
                            info['threads'], 
                            info['open_files'], 
                            info['connections'], 
                            count + 1, 
                            current_time, 
                            pid, 
                            info['cmdline']
                        ))
                    else:
                        insert_queries.append((
                            pid, 
                            info['name'], 
                            info['cmdline'], 
                            info['cpu_user_time'], 
                            info['cpu_system_time'], 
                            info['memory_info'], 
                            info['threads'], 
                            info['open_files'], 
                            info['connections'], 
                            1, 
                            current_time
                        ))

                if update_queries:
                    try:
                        await conn.executemany('''
                        UPDATE process_stats SET 
                            cpu_user_time = $1, 
                            cpu_system_time = $2, 
                            memory_info = $3, 
                            threads = $4, 
                            open_files = $5, 
                            connections = $6, 
                            count = $7, 
                            last_update = $8
                        WHERE pid = $9 AND cmdline = $10''', update_queries)
                    except SQLAlchemyError as e:
                        logging.error(f"Failed to update database: {str(e)}")

                if insert_queries:
                    try:
                        await conn.executemany('''
                        INSERT INTO process_stats (
                            pid, 
                            name, 
                            cmdline, 
                            cpu_user_time, 
                            cpu_system_time, 
                            memory_info, 
                            threads, 
                            open_files, 
                            connections, 
                            count,
                            last_update
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)''', insert_queries)
                    except SQLAlchemyError as e:
                        logging.error(f"Failed to insert into database: {str(e)}")

async def monitor_system():
    """监控系统健康状况"""
    while True:
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)
        logging.info(f"Memory Usage: {mem.percent}% | CPU Usage: {cpu}%")
        await asyncio.sleep(MONITOR_INTERVAL)  # 每 MONITOR_INTERVAL 秒记录一次

async def async_main():
    """主函数，初始化数据库并开始进程信息收集和系统监控"""
    pool = await create_pool(dsn=DB_PATH)
    queue = asyncio.Queue()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        loop = asyncio.get_running_loop()
        loop.set_default_executor(executor)
        
        async with Monitor():
            await asyncio.gather(
                collect_process_stats(queue),
                update_process_stats(pool, queue),
                monitor_system()
            )

if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logging.info("Process stats collection stopped.")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        # 尝试重新启动程序
        os.execv(__file__, ['python'] + [__file__])
