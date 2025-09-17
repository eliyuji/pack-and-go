import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_connection():
    db_url = os.getenv("DB")
    if not db_url:
        raise ValueError("DATABASE_URL is not set in .env")
    return psycopg2.connect(db_url)
