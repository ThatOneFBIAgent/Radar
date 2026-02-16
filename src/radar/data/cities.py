"""
City database — searchable index of ~2,500 world cities with coordinates.

Provides fast prefix-based fuzzy search ranked by population,
used for the weather panel's location autofill.
"""

from __future__ import annotations

import gzip
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).parent / "cities_data.json.gz"


@dataclass(frozen=True, slots=True)
class CityEntry:
    """A city with geographic coordinates."""

    name: str
    region: str        # state, province, or region
    country: str       # ISO 3166-1 alpha-2 (US, GB, JP, etc.)
    latitude: float
    longitude: float
    population: int

    @property
    def display_name(self) -> str:
        """Format for dropdown display."""
        if self.region:
            return f"{self.name}, {self.region}, {self.country}"
        return f"{self.name}, {self.country}"

    @property
    def short_name(self) -> str:
        """Shorter format for the location label."""
        if self.region:
            return f"{self.name}, {self.region}"
        return f"{self.name}, {self.country}"


class CityIndex:
    """Searchable city database loaded from compressed JSON.

    Usage:
        idx = CityIndex()
        idx.load()
        results = idx.search("Hou", limit=10)
    """

    def __init__(self) -> None:
        self._cities: list[CityEntry] = []
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def count(self) -> int:
        return len(self._cities)

    def load(self, path: Path | None = None) -> None:
        """Load cities from compressed JSON file."""
        src = path or _DATA_FILE
        if not src.exists():
            logger.warning("City data file not found: %s — using built-in fallback", src)
            self._cities = _FALLBACK_CITIES
            self._loaded = True
            return

        try:
            with gzip.open(src, "rt", encoding="utf-8") as f:
                raw = json.load(f)

            self._cities = [
                CityEntry(
                    name=c["name"],
                    region=c.get("region", ""),
                    country=c["country"],
                    latitude=c["lat"],
                    longitude=c["lon"],
                    population=c.get("pop", 0),
                )
                for c in raw
            ]
            # Pre-sort by population descending for ranked results
            self._cities.sort(key=lambda c: c.population, reverse=True)
            self._loaded = True
            logger.info("Loaded %d cities from %s", len(self._cities), src.name)

        except Exception as e:
            logger.error("Failed to load city data: %s — using fallback", e)
            self._cities = _FALLBACK_CITIES
            self._loaded = True

    def search(self, query: str, limit: int = 10) -> list[CityEntry]:
        """Search cities by prefix match. Case-insensitive, ranked by population.

        Supports partial matching on city name, region, or country.
        """
        if not query or not query.strip():
            return []

        q = query.strip().lower()
        parts = [p.strip() for p in q.split(",")]

        matches: list[CityEntry] = []

        for city in self._cities:
            if len(matches) >= limit * 3:  # collect extra for scoring
                break

            name_lower = city.name.lower()
            region_lower = city.region.lower()
            country_lower = city.country.lower()
            display_lower = city.display_name.lower()

            if len(parts) == 1:
                # Single query — match name prefix or region/country contains
                if name_lower.startswith(q) or q in display_lower:
                    matches.append(city)
            elif len(parts) >= 2:
                # "city, region" or "city, region, country" style
                city_q = parts[0]
                region_q = parts[1] if len(parts) > 1 else ""

                if name_lower.startswith(city_q):
                    if not region_q or region_lower.startswith(region_q) or country_lower.startswith(region_q):
                        matches.append(city)

        # Sort: exact prefix matches first, then by population
        def _score(c: CityEntry) -> tuple[int, int]:
            exact = 0 if c.name.lower().startswith(parts[0]) else 1
            return (exact, -c.population)

        matches.sort(key=_score)
        return matches[:limit]

    def get_all(self) -> Sequence[CityEntry]:
        """Return all cities (sorted by population)."""
        return self._cities


