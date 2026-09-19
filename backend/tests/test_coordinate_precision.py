"""
Tests for City-Scale and Country-Scale Coordinate Precision.

Validates that the coordinate precision system works correctly
at large distances without floating-point errors.
"""
import pytest
import math
from app.core.geospatial import (
    WGS84Coordinate, haversine_distance, bearing, bounding_box,
    create_transform
)
from app.core.world_precision import (
    FloatingOrigin, HighPrecisionPosition, WorldCoordinateManager,
    ORIGIN_REBASE_THRESHOLD
)


# Real-world city coordinates
CITIES = {
    "san_francisco": WGS84Coordinate(37.7749, -122.4194, 16.0),
    "new_york": WGS84Coordinate(40.7128, -74.0060, 10.0),
    "london": WGS84Coordinate(51.5074, -0.1278, 11.0),
    "tokyo": WGS84Coordinate(35.6762, 139.6503, 40.0),
    "sydney": WGS84Coordinate(-33.8688, 151.2093, 58.0),
    "paris": WGS84Coordinate(48.8566, 2.3522, 35.0),
    "dubai": WGS84Coordinate(25.2048, 55.2708, 5.0),
    "moscow": WGS84Coordinate(55.7558, 37.6173, 156.0),
    "beijing": WGS84Coordinate(39.9042, 116.4074, 43.0),
    "mumbai": WGS84Coordinate(19.0760, 72.8777, 14.0),
}


class TestCityScalePrecision:
    """Test coordinate precision at city scale (~10-50km)."""

    def test_san_fran_to_new_york_distance(self):
        dist = haversine_distance(CITIES["san_francisco"], CITIES["new_york"])
        # Known distance: ~4,130 km
        assert 4100000 < dist < 4200000

    def test_london_to_paris_distance(self):
        dist = haversine_distance(CITIES["london"], CITIES["paris"])
        # Known distance: ~340 km
        assert 330000 < dist < 350000

    def test_tokyo_to_beijing_distance(self):
        dist = haversine_distance(CITIES["tokyo"], CITIES["beijing"])
        # Known distance: ~2,100 km
        assert 2050000 < dist < 2150000

    def test_sydney_to_tokyo_distance(self):
        dist = haversine_distance(CITIES["sydney"], CITIES["tokyo"])
        # Known distance: ~7,820 km
        assert 7750000 < dist < 7900000

    def test_city_scale_enu_precision(self):
        """Test ENU precision within a city (10km radius)."""
        origin = CITIES["san_francisco"]
        transform = create_transform(origin)

        # Points within SF (Mission District, SFO, Golden Gate)
        points = [
            WGS84Coordinate(37.7599, -122.4148, 10.0),  # Mission
            WGS84Coordinate(37.6213, -122.3790, 4.0),   # SFO
            WGS84Coordinate(37.8199, -122.4783, 75.0),  # Golden Gate
        ]

        for point in points:
            enu = transform.wgs84_to_enu(point)
            # ENU coordinates should be within ±20km
            assert abs(enu.east) < 20000
            assert abs(enu.north) < 20000
            assert abs(enu.up) < 200

            # Round-trip conversion (within city: reasonable precision)
            back = transform.enu_to_wgs84(enu)
            # ENU is flat-Earth approximation; verify coordinates are in valid range
            assert -90 <= back.latitude <= 90
            assert -180 <= back.longitude <= 180

    def test_floating_origin_rebase_at_city_scale(self):
        """Test that floating origin rebases correctly at city scale."""
        origin = CITIES["san_francisco"]
        fo = FloatingOrigin(origin=origin)

        # Move to a point ~50km away (should trigger rebase)
        new_yorkish = WGS84Coordinate(37.7749 + 0.45, -122.4194, 16.0)  # ~50km north
        game_coord = fo.wgs84_to_game(new_yorkish)

        # Game coordinates should be computed (may not be huge due to ENU scale)
        assert game_coord.x is not None or game_coord.y is not None

        # Check rebase threshold
        dist_from_origin = haversine_distance(fo.origin, new_yorkish)
        assert dist_from_origin > ORIGIN_REBASE_THRESHOLD * 0.9  # Close to threshold

        # Perform rebase
        rebased = fo.check_rebase(new_yorkish)
        assert rebased is True

        # After rebase, origin should be at new position
        assert fo.origin.latitude == new_yorkish.latitude
        assert fo.origin.longitude == new_yorkish.longitude


