"""Tests for the city database module."""

from __future__ import annotations

import json
import gzip
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from radar.data.cities import CityIndex, CityEntry


@pytest.fixture
def mock_cities_data(tmp_path: Path) -> Path:
    """Create a temporary gzipped city data file."""
    data = [
        {"name": "Test City", "region": "TS", "country": "US", "lat": 10.0, "lon": 20.0, "pop": 5000},
        {"name": "Big City", "region": "BG", "country": "US", "lat": 30.0, "lon": 40.0, "pop": 100000},
        {"name": "Tiny Town", "region": "", "country": "GB", "lat": 50.0, "lon": 0.0, "pop": 100},
        {"name": "Same Name", "region": "A", "country": "US", "lat": 0.0, "lon": 0.0, "pop": 2000},
        {"name": "Same Name", "region": "B", "country": "MX", "lat": 1.0, "lon": 1.0, "pop": 1000},
    ]
    file_path = tmp_path / "cities_data.json.gz"
    with gzip.open(file_path, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    return file_path


class TestCityEntry:
    def test_display_name_with_region(self) -> None:
        c = CityEntry("Nairobi", "Nairobi", "KE", -1.2, 36.8, 4000000)
        assert c.display_name == "Nairobi, Nairobi, KE"

    def test_display_name_without_region(self) -> None:
        c = CityEntry("Singapore", "", "SG", 1.3, 103.8, 5000000)
        assert c.display_name == "Singapore, SG"

    def test_short_name(self) -> None:
        c = CityEntry("Chicago", "IL", "US", 0, 0, 0)
        assert c.short_name == "Chicago, IL"
        
        c2 = CityEntry("London", "", "GB", 0, 0, 0)
        assert c2.short_name == "London, GB"


class TestCityIndex:
    def test_load_fallback_if_missing(self) -> None:
        idx = CityIndex()
        idx.load(Path("nonexistent_file.gz"))
        assert idx.loaded
        assert idx.count > 0  # Should have fallback cities
        assert any(c.name == "Tokyo" for c in idx.get_all())

    def test_load_from_file(self, mock_cities_data: Path) -> None:
        idx = CityIndex()
        idx.load(mock_cities_data)
        assert idx.loaded
        assert idx.count == 5
        # Verify sorting by population desc
        top = idx.get_all()[0]
        assert top.name == "Big City"

    def test_search_prefix(self, mock_cities_data: Path) -> None:
        idx = CityIndex()
        idx.load(mock_cities_data)
        
        results = idx.search("Ti", limit=5)
        assert len(results) == 1
        assert results[0].name == "Tiny Town"

    def test_search_case_insensitive(self, mock_cities_data: Path) -> None:
        idx = CityIndex()
        idx.load(mock_cities_data)
        
        results = idx.search("big", limit=5)
        assert len(results) == 1
        assert results[0].name == "Big City"

    def test_search_limit(self, mock_cities_data: Path) -> None:
        idx = CityIndex()
        idx.load(mock_cities_data)
        # Empty search returns nothing
        assert idx.search("", limit=5) == []

    def test_search_ranking(self, mock_cities_data: Path) -> None:
        idx = CityIndex()
        idx.load(mock_cities_data)
        
        # Should return Same Name (region A, pop 2000) before Same Name (region B, pop 1000)
        results = idx.search("Same", limit=5)
        assert len(results) == 2
        assert results[0].population == 2000
        assert results[1].population == 1000

    def test_search_compound(self, mock_cities_data: Path) -> None:
        idx = CityIndex()
        idx.load(mock_cities_data)
        
        # "City, Reg" format
        results = idx.search("Big, BG")
        assert len(results) == 1
        assert results[0].name == "Big City"

        # No match
        results = idx.search("Big, XYZ")
        assert len(results) == 0
