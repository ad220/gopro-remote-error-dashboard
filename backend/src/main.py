import datetime
import shutil
import os
import sys
import asyncio

from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from api import app


def backup_database():
    # Get the current date
    current_date = datetime.datetime.now().strftime("%y-%m-%d")

    # Define the source and destination paths
    source_path = "data/errors.db"
    destination_path = f"data/backup/errors_{current_date}.db"

    # Check if the source file exists
    if not os.path.exists(source_path):
        print(f"Source file {source_path} does not exist.")

    # Copy the file to the backup location
    shutil.copy2(source_path, destination_path)
    print(f"Backup of {source_path} created at {destination_path}")


async def backup_loop() -> None:
    while True:
        await asyncio.sleep(86400)  # 24h
        try:
            backup_database()
        except Exception as e:
            print(f"[backup] failed: {e}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(backup_loop())
    yield
    task.cancel()


if __name__ == "__main__":
    import uvicorn
    backup_database()
    app.mount("/", StaticFiles(directory="static", html=True))
    uvicorn.run(app, host="127.0.0.1", port=8083, proxy_headers=True, forwarded_allow_ips="127.0.0.1")
