import asyncio
from sqlalchemy import text
from app.database.db import engine

async def main():
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE jant SET image_url = REPLACE(image_url, 'assets/jantlar/', 'uploads/plugins/jants/') WHERE image_url LIKE 'assets/jantlar/%'"))
        print("Updated jant image_url paths successfully.")

if __name__ == "__main__":
    asyncio.run(main())
