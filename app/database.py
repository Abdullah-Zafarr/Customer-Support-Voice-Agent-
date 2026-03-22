from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from .config import settings

engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class PatientInquiry(Base):
    __tablename__ = "patient_inquiries"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, index=True) # Keeping original column for compatibility with manual migration simplicity or renaming it
    # Let's actually do the clean renaming. 
    patient_name = Column(String, index=True)
    inquiry_details = Column(String)
    urgency = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    status = Column(String, default="open")  # open, in_progress, resolved, closed

class CallSession(Base):
    __tablename__ = "call_sessions"
    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, default=datetime.now)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0)
    messages_count = Column(Integer, default=0)
    tickets_created = Column(Integer, default=0)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
