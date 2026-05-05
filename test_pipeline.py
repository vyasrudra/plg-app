import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("Testing Render Live URL...")
        try:
            resp = await client.post(
                "https://plg-app-m8vg.onrender.com/generate-leads",
                json={"company_name": "WebFX", "website": "https://www.webfx.com/"}
            )
            print(f"Status: {resp.status_code}")
            print(resp.json())
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
