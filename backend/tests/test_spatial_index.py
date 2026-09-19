import pytest
from app.core.geospatial import WGS84Coordinate
from app.core.spatial_index import (
    compute_grid_cell_id,
    compute_candidate_cells,
    search_locations_sql,
    GridCell,
    update_location_grid_cell,
)


class TestGridCell:
    def test_from_coordinate(self):
        coord = WGS84Coordinate(40.7128, -74.0060)
        cell = GridCell.from_coordinate(coord, 100.0)
        assert isinstance(cell.lat_cell, int)
        assert isinstance(cell.lon_cell, int)

    def test_cell_id_format(self):
        cell = GridCell(lat_cell=407, lon_cell=-740)
        assert cell.cell_id == "407:-740"

    def test_from_id(self):
        cell = GridCell.from_id("407:-740")
        assert cell.lat_cell == 407
        assert cell.lon_cell == -740


class TestComputeGridCellId:
    def test_same_location_same_cell(self):
        coord = WGS84Coordinate(40.7128, -74.0060)
        id1 = compute_grid_cell_id(coord, 100.0)
        id2 = compute_grid_cell_id(coord, 100.0)
        assert id1 == id2

    def test_nearby_locations_same_cell(self):
        # Two points ~10m apart should be in same 100m cell
        coord1 = WGS84Coordinate(40.7128, -74.0060)
        coord2 = WGS84Coordinate(40.71285, -74.00605)
        id1 = compute_grid_cell_id(coord1, 100.0)
        id2 = compute_grid_cell_id(coord2, 100.0)
        assert id1 == id2

    def test_distant_locations_different_cells(self):
        # Two points ~1km apart should be in different 100m cells
        coord1 = WGS84Coordinate(40.7128, -74.0060)
        coord2 = WGS84Coordinate(40.7228, -74.0060)
        id1 = compute_grid_cell_id(coord1, 100.0)
        id2 = compute_grid_cell_id(coord2, 100.0)
        assert id1 != id2

    def test_large_cell_size(self):
        # With 1000m cells, nearby points should share cell
        coord1 = WGS84Coordinate(40.7128, -74.0060)
        coord2 = WGS84Coordinate(40.7135, -74.0065)
        id1 = compute_grid_cell_id(coord1, 1000.0)
        id2 = compute_grid_cell_id(coord2, 1000.0)
        assert id1 == id2

    def test_negative_coordinates(self):
        # Southern hemisphere, western hemisphere
        coord = WGS84Coordinate(-33.8688, 151.2093)  # Sydney
        cell_id = compute_grid_cell_id(coord, 100.0)
        assert ":" in cell_id
        lat_cell, lon_cell = cell_id.split(":")
        assert int(lat_cell) < 0
        assert int(lon_cell) > 0


class TestCandidateCells:
    def test_includes_center_cell(self):
        center = WGS84Coordinate(40.7128, -74.0060)
        cells = compute_candidate_cells(center, 100.0, 100.0)
        center_cell = compute_grid_cell_id(center, 100.0)
        assert center_cell in cells

    def test_includes_neighbor_cells(self):
        center = WGS84Coordinate(40.7128, -74.0060)
        cells = compute_candidate_cells(center, 200.0, 100.0)
        # Should include more than just center
        assert len(cells) > 1

    def test_radius_scales_candidates(self):
        center = WGS84Coordinate(40.7128, -74.0060)
        cells_small = compute_candidate_cells(center, 100.0, 100.0)
        cells_large = compute_candidate_cells(center, 500.0, 100.0)
        assert len(cells_large) > len(cells_small)

    def test_no_duplicates(self):
        center = WGS84Coordinate(40.7128, -74.0060)
        cells = compute_candidate_cells(center, 300.0, 100.0)
        assert len(cells) == len(set(cells))


class TestSearchLocationsSql:
    def test_returns_tuple(self):
        center = WGS84Coordinate(40.7128, -74.0060)
        result = search_locations_sql(center, 1000.0)
        assert len(result) == 5

    def test_bounding_box_valid(self):
        center = WGS84Coordinate(40.7128, -74.0060)
        cells, min_lat, max_lat, min_lon, max_lon = search_locations_sql(center, 1000.0)
        assert min_lat < center.latitude < max_lat
        assert min_lon < center.longitude < max_lon

    def test_bounding_box_radius(self):
        from app.core.geospatial import haversine_distance
        center = WGS84Coordinate(40.7128, -74.0060)
        _, min_lat, max_lat, min_lon, max_lon = search_locations_sql(center, 5000.0)
        # Verify bounding box corners are ~5km from center
        d_north = haversine_distance(center, WGS84Coordinate(max_lat, center.longitude))
        d_south = haversine_distance(center, WGS84Coordinate(min_lat, center.longitude))
        d_east = haversine_distance(center, WGS84Coordinate(center.latitude, max_lon))
        d_west = haversine_distance(center, WGS84Coordinate(center.latitude, min_lon))
        assert 4500 < d_north < 5500
        assert 4500 < d_south < 5500
        assert 4500 < d_east < 5500
        assert 4500 < d_west < 5500


class TestUpdateLocationGridCell:
    def test_returns_string(self):
        result = update_location_grid_cell(40.7128, -74.0060)
        assert isinstance(result, str)

    def test_matches_compute(self):
        lat, lon = 40.7128, -74.0060
        result = update_location_grid_cell(lat, lon)
        expected = compute_grid_cell_id(WGS84Coordinate(lat, lon))
        assert result == expected
