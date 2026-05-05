"""
PLG App — Main qualification pipeline.
Orchestrates: scrape → ICP extraction → LeadMagic → Claude qualification → geo mix → sheet.

Build Order Steps 10.6 – 10.8.
"""

import json
import asyncio
from typing import Optional

import structlog

from app.models.schemas import (
    ICPProfile,
    CandidateCompany,
    QualifiedLead,
)
from app.services.scraper import WebsiteScraper
from app.services.openrouter import OpenRouterClient
from app.services.leadmagic import LeadMagicClient
from app.services.sheets import GoogleSheetsClient
from app.services.geography import normalize_state
from app.pipeline.prompts import (
    ICP_EXTRACTION_PROMPT,
    LEAD_QUALIFICATION_PROMPT,
)

logger = structlog.get_logger()

# ─── Constants ─────────────────────────────────────────────────

TARGET_LEADS = 50
QUALIFICATION_BATCH_SIZE = 25




class QualificationPipeline:
    """End-to-end lead qualification pipeline."""

    def __init__(self):
        self.scraper = WebsiteScraper()
        self.ai = OpenRouterClient()
        self.leadmagic = LeadMagicClient()
        self.sheets = GoogleSheetsClient()

    async def run(
        self,
        company_name: str,
        website: str,
        lead_name: Optional[str] = None,
    ) -> tuple[str, int]:
        """
        Run the full pipeline.
        Returns (sheet_url, leads_count).
        """
        # ── Step 1: Scrape website → extract ICP via Gemini ────
        logger.info("pipeline_step", step="1_icp_extraction", company=company_name)
        icp = await self._extract_icp(website)
        logger.info("icp_extracted", niche=icp.niche, past_clients=icp.past_clients)

        # ── Step 2: Get target company info via LeadMagic ──────
        logger.info("pipeline_step", step="2_target_enrichment", company=company_name)
        target_info = await self._enrich_target(website, company_name)
        target_state = target_info.get("state")
        logger.info("target_enriched", state=target_state)

        # ── Step 3: Build candidate pool via LeadMagic ─────────
        logger.info("pipeline_step", step="3_candidate_pool")
        candidates = await self._build_candidate_pool(
            company_name=company_name,
            website=website,
            icp=icp,
            target_state=target_state,
        )
        logger.info("candidates_found", count=len(candidates))

        if not candidates:
            logger.warning("no_candidates_found")
            # Return an empty sheet
            sheet_url = self.sheets.create_sheet(company_name, [])
            return sheet_url, 0

        # ── Step 4: AI qualification via Claude ────────────────
        logger.info("pipeline_step", step="4_ai_qualification", candidates=len(candidates))
        scored = await self._qualify_candidates(candidates, icp)
        logger.info("qualification_done", scored=len(scored))

        # ── Step 5: Final filtering and exclusions ───────────────
        logger.info("pipeline_step", step="5_exclusions")
        leads = self._apply_exclusions(scored)
        
        # Sort by relevance and take top candidates
        leads.sort(key=lambda x: x.relevance_score, reverse=True)
        top_leads = leads[:TARGET_LEADS]
        
        # ── Step 6: Contact Discovery ────────────────────────────
        logger.info("pipeline_step", step="6_contact_discovery", count=len(top_leads))
        final_leads = []
        contact_tasks = [self._find_contact(lead) for lead in top_leads]
        if contact_tasks:
            results = await asyncio.gather(*contact_tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, QualifiedLead):
                    final_leads.append(res)
        
        logger.info("final_leads", count=len(final_leads))

        # ── Step 7: Write to Google Sheets ─────────────────────
        logger.info("pipeline_step", step="7_write_sheet")
        sheet_url = self.sheets.create_sheet(company_name, final_leads)
        
        return sheet_url, len(final_leads)

    async def _find_contact(self, lead: QualifiedLead) -> QualifiedLead:
        """Find decision maker (Owner/CEO/Marketing Director) at the company."""
        if not lead.website:
            return lead
            
        try:
            # Try to find high-level roles
            roles = ["CEO", "Owner", "Founder", "Marketing Director", "VP Marketing"]
            for role in roles:
                contact_res = await self.leadmagic.role_finder(company_domain=lead.website, role=role)
                data = contact_res.get("data", [])
                if data:
                    person = data[0]
                    lead.contact_name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                    lead.contact_title = person.get("title")
                    lead.contact_email = person.get("email")
                    lead.contact_phone = person.get("phone")
                    if lead.contact_email:
                        break # Found one!
            return lead
        except Exception as e:
            logger.warning("contact_discovery_failed", company=lead.company, error=str(e))
            return lead

    # ─── Step 1: ICP Extraction ────────────────────────────────

    async def _extract_icp(self, website: str) -> ICPProfile:
        """Step 1: Scrape website and extract ICP via Claude."""
        scraped_text = await self.scraper.scrape(website)
        
        prompt = ICP_EXTRACTION_PROMPT.format(scraped_text=scraped_text[:10000])
        raw_json = await self.ai.call_claude(prompt, temperature=0)
        
        data = await self.ai.parse_json_response(raw_json)
        logger.info("icp_extracted", niche=data.get("niche"), past_clients=data.get("past_clients"))
        
        return ICPProfile(**data)

    # ─── Step 2: Enrich Target Company ─────────────────────────

    async def _enrich_target(self, website: str, company_name: str) -> dict:
        """Get the target company's state and industry via LeadMagic."""
        domain = self._extract_domain(website)
        try:
            result = await self.leadmagic.company_search(
                company_domain=domain,
                company_name=company_name,
            )
            state = None
            hq = result.get("headquarter") or {}
            state = hq.get("geographicArea")
            if not state:
                locations = result.get("locations", [])
                for loc in locations:
                    if loc.get("headquarter"):
                        state = loc.get("geographicArea")
                        break
            return {
                "state": normalize_state(state),
                "industry": result.get("industry"),
                "employee_count": result.get("employeeCount"),
            }
        except Exception as e:
            logger.warning("target_enrichment_failed", error=str(e))
            return {"state": None, "industry": None, "employee_count": None}

    # ─── Step 3: Build Candidate Pool ──────────────────────────

    async def _build_candidate_pool(
        self,
        company_name: str,
        website: str,
        icp: ICPProfile,
        target_state: Optional[str],
    ) -> list[CandidateCompany]:
        """
        Build candidate pool using LeadMagic jobs_finder (discovery) based on the niche.
        """
        all_candidates: dict[str, CandidateCompany] = {}

        # 1. Use LeadMagic jobs_finder to find real companies based on the agency's niche
        # This replaces the AI-generated names with real-world hiring/business data.
        try:
            logger.info("discovery_search", niche=icp.niche)
            discovery_results = await self.leadmagic.jobs_finder(job_description=icp.niche, limit=50)
            
            # The jobs-finder returns companies matching the description
            # Let's extract domains/names from results
            results = discovery_results.get("data", [])
            seed_domains = []
            for item in results:
                domain = item.get("website") or item.get("company_domain")
                if domain:
                    seed_domains.append(domain)
        except Exception as e:
            logger.error("discovery_search_failed", error=str(e))
            seed_domains = []

        # 2. Enrich the discovered domains via LeadMagic company_search
        enrich_tasks = [self.leadmagic.company_search(company_domain=domain) for domain in seed_domains[:50]]
        if enrich_tasks:
            enriched_results = await asyncio.gather(*enrich_tasks, return_exceptions=True)
            for res in enriched_results:
                if isinstance(res, dict) and (res.get("domain") or res.get("website")):
                    candidate = self._parse_competitor(res)
                    if candidate:
                        # Enforce < 50 employees immediately
                        if candidate.employee_count is not None and candidate.employee_count >= 50:
                            continue
                            
                        key = (candidate.domain or candidate.company_name).lower()
                        if key not in all_candidates and candidate.company_name.lower() != company_name.lower():
                            all_candidates[key] = candidate

        logger.info("candidate_pool_built", total=len(all_candidates))
        return list(all_candidates.values())

    async def _get_competitors_of(self, domain: str) -> list[CandidateCompany]:
        """Get competitors of a company by domain."""
        try:
            result = await self.leadmagic.competitors_search(company_domain=domain)
            candidates = []
            for comp in result.get("competitors", []):
                candidate = self._parse_competitor(comp)
                if candidate:
                    candidates.append(candidate)
            return candidates
        except Exception:
            return []

    async def _enrich_candidate(self, candidate: CandidateCompany) -> CandidateCompany:
        """Enrich a candidate with full company data from LeadMagic."""
        try:
            result = await self.leadmagic.company_search(company_domain=candidate.domain)
            candidate.employee_count = result.get("employeeCount")
            candidate.industry = result.get("industry") or candidate.industry

            hq = result.get("headquarter") or {}
            candidate.state = normalize_state(hq.get("geographicArea"))
            candidate.city = hq.get("city")
            candidate.country = hq.get("country")

            founded = result.get("foundedOn") or {}
            if founded.get("year"):
                candidate.founded_year = str(founded["year"])
            elif result.get("founded_year"):
                candidate.founded_year = str(result["founded_year"])

            candidate.ownership_status = result.get("ownership_status")
            candidate.revenue = result.get("revenue")
            candidate.revenue_formatted = result.get("revenue_formatted")
            candidate.description = result.get("description")

            b2b_url = result.get("b2b_profile_url")
            if b2b_url:
                if not b2b_url.startswith("http"):
                    candidate.linkedin_url = f"https://linkedin.com/company/{b2b_url}"
                else:
                    candidate.linkedin_url = b2b_url

            return candidate
        except Exception as e:
            logger.warning("enrich_failed", domain=candidate.domain, error=str(e))
            return candidate

    def _parse_competitor(self, comp: dict) -> Optional[CandidateCompany]:
        """Parse a competitor object from LeadMagic into a CandidateCompany."""
        name = comp.get("name") or comp.get("companyName")
        if not name:
            return None

        # Extract employee count from various formats
        emp_count = comp.get("employeesCount") or comp.get("employee_count")
        if isinstance(emp_count, str):
            try:
                emp_count = int(emp_count.replace(",", ""))
            except (ValueError, AttributeError):
                emp_count = None

        # Extract HQ location
        hq_str = comp.get("hq", "")
        state = None
        country = None
        if hq_str:
            parts = [p.strip() for p in hq_str.split(",")]
            if len(parts) >= 2:
                country = parts[-1]
                state = normalize_state(parts[-2] if len(parts) > 2 else parts[0])

        # Extract domain/website
        domain = comp.get("domain") or comp.get("website")
        if domain:
            domain = domain.replace("https://", "").replace("http://", "").rstrip("/")

        linkedin_url = comp.get("profile_url") or comp.get("b2b_profile_url")
        if linkedin_url and not linkedin_url.startswith("http"):
            linkedin_url = f"https://linkedin.com/company/{linkedin_url}"

        return CandidateCompany(
            company_name=name,
            domain=domain,
            industry=comp.get("industry"),
            employee_count=emp_count,
            state=state,
            country=country,
            founded_year=comp.get("founded_year") or comp.get("founded"),
            description=comp.get("shortDescription") or comp.get("description"),
            linkedin_url=linkedin_url,
            ownership_status=comp.get("companyType") or comp.get("ownership"),
        )

    # ─── Step 4: AI Qualification ──────────────────────────────

    async def _qualify_candidates(
        self,
        candidates: list[CandidateCompany],
        icp: ICPProfile,
    ) -> list[QualifiedLead]:
        """
        Step 4: AI Qualification via Gemini
        Batch candidate companies and ask Gemini to score them against the ICP.
        """
        icp_json = icp.model_dump_json(indent=2)
        all_scored: list[QualifiedLead] = []

        # Process in batches
        for i in range(0, len(candidates), QUALIFICATION_BATCH_SIZE):
            batch = candidates[i:i + QUALIFICATION_BATCH_SIZE]
            batch_json = json.dumps(
                [c.model_dump() for c in batch],
                indent=2,
                default=str,
            )

            prompt = LEAD_QUALIFICATION_PROMPT.format(
                target_icp_json=icp_json,
                candidates_json=batch_json,
            )

            try:
                raw = await self.ai.call_gemini(prompt, temperature=0.2)
                scored_data = await self.ai.parse_json_response(raw)

                if not isinstance(scored_data, list):
                    scored_data = [scored_data]

                for item in scored_data:
                    # Find the matching candidate for enrichment data
                    matched = self._find_candidate(batch, item.get("company_name", ""))

                    lead = QualifiedLead(
                        company=item.get("company_name", "Unknown"),
                        website=matched.domain if matched else None,
                        industry=matched.industry if matched else None,
                        employees=matched.employee_count if matched else None,
                        state=matched.state if matched else None,
                        founded=matched.founded_year if matched else None,
                        relevance_score=item.get("relevance_score", 0),
                        why_qualified=item.get("why_qualified", ""),
                        buying_intent_signals=item.get("buying_intent_signals", []),
                        linkedin_url=matched.linkedin_url if matched else None,
                    )
                    all_scored.append(lead)

            except Exception as e:
                logger.warning("qualification_batch_failed", batch=i, error=str(e))
                continue

        # Sort by relevance score descending
        all_scored.sort(key=lambda x: x.relevance_score, reverse=True)
        return all_scored

    def _find_candidate(
        self, batch: list[CandidateCompany], name: str
    ) -> Optional[CandidateCompany]:
        """Find a candidate by name (fuzzy match)."""
        name_lower = name.lower().strip()
        for c in batch:
            if c.company_name.lower().strip() == name_lower:
                return c
        # Partial match fallback
        for c in batch:
            if name_lower in c.company_name.lower() or c.company_name.lower() in name_lower:
                return c
        return None

    # ─── Step 5: Exclusions ────────────────────────────────────

    def _apply_exclusions(self, leads: list[QualifiedLead]) -> list[QualifiedLead]:
        """Apply hard filters after scoring to remove defaulters/poor matches."""
        filtered = []
        for lead in leads:
            if lead.relevance_score >= 40:
                filtered.append(lead)

        return filtered



    # ─── Step 6: Geographic Mix ────────────────────────────────



    # ─── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _extract_domain(website: str) -> str:
        """Extract domain from a URL."""
        domain = website.replace("https://", "").replace("http://", "")
        domain = domain.split("/")[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
