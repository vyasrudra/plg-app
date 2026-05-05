import asyncio
import logging
from app.pipeline.qualify import QualificationPipeline
from app.models.schemas import CandidateCompany
import structlog

async def main():
    pipeline = QualificationPipeline()
    icp = await pipeline._extract_icp("https://www.webfx.com/")
    print(f"ICP: {icp}")
    target_info = await pipeline._enrich_target("https://www.webfx.com/", "WebFx")
    print(f"Target Info: {target_info}")
    
    # We will build candidate pool
    candidates = await pipeline._build_candidate_pool("WebFx", "https://www.webfx.com/", icp, target_info.get("state"))
    print(f"Filtered Candidates: {len(candidates)}")
    for c in candidates:
        print(c.company_name, c.employee_count, c.country)

if __name__ == "__main__":
    asyncio.run(main())
