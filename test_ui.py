import asyncio
import httpx
import json

async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        payload = {
            "company_name": "Freedom Formula",
            "website": "https://www.gofreedomformula.co",
            "lead_name": "Rudra Vyas"
        }
        print(f"Sending POST /generate-leads with {payload}")
        try:
            resp = await client.post(
                "https://plg-app-m8vg.onrender.com/generate-leads",
                json=payload
            )
            print(f"Status: {resp.status_code}")
            print(resp.text)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
