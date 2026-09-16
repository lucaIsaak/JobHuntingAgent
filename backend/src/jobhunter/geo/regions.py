"""Region -> country taxonomy for the search form's Region/Country cascade, plus a canonical
language option list for the Language filter.

Flat and deliberately overlapping (e.g. Spain/Portugal appear under both "Iberia" and "EU") --
this mirrors how recruiting/business teams actually group markets, not a strict continent
hierarchy. A country reachable via two checked regions just dedupes in `countries_for_regions`,
no special-casing needed.
"""

from __future__ import annotations

from collections.abc import Sequence

REGIONS: dict[str, tuple[str, ...]] = {
    "North America": ("United States", "Canada", "Mexico"),
    "LATAM": ("Mexico", "Brazil", "Argentina", "Chile", "Colombia", "Peru", "Costa Rica"),
    "UK & Ireland": ("United Kingdom", "Ireland"),
    "Iberia": ("Spain", "Portugal"),
    "DACH": ("Germany", "Austria", "Switzerland"),
    "Nordics": ("Sweden", "Norway", "Denmark", "Finland", "Iceland"),
    "EU": (
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark", "Estonia",
        "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia",
        "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal", "Romania",
        "Slovakia", "Slovenia", "Spain", "Sweden",
    ),
    "Middle East": ("United Arab Emirates", "Saudi Arabia", "Israel", "Qatar", "Turkey"),
    "Africa": ("South Africa", "Nigeria", "Kenya", "Egypt", "Morocco"),
    "APAC": (
        "India", "China", "Japan", "Singapore", "Australia", "South Korea", "Indonesia", "Vietnam",
    ),
}

LANGUAGE_OPTIONS: tuple[str, ...] = (
    "German", "English", "French", "Spanish", "Italian", "Portuguese", "Dutch", "Chinese",
    "Japanese", "Korean", "Russian", "Arabic", "Polish", "Turkish", "Hindi",
)


def countries_for_regions(regions: Sequence[str]) -> list[str]:
    """Deduped, sorted union of every country in the given regions. Unknown region names are
    ignored rather than raising -- same tolerant-default style as the rest of this codebase."""
    countries = {country for region in regions for country in REGIONS.get(region, ())}
    return sorted(countries)
