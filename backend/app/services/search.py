from dataclasses import dataclass, field
from app.models.marketplace import Listing

CITY_ALIASES = {"bangalore": "bengaluru", "blr": "bengaluru"}
SORTS = {"recommended", "rent-asc", "rent-desc", "available", "newest", "trust"}


@dataclass
class Filters:  # same names as the web app's search filters
    q: str = ""
    budgetMin: int | None = None
    budgetMax: int | None = None
    bhk: list[int] = field(default_factory=list)
    furnishing: list[str] = field(default_factory=list)
    amenities: list[str] = field(default_factory=list)
    tenantType: str = ""
    depositWithinCap: bool = False
    withHistory: bool = False
    availableBy: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Filters":
        def ints(v):
            return [int(x) for x in (v or []) if str(x).isdigit()]
        def num(v):
            return int(v) if v not in (None, "") and str(v).lstrip("-").isdigit() else None
        return cls(q=str(d.get("q") or "")[:80], budgetMin=num(d.get("budgetMin")), budgetMax=num(d.get("budgetMax")),
                   bhk=ints(d.get("bhk")), furnishing=[str(x) for x in d.get("furnishing") or []][:5],
                   amenities=[str(x) for x in d.get("amenities") or []][:20], tenantType=str(d.get("tenantType") or "")[:20],
                   depositWithinCap=bool(d.get("depositWithinCap")), withHistory=bool(d.get("withHistory")),
                   availableBy=str(d.get("availableBy") or "")[:10])

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _squash(s: str) -> str:
    return "".join((s or "").lower().split())


def matches_query(listing: Listing, q: str) -> bool:
    q = " ".join((q or "").strip().lower().split())
    if not q:
        return True
    if q == listing.id.lower():
        return True
    if q.isdigit():
        return listing.pincode.startswith(q) if 3 <= len(q) <= 6 else False
    city = CITY_ALIASES.get(q, q)
    if city == (listing.city or "").lower():
        return True
    return _squash(q) in _squash(listing.locality) or _squash(q) in _squash(listing.title)


def matches(listing: Listing, f: Filters, history: int = 0) -> bool:
    if not matches_query(listing, f.q):
        return False
    if f.budgetMin is not None and listing.rent < f.budgetMin:
        return False
    if f.budgetMax is not None and listing.rent > f.budgetMax:
        return False
    if f.bhk and not any((listing.bhk >= 3) if b >= 3 else listing.bhk == b for b in f.bhk):
        return False
    if f.furnishing and listing.furnishing not in f.furnishing:
        return False
    if any(a not in (listing.amenities or []) for a in f.amenities):
        return False
    tenants = listing.preferred_tenants or ["any"]
    if f.tenantType and "any" not in tenants and f.tenantType not in tenants:
        return False
    if f.depositWithinCap and listing.rent and round(listing.deposit / listing.rent, 1) > 2:
        return False
    if f.withHistory and history == 0:
        return False
    if f.availableBy and (listing.available_from or "") > f.availableBy:
        return False
    return True


def trust_score(stats: dict) -> float:
    n = stats.get("tenancies_completed") or 0
    if not n:
        return 0.5
    raw = stats["full_refunds"] / n - 0.5 * (stats["disputes_lost"] / n)
    return min(1.0, max(0.0, 0.5 + (raw - 0.5) * min(1.0, n / 3)))