# Fallback: major world cities if data file is missing────
_FALLBACK_CITIES = [
    CityEntry("Tokyo", "Tokyo", "JP", 35.6762, 139.6503, 13960000),
    CityEntry("Delhi", "Delhi", "IN", 28.7041, 77.1025, 11030000),
    CityEntry("Shanghai", "Shanghai", "CN", 31.2304, 121.4737, 24870000),
    CityEntry("São Paulo", "São Paulo", "BR", -23.5505, -46.6333, 12330000),
    CityEntry("Mexico City", "CDMX", "MX", 19.4326, -99.1332, 9210000),
    CityEntry("Cairo", "Cairo", "EG", 30.0444, 31.2357, 9540000),
    CityEntry("Mumbai", "Maharashtra", "IN", 19.0760, 72.8777, 12440000),
    CityEntry("Beijing", "Beijing", "CN", 39.9042, 116.4074, 21540000),
    CityEntry("Dhaka", "Dhaka", "BD", 23.8103, 90.4125, 8906000),
    CityEntry("Osaka", "Osaka", "JP", 34.6937, 135.5023, 2750000),
    CityEntry("New York", "NY", "US", 40.7128, -74.0060, 8336000),
    CityEntry("Karachi", "Sindh", "PK", 24.8607, 67.0011, 14910000),
    CityEntry("Buenos Aires", "Buenos Aires", "AR", -34.6037, -58.3816, 3076000),
    CityEntry("Istanbul", "Istanbul", "TR", 41.0082, 28.9784, 15460000),
    CityEntry("Lagos", "Lagos", "NG", 6.5244, 3.3792, 14860000),
    CityEntry("London", "England", "GB", 51.5074, -0.1278, 8982000),
    CityEntry("Los Angeles", "CA", "US", 34.0522, -118.2437, 3979000),
    CityEntry("Chicago", "IL", "US", 41.8781, -87.6298, 2694000),
    CityEntry("Houston", "TX", "US", 29.7604, -95.3698, 2320000),
    CityEntry("Phoenix", "AZ", "US", 33.4484, -112.0740, 1681000),
    CityEntry("Philadelphia", "PA", "US", 39.9526, -75.1652, 1584000),
    CityEntry("San Antonio", "TX", "US", 29.4241, -98.4936, 1547000),
    CityEntry("San Diego", "CA", "US", 32.7157, -117.1611, 1424000),
    CityEntry("Dallas", "TX", "US", 32.7767, -96.7970, 1344000),
    CityEntry("San Jose", "CA", "US", 37.3382, -121.8863, 1022000),
    CityEntry("Austin", "TX", "US", 30.2672, -97.7431, 979000),
    CityEntry("Jacksonville", "FL", "US", 30.3322, -81.6557, 950000),
    CityEntry("Fort Worth", "TX", "US", 32.7555, -97.3308, 919000),
    CityEntry("Columbus", "OH", "US", 39.9612, -82.9988, 906000),
    CityEntry("Charlotte", "NC", "US", 35.2271, -80.8431, 874000),
    CityEntry("Indianapolis", "IN", "US", 39.7684, -86.1581, 877000),
    CityEntry("San Francisco", "CA", "US", 37.7749, -122.4194, 874000),
    CityEntry("Seattle", "WA", "US", 47.6062, -122.3321, 737000),
    CityEntry("Denver", "CO", "US", 39.7392, -104.9903, 716000),
    CityEntry("Washington", "DC", "US", 38.9072, -77.0369, 690000),
    CityEntry("Nashville", "TN", "US", 36.1627, -86.7816, 689000),
    CityEntry("Oklahoma City", "OK", "US", 35.4676, -97.5164, 681000),
    CityEntry("El Paso", "TX", "US", 31.7619, -106.4850, 678000),
    CityEntry("Boston", "MA", "US", 42.3601, -71.0589, 675000),
    CityEntry("Portland", "OR", "US", 45.5152, -122.6784, 652000),
    CityEntry("Las Vegas", "NV", "US", 36.1699, -115.1398, 642000),
    CityEntry("Memphis", "TN", "US", 35.1495, -90.0490, 633000),
    CityEntry("Louisville", "KY", "US", 38.2527, -85.7585, 617000),
    CityEntry("Baltimore", "MD", "US", 39.2904, -76.6122, 586000),
    CityEntry("Milwaukee", "WI", "US", 43.0389, -87.9065, 577000),
    CityEntry("Albuquerque", "NM", "US", 35.0844, -106.6504, 560000),
    CityEntry("Tucson", "AZ", "US", 32.2226, -110.9747, 542000),
    CityEntry("Fresno", "CA", "US", 36.7378, -119.7871, 531000),
    CityEntry("Sacramento", "CA", "US", 38.5816, -121.4944, 524000),
    CityEntry("Mesa", "AZ", "US", 33.4152, -111.8315, 508000),
    CityEntry("Atlanta", "GA", "US", 33.7490, -84.3880, 499000),
    CityEntry("Kansas City", "MO", "US", 39.0997, -94.5786, 496000),
    CityEntry("Colorado Springs", "CO", "US", 38.8339, -104.8214, 479000),
    CityEntry("Omaha", "NE", "US", 41.2565, -95.9345, 478000),
    CityEntry("Raleigh", "NC", "US", 35.7796, -78.6382, 468000),
    CityEntry("Miami", "FL", "US", 25.7617, -80.1918, 442000),
    CityEntry("Minneapolis", "MN", "US", 44.9778, -93.2650, 430000),
    CityEntry("Cleveland", "OH", "US", 41.4993, -81.6944, 373000),
    CityEntry("Tampa", "FL", "US", 27.9506, -82.4572, 385000),
    CityEntry("New Orleans", "LA", "US", 29.9511, -90.0715, 391000),
    CityEntry("Pittsburgh", "PA", "US", 40.4406, -79.9959, 302000),
    CityEntry("Cincinnati", "OH", "US", 39.1031, -84.5120, 302000),
    CityEntry("St. Louis", "MO", "US", 38.6270, -90.1994, 302000),
    CityEntry("Orlando", "FL", "US", 28.5383, -81.3792, 287000),
    CityEntry("Salt Lake City", "UT", "US", 40.7608, -111.8910, 200000),
    CityEntry("Detroit", "MI", "US", 42.3314, -83.0458, 639000),
    CityEntry("Honolulu", "HI", "US", 21.3069, -157.8583, 350000),
    CityEntry("Anchorage", "AK", "US", 61.2181, -149.9003, 292000),
    # Major world cities not already listed
    CityEntry("Paris", "Île-de-France", "FR", 48.8566, 2.3522, 2161000),
    CityEntry("Berlin", "Berlin", "DE", 52.5200, 13.4050, 3645000),
    CityEntry("Madrid", "Comunidad de Madrid", "ES", 40.4168, -3.7038, 3224000),
    CityEntry("Rome", "Lazio", "IT", 41.9028, 12.4964, 2873000),
    CityEntry("Moscow", "Moscow", "RU", 55.7558, 37.6173, 12540000),
    CityEntry("Toronto", "Ontario", "CA", 43.6532, -79.3832, 2731000),
    CityEntry("Sydney", "NSW", "AU", -33.8688, 151.2093, 5312000),
    CityEntry("Melbourne", "VIC", "AU", -37.8136, 144.9631, 4936000),
    CityEntry("Seoul", "Seoul", "KR", 37.5665, 126.9780, 9776000),
    CityEntry("Singapore", "", "SG", 1.3521, 103.8198, 5850000),
    CityEntry("Hong Kong", "", "HK", 22.3193, 114.1694, 7482000),
    CityEntry("Bangkok", "Bangkok", "TH", 13.7563, 100.5018, 8281000),
    CityEntry("Jakarta", "Jakarta", "ID", -6.2088, 106.8456, 10560000),
    CityEntry("Manila", "Metro Manila", "PH", 14.5995, 120.9842, 1780000),
    CityEntry("Kuala Lumpur", "KL", "MY", 3.1390, 101.6869, 1808000),
    CityEntry("Taipei", "Taipei", "TW", 25.0330, 121.5654, 2647000),
    CityEntry("Ho Chi Minh City", "HCMC", "VN", 10.8231, 106.6297, 8993000),
    CityEntry("Lima", "Lima", "PE", -12.0464, -77.0428, 9752000),
    CityEntry("Bogotá", "Bogotá", "CO", 4.7110, -74.0721, 7181000),
    CityEntry("Santiago", "Santiago", "CL", -33.4489, -70.6693, 6270000),
    CityEntry("Nairobi", "Nairobi", "KE", -1.2921, 36.8219, 4397000),
    CityEntry("Johannesburg", "Gauteng", "ZA", -26.2041, 28.0473, 5635000),
    CityEntry("Cape Town", "Western Cape", "ZA", -33.9249, 18.4241, 4618000),
    CityEntry("Addis Ababa", "Addis Ababa", "ET", 9.0250, 38.7469, 3352000),
    CityEntry("Casablanca", "Casablanca-Settat", "MA", 33.5731, -7.5898, 3359000),
    CityEntry("Accra", "Greater Accra", "GH", 5.6037, -0.1870, 2291000),
    CityEntry("Riyadh", "Riyadh", "SA", 24.7136, 46.6753, 7680000),
    CityEntry("Dubai", "Dubai", "AE", 25.2048, 55.2708, 3331000),
    CityEntry("Tel Aviv", "Tel Aviv", "IL", 32.0853, 34.7818, 460000),
    CityEntry("Athens", "Attica", "GR", 37.9838, 23.7275, 664000),
    CityEntry("Lisbon", "Lisbon", "PT", 38.7223, -9.1393, 505000),
    CityEntry("Amsterdam", "North Holland", "NL", 52.3676, 4.9041, 873000),
    CityEntry("Brussels", "Brussels", "BE", 50.8503, 4.3517, 185000),
    CityEntry("Vienna", "Vienna", "AT", 48.2082, 16.3738, 1900000),
    CityEntry("Zurich", "Zürich", "CH", 47.3769, 8.5417, 421000),
    CityEntry("Munich", "Bavaria", "DE", 48.1351, 11.5820, 1472000),
    CityEntry("Hamburg", "Hamburg", "DE", 53.5511, 9.9937, 1845000),
    CityEntry("Barcelona", "Catalonia", "ES", 41.3874, 2.1686, 1621000),
    CityEntry("Milan", "Lombardy", "IT", 45.4642, 9.1900, 1352000),
    CityEntry("Warsaw", "Masovian", "PL", 52.2297, 21.0122, 1790000),
    CityEntry("Prague", "Prague", "CZ", 50.0755, 14.4378, 1309000),
    CityEntry("Budapest", "Budapest", "HU", 47.4979, 19.0402, 1752000),
    CityEntry("Stockholm", "Stockholm", "SE", 59.3293, 18.0686, 975000),
    CityEntry("Oslo", "Oslo", "NO", 59.9139, 10.7522, 694000),
    CityEntry("Copenhagen", "Capital Region", "DK", 55.6761, 12.5683, 602000),
    CityEntry("Helsinki", "Uusimaa", "FI", 60.1699, 24.9384, 656000),
    CityEntry("Dublin", "Leinster", "IE", 53.3498, -6.2603, 554000),
    CityEntry("Edinburgh", "Scotland", "GB", 55.9533, -3.1883, 527000),
    CityEntry("Manchester", "England", "GB", 53.4808, -2.2426, 553000),
    CityEntry("Kyiv", "Kyiv", "UA", 50.4504, 30.5234, 2884000),
    CityEntry("Bucharest", "Bucharest", "RO", 44.4268, 26.1025, 1794000),
    CityEntry("Vancouver", "BC", "CA", 49.2827, -123.1207, 631000),
    CityEntry("Montreal", "QC", "CA", 45.5017, -73.5673, 1762000),
    CityEntry("Calgary", "AB", "CA", 51.0447, -114.0719, 1239000),
    CityEntry("Ottawa", "ON", "CA", 45.4215, -75.6972, 935000),
    CityEntry("Edmonton", "AB", "CA", 53.5461, -113.4938, 981000),
    CityEntry("Havana", "Havana", "CU", 23.1136, -82.3666, 2132000),
    CityEntry("Santo Domingo", "DN", "DO", 18.4861, -69.9312, 965000),
    CityEntry("Guatemala City", "Guatemala", "GT", 14.6349, -90.5069, 994000),
    CityEntry("San Juan", "PR", "US", 18.4655, -66.1057, 318000),
    CityEntry("Auckland", "Auckland", "NZ", -36.8485, 174.7633, 1463000),
    CityEntry("Wellington", "Wellington", "NZ", -41.2865, 174.7762, 215000),
    CityEntry("Brisbane", "QLD", "AU", -27.4698, 153.0251, 2514000),
    CityEntry("Perth", "WA", "AU", -31.9505, 115.8605, 2085000),
    CityEntry("Adelaide", "SA", "AU", -34.9285, 138.6007, 1346000),
    CityEntry("Guangzhou", "Guangdong", "CN", 23.1291, 113.2644, 18680000),
    CityEntry("Shenzhen", "Guangdong", "CN", 22.5431, 114.0579, 17560000),
    CityEntry("Chengdu", "Sichuan", "CN", 30.5728, 104.0668, 16330000),
    CityEntry("Wuhan", "Hubei", "CN", 30.5928, 114.3055, 12330000),
    CityEntry("Hangzhou", "Zhejiang", "CN", 30.2741, 120.1551, 12200000),
    CityEntry("Chongqing", "Chongqing", "CN", 29.4316, 106.9123, 16380000),
    CityEntry("Tianjin", "Tianjin", "CN", 39.3434, 117.3616, 13870000),
    CityEntry("Nanjing", "Jiangsu", "CN", 32.0603, 118.7969, 9420000),
]