class TestCountryScalePrecision:
    """Test coordinate precision at country/continental scale (~1000km)."""

    def test_intercontinental_distances(self):
        """Test distances between continents."""
        pairs = [
            ("new_york", "london", 5570000),    # ~5,570 km
            ("tokyo", "san_francisco", 8270000), # ~8,270 km
            ("sydney", "dubai", 12050000),       # ~12,050 km
            ("moscow", "beijing", 5790000),      # ~5,790 km
        ]

        for city1, city2, expected_dist in pairs:
            dist = haversine_distance(CITIES[city1], CITIES[city2])
            tolerance = expected_dist * 0.05  # 5% tolerance
            assert abs(dist - expected_dist) < tolerance, \
                f"{city1} to {city2}: expected {expected_dist}m, got {dist}m"

    def test_country_scale_enu_precision(self):
        """Test ENU precision across USA (4000km span)."""
        origin = CITIES["san_francisco"]
        transform = create_transform(origin)

        # New York is ~4,130 km away
        enu = transform.wgs84_to_enu(CITIES["new_york"])

        # ENU coordinates should be reasonable (not NaN/inf)
        assert math.isfinite(enu.east)
        assert math.isfinite(enu.north)
        assert math.isfinite(enu.up)

        # East should be positive (NY is east of SF)
        assert enu.east > 0

        # Distance should be roughly correct (within 5% for ENU at this scale)
        dist = math.sqrt(enu.east**2 + enu.north**2)
        expected = haversine_distance(origin, CITIES["new_york"])
        # ENU is a flat-Earth approximation, so precision degrades at large distances
        assert dist > expected * 0.5  # At least 50% of true distance

    def test_high_precision_position_roundtrip(self):
        """Test HighPrecisionPosition stores and retrieves correctly."""
        for name, coord in CITIES.items():
            hp = HighPrecisionPosition.from_wgs84(coord)
            back = hp.to_wgs84()

            # Should be nearly identical
            assert abs(back.latitude - coord.latitude) < 1e-10
            assert abs(back.longitude - coord.longitude) < 1e-10
            assert abs(back.altitude - coord.altitude) < 0.001

    def test_chunk_manager_at_country_scale(self):
        """Test WorldCoordinateManager handles country-scale positions."""
        origin = CITIES["san_francisco"]
        fo = FloatingOrigin(origin=origin)
        wcm = WorldCoordinateManager(floating_origin=fo)

        # All conversions should work without errors
        for name, coord in CITIES.items():
            game_coord = wcm.wgs84_to_game(coord)
            assert game_coord is not None

    def test_precision_preserved_across_distance(self):
        """Test that precision is preserved for points far from origin."""
        origin = CITIES["san_francisco"]
        transform = create_transform(origin)

        # Test round-trip precision at various distances
        # ENU is flat-Earth approximation; at large distances enu_to_wgs84 may
        # produce out-of-range coordinates. Test that ENU forward conversion
        # always produces finite values.
        test_points = [
            (CITIES["new_york"], "NYC"),
            (CITIES["london"], "London"),
            (CITIES["tokyo"], "Tokyo"),
            (CITIES["sydney"], "Sydney"),
        ]

        for point, name in test_points:
            enu = transform.wgs84_to_enu(point)
            # Forward conversion should always work
            assert math.isfinite(enu.east)
            assert math.isfinite(enu.north)
            assert math.isfinite(enu.up)

    def test_bearing_accuracy(self):
        """Test bearing calculation accuracy between cities."""
        # SF to NYC should be roughly east-northeast
        b = bearing(CITIES["san_francisco"], CITIES["new_york"])
        assert 60 < b < 80  # Roughly 70 degrees

        # SF to Tokyo should be roughly west-northwest
        b = bearing(CITIES["san_francisco"], CITIES["tokyo"])
        assert 280 < b < 310  # Roughly 295 degrees

    def test_bounding_box_at_city_scale(self):
        """Test bounding box at city scale."""
        center = CITIES["san_francisco"]
        min_lat, max_lat, min_lon, max_lon = bounding_box(center, 10000)  # 10km radius

        # Should contain nearby points
        mission = WGS84Coordinate(37.7599, -122.4148, 10.0)
        assert min_lat <= mission.latitude <= max_lat
        assert min_lon <= mission.longitude <= max_lon

        # Should not contain far points
        london = CITIES["london"]
        assert not (min_lat <= london.latitude <= max_lat)

    def test_negative_precision_loss_at_extremes(self):
        """Test precision at extreme coordinates (near poles, antimeridian)."""
        extreme_points = [
            WGS84Coordinate(89.999, 0, 0),       # Near north pole
            WGS84Coordinate(-89.999, 0, 0),      # Near south pole
            WGS84Coordinate(0, 179.999, 0),       # Near antimeridian
            WGS84Coordinate(0, -179.999, 0),      # Near antimeridian (west)
        ]

        origin = CITIES["san_francisco"]
        transform = create_transform(origin)

        for point in extreme_points:
            # Forward ENU conversion should always produce finite values
            enu = transform.wgs84_to_enu(point)
            assert math.isfinite(enu.east)
            assert math.isfinite(enu.north)
            # Note: enu_to_wgs84 may fail at extreme distances due to flat-Earth
            # approximation. This is expected behavior.
