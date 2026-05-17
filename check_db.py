import asyncio
import asyncpg
async def check():
    conn = await asyncpg.connect('postgresql://postgres:1234@localhost:5432/modifai')
    records = await conn.fetch('SELECT scan_id, method, status FROM scans ORDER BY scan_id DESC LIMIT 5')
    print(records)
    await conn.close()
asyncio.run(check())
