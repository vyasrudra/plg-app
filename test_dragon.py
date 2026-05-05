import asyncio
import logging
from app.pipeline.qualify import QualificationPipeline
import structlog

async def main():
    pipeline = QualificationPipeline()
    url, count = await pipeline.run("DragonFly Digital Marketing", "https://dragonflydm.com/")
    print(f"Final Count: {count}")

if __name__ == "__main__":
    asyncio.run(main())
