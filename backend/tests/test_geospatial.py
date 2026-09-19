"""Tests for the geospatial coordinate system."""
import math
import pytest
from app.core.geospatial import (
    WGS84Coordinate,
    ENUVector,
    GameCoordinate,
    GeoTransform,
    create_transform,
    haversine_distance,
    bearing,
    bounding_box,
    _wgs84_to_ecef,
    _meters_per_degree_latitude,
    _meters_per_degree_longitude,
)


class TestWGS84Coordinate:
    def test_valid_creation(self):
        coord = WGS84Coordinate(latitude=40.7128, longitude=-74.0060, altitude=10.0)
        assert coord.latitude == 40.7128
        assert coord.longitude == -74.0060
        assert coord.altitude == 10.0

    def test_invalid_latitude(self):
        with pytest.raises(ValueError):
            WGS84Coordinate(latitude=91, longitude=0)

    def test_invalid_longitude(self):
        with pytest.raises(ValueError):
            WGS84Coordinate(latitude=0, longitude=181)

    def test_boundary_values(self):
        coord = WGS84Coordinate(latitude=90, longitude=180)
        assert coord.latitude == 90
        assert coord.longitude == 180

    def test_to_dict(self):
        coord = WGS84Coordinate(latitude=40.7128, longitude=-74.0060)
        d = coord.to_dict()
        assert d["lat"] == 40.7128
        assert d["lon"] == -74.0060
        assert d["alt"] == 0.0

    def test_from_dict(self):
        d = {"lat": 40.7128, "lon": -74.0060, "alt": 5.0}
        coord = WGS84Coordinate.from_dict(d)
        assert coord.latitude == 40.7128
        assert coord.longitude == -74.0060
        assert coord.altitude == 5.0

    def test_from_dict_alternative_keys(self):
        d = {"latitude": 40.7128, "longitude": -74.0060, "altitude": 5.0}
        coord = WGS84Coordinate.from_dict(d)
        assert coord.latitude == 40.7128


class TestHaversineDistance:
    def test_same_point(self):
        a = WGS84Coordinate(latitude=40.7128, longitude=-74.0060)
        b = WGS84Coordinate(latitude=40.7128, longitude=-74.0060)
        assert haversine_distance(a, b) == pytest.approx(0, abs=0.1)

    def test_known_distance_new_york_to_la(self):
        """New York to Los Angeles is approximately 3944 km."""
        nyc = WGS84Coordinate(latitude=40.7128, longitude=-74.0060)
        la = WGS84Coordinate(latitude=34.0522, longitude=-118.2437)
        dist = haversine_distance(nyc, la)
        assert 3900000 < dist < 4000000  # 3900-4000 km

    def test_known_distance_short(self):
        """Two points 1 degree apart at equator is approximately 111 km."""
        a = WGS84Coordinate(latitude=0, longitude=0)
        b = WGS84Coordinate(latitude=1, longitude=0)
        dist = haversine_distance(a, b)
        assert 110000 < dist < 112000


class TestBearing:
    def test_north(self):
        a = WGS84Coordinate(latitude=0, longitude=0)
        b = WGS84Coordinate(latitude=1, longitude=0)
        assert bearing(a, b) == pytest.approx(0, abs=1)

    def test_east(self):
        a = WGS84Coordinate(latitude=0, longitude=0)
        b = WGS84Coordinate(latitude=0, longitude=1)
        assert bearing(a, b) == pytest.approx(90, abs=1)

    def test_south(self):
        a = WGS84Coordinate(latitude=1, longitude=0)
        b = WGS84Coordinate(latitude=0, longitude=0)
        assert bearing(a, b) == pytest.approx(180, abs=1)

    def test_west(self):
        a = WGS84Coordinate(latitude=0, longitude=1)
        b = WGS84Coordinate(latitude=0, longitude=0)
        assert bearing(a, b) == pytest.approx(270, abs=1)


