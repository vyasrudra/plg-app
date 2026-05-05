import asyncio
from app.pipeline.qualify import QualificationPipeline
from app.models.schemas import CandidateCompany, ICPProfile

async def main():
    pipeline = QualificationPipeline()
    icp = ICPProfile(niche="marketing teams", ideal_customer_size="Not specified", ideal_customer_stage="Growth-focused", geographic_focus="national", industries_served=[])
    candidates = [
        CandidateCompany(company_name="The Search Kings", employee_count=2, country="US"),
        CandidateCompany(company_name="Digivate", employee_count=17, country="None")
    ]
    scored = await pipeline._qualify_candidates(candidates, icp)
    print(f"Scored leads: {len(scored)}")
    for s in scored:
        print(s)

if __name__ == "__main__":
    asyncio.run(main())
