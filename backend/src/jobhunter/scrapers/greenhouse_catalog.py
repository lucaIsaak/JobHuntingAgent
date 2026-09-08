"""Static catalog of public Greenhouse-hosted companies with domain tags for fit scoring.

Sourced from backend/greenhouse.txt (which is otherwise not read by any code); tags are drawn
from the same DOMAIN_SIGNALS vocabulary used by profile_extractor.extract_domain_tags so a
candidate profile's industries can be scored directly against a company's tags.
"""

from dataclasses import dataclass

from jobhunter.models.search_criteria import CandidateProfile


@dataclass(frozen=True)
class GreenhouseCompany:
    name: str
    board_token: str
    tags: tuple[str, ...]


GREENHOUSE_COMPANIES: tuple[GreenhouseCompany, ...] = (
    GreenhouseCompany("Airbnb", "airbnb", ("marketplace_delivery", "technology", "design")),
    GreenhouseCompany("Stripe", "stripe", ("fintech", "developer_tools", "technology")),
    GreenhouseCompany("Anthropic", "anthropic", ("ai_ml", "technology")),
    GreenhouseCompany("Notion", "notion", ("productivity_saas", "design", "technology")),
    GreenhouseCompany("Linear", "linear", ("developer_tools", "productivity_saas", "technology")),
    GreenhouseCompany("Vercel", "vercel", ("developer_tools", "technology")),
    GreenhouseCompany("Figma", "figma", ("design", "productivity_saas", "technology")),
    GreenhouseCompany("Instacart", "instacart", ("marketplace_delivery", "technology")),
    GreenhouseCompany("DoorDash", "doordash", ("marketplace_delivery", "technology")),
    GreenhouseCompany("Asana", "asana", ("productivity_saas", "technology")),
    GreenhouseCompany("Brex", "brex", ("fintech", "technology")),
    GreenhouseCompany("Ramp", "ramp", ("fintech", "technology")),
    GreenhouseCompany("Plaid", "plaid", ("fintech", "developer_tools", "technology")),
    GreenhouseCompany("Robinhood", "robinhood", ("fintech", "technology")),
    GreenhouseCompany("Coinbase", "coinbase", ("crypto_web3", "fintech", "technology")),
    GreenhouseCompany("Webflow", "webflow", ("developer_tools", "design", "technology")),
    GreenhouseCompany("Loom", "loom", ("productivity_saas", "technology")),
    GreenhouseCompany("Retool", "retool", ("developer_tools", "technology")),
    GreenhouseCompany("Rippling", "rippling", ("hr_tech", "technology")),
    GreenhouseCompany("Gusto", "gusto", ("hr_tech", "technology")),
    GreenhouseCompany("Mercury", "mercury", ("fintech", "technology")),
    GreenhouseCompany("Replit", "replit", ("developer_tools", "ai_ml", "technology")),
    GreenhouseCompany("Perplexity", "perplexity", ("ai_ml", "technology")),
    GreenhouseCompany("Hugging Face", "huggingface", ("ai_ml", "developer_tools", "technology")),
    GreenhouseCompany("OpenAI", "openai", ("ai_ml", "technology")),
)


def score_company(profile: CandidateProfile, company: GreenhouseCompany) -> float:
    if not company.tags:
        return 0.0
    profile_tags = set(profile.industries)
    overlap = len(profile_tags & set(company.tags))
    return overlap / len(company.tags)


def select_top_companies(
    profile: CandidateProfile,
    top_n: int = 5,
    catalog: tuple[GreenhouseCompany, ...] = GREENHOUSE_COMPANIES,
) -> list[str]:
    """Board tokens for the top_n companies that best fit the candidate's domain tags.

    Falls back to the first top_n 'technology'-tagged companies when the profile carries no
    domain signal, mirroring the previous default-to-'technology' behavior.
    """
    if not profile.industries:
        return [company.board_token for company in catalog if "technology" in company.tags][:top_n]

    scored = [(score_company(profile, company), company) for company in catalog]
    scored = [(score, company) for score, company in scored if score > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [company.board_token for _, company in scored[:top_n]]
