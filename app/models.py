from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
import datetime
import json

Base = declarative_base()

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    conn_type = Column(String(10), nullable=False)  # "rtu" or "wifi"
    settings = Column(Text, nullable=False)         # JSON dump of dict
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def as_dict(self):
        d = {
            "id": self.id,
            "name": self.name,
            "conn_type": self.conn_type,
            "settings": json.loads(self.settings)
        }
        return d
