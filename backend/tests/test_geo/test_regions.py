from jobhunter.geo.regions import countries_for_regions


def test_countries_for_regions_dedupes_overlapping_regions():
    countries = countries_for_regions(["Iberia", "EU"])
    assert countries.count("Spain") == 1
    assert countries.count("Portugal") == 1
    assert "Germany" in countries  # from EU


def test_countries_for_regions_single_region():
    countries = countries_for_regions(["Iberia"])
    assert countries == ["Portugal", "Spain"]


def test_countries_for_regions_ignores_unknown_region_names():
    countries = countries_for_regions(["Narnia", "Iberia"])
    assert countries == ["Portugal", "Spain"]


def test_countries_for_regions_empty_input_returns_empty():
    assert countries_for_regions([]) == []
