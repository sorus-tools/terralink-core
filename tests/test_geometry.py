from __future__ import annotations

import math

from terralink_core.geometry.compat import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsSpatialIndex,
    QgsVectorLayer,
)


def polygon(xmin: float, ymin: float, xmax: float, ymax: float) -> QgsGeometry:
    return QgsGeometry.fromPolygonXY(
        [
            [
                QgsPointXY(xmin, ymin),
                QgsPointXY(xmax, ymin),
                QgsPointXY(xmax, ymax),
                QgsPointXY(xmin, ymax),
                QgsPointXY(xmin, ymin),
            ]
        ]
    )


def test_corridor_operations_preserve_planar_cost_and_clip_semantics() -> None:
    source = polygon(0, 0, 10, 10)
    target = polygon(30, 0, 40, 10)
    shortest = source.shortestLine(target)
    corridor = shortest.buffer(2, 16)
    clipped = corridor.difference(source.combine(target))

    assert math.isclose(shortest.length(), 20.0, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(corridor.area(), 80.0 + math.pi * 4.0, rel_tol=0, abs_tol=0.2)
    assert clipped.intersection(source).area() == 0.0
    assert clipped.intersection(target).area() == 0.0
    assert 0.0 < clipped.area() < corridor.area()
    assert source.intersects(source.buffer(0.01, 8))


def test_nearest_point_is_on_receiver_and_spatial_index_keeps_input_order() -> None:
    first = polygon(0, 0, 10, 10)
    second = polygon(20, 0, 30, 10)
    closest_on_first = first.nearestPoint(second).asPoint()
    assert math.isclose(
        closest_on_first.distance(QgsPointXY(10, 0)), 0.0, abs_tol=1e-12
    )
    assert math.isclose(first.distance(second), 10.0, abs_tol=1e-12)

    features = []
    for fid, x in [(40, 4), (2, 0), (27, 2), (5, 7)]:
        feature = QgsFeature()
        feature.setId(fid)
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, 0)))
        features.append(feature)
    index = QgsSpatialIndex(
        features, flags=QgsSpatialIndex.Flag.FlagStoreFeatureGeometries
    )
    assert index.intersects(QgsRectangle(1, -1, 5, 1)) == [40, 27]
    assert index.geometry(27).asPoint() == QgsPointXY(2, 0)


def test_rectangle_growth_matches_qgis_including_negative_shrink() -> None:
    rectangle = QgsRectangle(0, 0, 10, 10)
    rectangle.grow(2)
    assert rectangle._bounds() == (-2.0, -2.0, 12.0, 12.0)
    rectangle.grow(-2)
    assert rectangle._bounds() == (0.0, 0.0, 10.0, 10.0)
    rectangle.grow(-6)
    assert rectangle.isEmpty()
    assert rectangle._bounds() == (6.0, 6.0, 4.0, 4.0)


def test_polygon_rings_and_multipart_access_match_qgis_shapes() -> None:
    with_hole = QgsGeometry.fromPolygonXY(
        [
            [
                QgsPointXY(0, 0),
                QgsPointXY(8, 0),
                QgsPointXY(8, 8),
                QgsPointXY(0, 8),
                QgsPointXY(0, 0),
            ],
            [
                QgsPointXY(2, 2),
                QgsPointXY(4, 2),
                QgsPointXY(4, 4),
                QgsPointXY(2, 4),
                QgsPointXY(2, 2),
            ],
        ]
    )
    assert not with_hole.isMultipart()
    rings = with_hole.asPolygon()
    assert len(rings) == 2
    assert rings[0][0] == rings[0][-1]
    assert rings[1][0] == rings[1][-1]
    assert math.isclose(with_hole.area(), 60.0)
    assert len(list(with_hole.vertices())) == 10

    multi = QgsGeometry(with_hole.constGet().union(polygon(20, 0, 21, 1).constGet()))
    assert multi.isMultipart()
    assert len(multi.asGeometryCollection()) == 2