class TestGeoTransform:
    def test_origin_maps_to_zero(self):
        origin = WGS84Coordinate(latitude=40.7128, longitude=-74.0060)
        transform = create_transform(origin)
        game = transform.wgs84_to_game(origin)
        assert game.x == pytest.approx(0, abs=0.01)
        assert game.y == pytest.approx(0, abs=0.01)
        assert game.z == pytest.approx(0, abs=0.01)

    def test_north_displacement(self):
        """Moving north should increase z (game Z = north)."""
        origin = WGS84Coordinate(latitude=40.7128, longitude=-74.0060)
        transform = create_transform(origin)

        # Move ~100m north
        point = WGS84Coordinate(
            latitude=origin.latitude + 100 / 111320,
            longitude=origin.longitude,
        )
        game = transform.wgs84_to_game(point)
        assert game.z > 50  # Should be ~100m north
        assert game.z < 150
        assert abs(game.x) < 5  # Should not move east/west

    def test_east_displacement(self):
        """Moving east should increase x (game X = east)."""
        origin = WGS84Coordinate(latitude=40.7128, longitude=-74.0060)
        transform = create_transform(origin)

        # Move ~100m east
        meters_per_deg_lon = _meters_per_degree_longitude(origin.latitude)
        point = WGS84Coordinate(
            latitude=origin.latitude,
            longitude=origin.longitude + 100 / meters_per_deg_lon,
        )
        game = transform.wgs84_to_game(point)
        assert game.x > 50  # Should be ~100m east
        assert game.x < 150
        assert abs(game.z) < 5  # Should not move north/south

    def test_altitude(self):
        """Altitude should map to game Y."""
        origin = WGS84Coordinate(latitude=40.7128, longitude=-74.0060)
        transform = create_transform(origin)

        point = WGS84Coordinate(
            latitude=origin.latitude,
            longitude=origin.longitude,
            altitude=50.0,
        )
        game = transform.wgs84_to_game(point)
        assert game.y == pytest.approx(50, abs=1)

    def test_roundtrip(self):
        """Converting WGS84 → game → WGS84 should return close to original."""
        origin = WGS84Coordinate(latitude=40.7128, longitude=-74.0060)
        transform = create_transform(origin)

        original = WGS84Coordinate(
            latitude=40.7150,
            longitude=-74.0040,
            altitude=25.0,
        )

        game = transform.wgs84_to_game(original)
        recovered = transform.game_to_wgs84(game)

        assert recovered.latitude == pytest.approx(original.latitude, abs=0.0001)
        assert recovered.longitude == pytest.approx(original.longitude, abs=0.0001)
        assert recovered.altitude == pytest.approx(original.altitude, abs=1)


class TestBoundingBox:
    def test_bounding_box(self):
        center = WGS84Coordinate(latitude=40.7128, longitude=-74.0060)
        min_lat, max_lat, min_lon, max_lon = bounding_box(center, 1000)  # 1km

        # Should be roughly +/- 0.009 degrees
        assert min_lat < center.latitude < max_lat
        assert min_lon < center.longitude < max_lon
        assert (max_lat - min_lat) * 111000 == pytest.approx(2000, abs=200)
        assert (max_lon - min_lon) * 111000 * math.cos(math.radians(center.latitude)) == pytest.approx(2000, abs=200)


class TestMetersPerDegree:
    def test_equator(self):
        assert _meters_per_degree_latitude(0) == pytest.approx(111320, rel=0.01)
        assert _meters_per_degree_longitude(0) == pytest.approx(111320, rel=0.01)

    def test_latitude_longitude_differ_at_high_lat(self):
        """At high latitudes, longitude degrees are smaller."""
        m_per_lat = _meters_per_degree_latitude(60)
        m_per_lon = _meters_per_degree_longitude(60)
        assert m_per_lat == pytest.approx(111320, rel=0.01)
        assert m_per_lon < m_per_lat  # Longitude degrees shrink toward poles
