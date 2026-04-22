import os
import ssl
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

engine = create_engine(
    os.getenv("DB_URL"),
    connect_args={"ssl_context": ssl_context},
    pool_pre_ping=True
)

df = pd.read_sql("SELECT COUNT(*) AS billing FROM healthcare.billing", engine)
print(df)
print("Connected!")