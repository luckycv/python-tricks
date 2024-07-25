import psutil
import logging
import asyncio
import configparser
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from concurrent.futures import ThreadPoolExecutor
from aiomonitor import Monitor

# 配置日志记录
logging.basicConfig(filename='process_stats.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取配置文件
config = configparser.ConfigParser()
config.read('config.ini')

DB_PATH = config.get('Database', 'DB_PATH', fallback='sqlite:///detailed_process_stats.db')
UPDATE_INTERVAL = config.getint('Settings', 'UPDATE_INTERVAL', fallback=10)
MONITOR_INTERVAL = config.getint('Settings', 'MONITOR_INTERVAL', fallback=60)

# 创建 SQLAlchemy 引擎和会话
engine = create_engine(DB_PATH, echo=False)  # echo=False 以减少日志输出
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
    """序列化列表，将其转为字符串以便存储在 SQLite 中"""
    return ', '.join(str(item) for item in items)

async def collect_process_stats():
    """定期收集进程信息"""
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
        
        await update_process_stats(current_processes)
        await asyncio.sleep(UPDATE_INTERVAL)  # 每 UPDATE_INTERVAL 秒更新一次

async def update_process_stats(processes):
    """更新数据库中的进程信息"""
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, _update_process_stats_db, processes)

def _update_process_stats_db(processes):
    """批量更新和插入进程信息到数据库"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session = Session()
    try:
        for pid, info in processes.items():
            process = session.query(ProcessStats).filter_by(pid=pid, cmdline=info['cmdline']).first()
            
            if process:
                process.cpu_user_time = info['cpu_user_time']
                process.cpu_system_time = info['cpu_system_time']
                process.memory_info = info['memory_info']
                process.threads = info['threads']
                process.open_files = info['open_files']
                process.connections = info['connections']
                process.count += 1
                process.last_update = current_time
            else:
                new_process = ProcessStats(
                    pid=pid,
                    name=info['name'],
                    cmdline=info['cmdline'],
                    cpu_user_time=info['cpu_user_time'],
                    cpu_system_time=info['cpu_system_time'],
                    memory_info=info['memory_info'],
                    threads=info['threads'],
                    open_files=info['open_files'],
                    connections=info['connections'],
                    count=1,
                    last_update=current_time
                )
                session.add(new_process)

        session.commit()
    except SQLAlchemyError as e:
        logging.error(f"Error updating database: {str(e)}")
    finally:
        session.remove()  # 关闭会话

async def monitor_system():
    """监控系统健康状况"""
    while True:
        # 记录系统的内存和CPU使用情况
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)
        logging.info(f"Memory Usage: {mem.percent}% | CPU Usage: {cpu}%")
        await asyncio.sleep(MONITOR_INTERVAL)  # 每 MONITOR_INTERVAL 秒记录一次

def main():
    """主函数，初始化数据库并开始进程信息收集和系统监控"""
    try:
        with Monitor():
            asyncio.run(asyncio.gather(
                collect_process_stats(),
                monitor_system()
            ))
    except KeyboardInterrupt:
        logging.info("Process stats collection stopped.")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        main()  # 重新启动以实现错误恢复

if __name__ == "__main__":
    main()
