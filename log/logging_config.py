from loguru import logger
import sys
import json
from logging.handlers import TimedRotatingFileHandler

from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


# Define log format (JSON)
def json_formatter(record):
    return json.dumps({
        "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S"),
        "level": record["level"].name,
        "module": record["module"],
        "message": record["message"],
        "function": record["function"],
        "line": record["line"]
    })

# Remove default Loguru handler (to avoid duplicate logs)
logger.remove()

# Console Logging (JSON)
logger.add(sys.stdout, format="{message}", serialize=True, level="DEBUG")

# File Logging (Daily rotation, store up to 7 days)
logger.add("logs/app.json", rotation="1 day", retention="7 days", format="{message}", serialize=True, level="DEBUG")



# # Database Connection
# DATABASE_URL = "postgresql://user:password@localhost/logs_db"
# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(bind=engine)
# Base = declarative_base()

# # Define Log Table
# class LogEntry(Base):
#     __tablename__ = "logs"
#     id = Column(Integer, primary_key=True, index=True)
#     level = Column(String)
#     message = Column(String)
#     timestamp = Column(String)

# # Create Table
# Base.metadata.create_all(bind=engine)

# # Function to Save Log to Database
# def save_log_to_db(record):
#     session = SessionLocal()
#     log_entry = LogEntry(level=record["level"].name, message=record["message"], timestamp=str(record["time"]))
#     session.add(log_entry)
#     session.commit()
#     session.close()

# # Add Database Handler to Loguru
# logger.add(save_log_to_db, level="INFO")