def test_crs_transform_and_layer_adapter_feed_existing_loader_contract() -> None:
    source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    target_crs = QgsCoordinateReferenceSystem("EPSG:32630")
    transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
    point = transform.transform(QgsPointXY(-3.0, 51.0))
    assert 400_000 < point.x() < 600_000
    assert 5_500_000 < point.y() < 5_800_000
    projected_bounds = transform.transformBoundingBox(
        QgsRectangle(-3.1, 50.9, -2.9, 51.1)
    )
    assert projected_bounds.width() > 10_000
    assert projected_bounds.height() > 10_000

    feature = QgsFeature()
    feature.setId(12)
    feature.setGeometry(polygon(0, 0, 2, 2))
    feature.setAttributes([77])
    layer = QgsVectorLayer.from_features(
        [feature], crs="EPSG:3857", fields=[QgsField("patch_id", int)]
    )
    read_feature = next(layer.getFeatures())
    assert layer.crs().authid() == "EPSG:3857"
    assert layer.featureCount() == 1
    assert layer.name() == "input"
    assert layer.id().startswith("memory_")
    assert layer.source() == "memory:"
    assert read_feature["patch_id"] == 77
    assert read_feature.geometry().area() == 4.0


def test_make_valid_returns_new_geometry_and_qgis_smoothing_coordinates() -> None:
    bowtie = QgsGeometry.fromPolygonXY(
        [
            [
                QgsPointXY(0, 0),
                QgsPointXY(2, 2),
                QgsPointXY(0, 2),
                QgsPointXY(2, 0),
                QgsPointXY(0, 0),
            ]
        ]
    )
    repaired = bowtie.makeValid()
    assert not bowtie.isValid()
    assert repaired.isValid()
    assert not repaired.isEmpty()

    line = QgsGeometry.fromPolylineXY(
        [QgsPointXY(0, 0), QgsPointXY(2, 2), QgsPointXY(4, 0)]
    )
    smoothed = line.smooth(1, 0.25).asPolyline()
    assert smoothed == [
        QgsPointXY(0, 0),
        QgsPointXY(1.5, 1.5),
        QgsPointXY(2.5, 1.5),
        QgsPointXY(4, 0),
    ]
    # This square result was captured from the installed QGIS PyQGIS runtime.
    smooth_poly = polygon(0, 0, 4, 4).smooth(1, 0.25).asPolygon()[0]
    assert smooth_poly == [
        QgsPointXY(1, 0),
        QgsPointXY(3, 0),
        QgsPointXY(4, 1),
        QgsPointXY(4, 3),
        QgsPointXY(3, 4),
        QgsPointXY(1, 4),
        QgsPointXY(0, 3),
        QgsPointXY(0, 1),
        QgsPointXY(1, 0),
    ]


def test_densify_inserts_vertices_within_requested_spacing() -> None:
    line = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(10, 0)])
    points = line.densifyByDistance(3).asPolyline()
    assert len(points) == 5
    assert max(a.distance(b) for a, b in zip(points, points[1:])) <= 3.0


def test_default_point_is_empty_but_origin_is_not() -> None:
    assert QgsPointXY().isEmpty()
    assert QgsPointXY(0, 0).isEmpty() is False
    assert QgsPointXY(1, 2).isEmpty() is False


def test_planar_area_uses_qgis_edge_accumulation_for_large_coordinates() -> None:
    direct = QgsGeometry.fromPolylineXY(
        [QgsPointXY(500400, 5000100), QgsPointXY(500400, 5000300)]
    ).buffer(10, 16)
    routed_points = [QgsPointXY(500405, 5000095 + 10 * i) for i in range(21)]
    routed = QgsGeometry.fromPolylineXY(routed_points).smooth(3, 0.25).buffer(10, 16)

    # Captured from QGIS 3.44.7. Exact edge accumulation makes the mathematically
    # equal candidates distinguishable the same way the original engine does.
    assert math.isclose(direct.area(), 4313.654849037528, rel_tol=0, abs_tol=1e-9)
    assert routed.area() > direct.area()
