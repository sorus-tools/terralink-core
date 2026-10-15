"""Small PyQGIS-shaped geometry API backed by Shapely and pyproj.

This compatibility layer deliberately covers operations used by TerraLink's
existing vector implementation. It is not a general PyQGIS replacement. The
wrappers keep the original algorithm code callable while making the geometry
runtime independent of QGIS.
"""

from __future__ import annotations

import math
import itertools
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Iterable, Iterator, Optional, Sequence

from pyproj import CRS, Transformer
from shapely import from_wkb, make_valid, to_wkb, union_all
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
    box,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, transform as transform_geometry
from shapely.prepared import prep
from shapely.strtree import STRtree

_UNSET = object()


class QgsPointXY:
    """Immutable two-dimensional point with the PyQGIS accessor shape."""

    __slots__ = ("_x", "_y", "_empty")

    def __init__(self, x: Any = _UNSET, y: Any = _UNSET):
        empty = x is _UNSET and y is _UNSET
        if empty:
            x, y = 0.0, 0.0
        elif y is _UNSET and not isinstance(x, (int, float)):
            if isinstance(x, QgsPointXY):
                x, y, empty = x.x(), x.y(), x.isEmpty()
            elif isinstance(x, (tuple, list)) and len(x) >= 2:
                x, y = x[0], x[1]
            elif hasattr(x, "x") and hasattr(x, "y"):
                xv = x.x() if callable(x.x) else x.x
                yv = x.y() if callable(x.y) else x.y
                x, y = xv, yv
            else:
                raise TypeError(f"Cannot make a point from {type(x).__name__}")
        elif y is _UNSET:
            y = 0.0
        self._x = float(x)
        self._y = float(y)
        self._empty = bool(empty)

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y

    def distance(self, other: Any) -> float:
        other = _point_xy(other)
        return math.hypot(self._x - other.x(), self._y - other.y())

    def isEmpty(self) -> bool:
        return self._empty

    def __iter__(self) -> Iterator[float]:
        yield self._x
        yield self._y

    def __getitem__(self, index: int) -> float:
        return (self._x, self._y)[index]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, QgsPointXY):
            try:
                other = QgsPointXY(other)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return False
        return self._x == other.x() and self._y == other.y()

    def __hash__(self) -> int:
        return hash((self._x, self._y))

    def __repr__(self) -> str:
        return f"QgsPointXY({self._x!r}, {self._y!r})"


class QgsPoint(QgsPointXY):
    """Point class used by QGIS geometry-engine calls."""


def _point_xy(value: Any) -> QgsPointXY:
    if isinstance(value, QgsPointXY):
        return value
    return QgsPointXY(value)


def _xy(value: Any) -> tuple[float, float]:
    p = _point_xy(value)
    return p.x(), p.y()


class QgsRectangle:
    """Axis-aligned rectangle with QgsRectangle's bound methods."""

    __slots__ = ("_xmin", "_ymin", "_xmax", "_ymax", "_empty")

    def __init__(self, *args: Any):
        if len(args) == 1 and isinstance(args[0], QgsRectangle):
            other = args[0]
            self._xmin, self._ymin = other.xMinimum(), other.yMinimum()
            self._xmax, self._ymax = other.xMaximum(), other.yMaximum()
            self._empty = other.isEmpty()
        elif len(args) == 1 and isinstance(args[0], BaseGeometry):
            if args[0].is_empty:
                self._xmin = self._ymin = self._xmax = self._ymax = 0.0
                self._empty = True
            else:
                self._xmin, self._ymin, self._xmax, self._ymax = args[0].bounds
                self._empty = False
        elif len(args) == 4:
            x1, y1, x2, y2 = (float(v) for v in args)
            self._xmin, self._xmax = min(x1, x2), max(x1, x2)
            self._ymin, self._ymax = min(y1, y2), max(y1, y2)
            self._empty = False
        elif len(args) == 0:
            self._xmin = self._ymin = self._xmax = self._ymax = 0.0
            self._empty = True
        else:
            raise TypeError("QgsRectangle expects 0, 1, or 4 arguments")

    @classmethod
    def from_bounds(cls, bounds: Sequence[float]) -> "QgsRectangle":
        return cls(*bounds)

    def xMinimum(self) -> float:
        return self._xmin

    def yMinimum(self) -> float:
        return self._ymin

    def xMaximum(self) -> float:
        return self._xmax

    def yMaximum(self) -> float:
        return self._ymax

    def width(self) -> float:
        return 0.0 if self._empty else self._xmax - self._xmin

    def height(self) -> float:
        return 0.0 if self._empty else self._ymax - self._ymin

    def center(self) -> QgsPointXY:
        return QgsPointXY((self._xmin + self._xmax) / 2.0, (self._ymin + self._ymax) / 2.0)

    def isEmpty(self) -> bool:
        return self._empty

    def intersects(self, other: "QgsRectangle") -> bool:
        if self._empty or other.isEmpty():
            return False
        return not (
            self._xmax < other.xMinimum()
            or other.xMaximum() < self._xmin
            or self._ymax < other.yMinimum()
            or other.yMaximum() < self._ymin
        )

    def grow(self, delta: float) -> None:
        delta = float(delta)
        if self._empty:
            return
        self._xmin -= delta
        self._ymin -= delta
        self._xmax += delta
        self._ymax += delta
        if self._xmin > self._xmax or self._ymin > self._ymax:
            self._empty = True

    def combineExtentWith(self, other: Any) -> None:
        if isinstance(other, QgsRectangle):
            if other.isEmpty():
                return
            xmin, ymin, xmax, ymax = other.xMinimum(), other.yMinimum(), other.xMaximum(), other.yMaximum()
        elif isinstance(other, QgsPointXY):
            xmin = xmax = other.x()
            ymin = ymax = other.y()
        else:
            xmin, ymin, xmax, ymax = QgsGeometry(other).boundingBox()._bounds()
        if self._empty:
            self._xmin, self._ymin, self._xmax, self._ymax = xmin, ymin, xmax, ymax
            self._empty = False
        else:
            self._xmin = min(self._xmin, xmin)
            self._ymin = min(self._ymin, ymin)
            self._xmax = max(self._xmax, xmax)
            self._ymax = max(self._ymax, ymax)

    def _bounds(self) -> tuple[float, float, float, float]:
        return self._xmin, self._ymin, self._xmax, self._ymax

    def __repr__(self) -> str:
        return f"QgsRectangle{self._bounds()!r}"


class QgsGeometry:
    """Geometry wrapper implementing the PyQGIS operations used by TerraLink."""

    __slots__ = ("_geom",)

    def __init__(self, geometry: Any = None):
        if isinstance(geometry, QgsGeometry):
            self._geom = geometry._geom
        elif isinstance(geometry, BaseGeometry):
            self._geom = geometry
        elif geometry is None:
            self._geom = None
        else:
            raise TypeError(f"Cannot make QgsGeometry from {type(geometry).__name__}")

    @staticmethod
    def fromPointXY(point: Any) -> "QgsGeometry":
        return QgsGeometry(Point(_xy(point)))

    @staticmethod
    def fromPolylineXY(points: Iterable[Any]) -> "QgsGeometry":
        coords = [_xy(p) for p in points]
        if len(coords) < 2:
            return QgsGeometry(GeometryCollection())
        return QgsGeometry(LineString(coords))

    @staticmethod
    def fromPolygonXY(rings: Iterable[Iterable[Any]]) -> "QgsGeometry":
        rings_xy = [[_xy(p) for p in ring] for ring in rings]
        if not rings_xy or len(rings_xy[0]) < 3:
            return QgsGeometry(GeometryCollection())
        exterior = _closed_ring(rings_xy[0])
        holes = [_closed_ring(r) for r in rings_xy[1:] if len(r) >= 3]
        return QgsGeometry(Polygon(exterior, holes))

    @staticmethod
    def fromRect(rect: QgsRectangle) -> "QgsGeometry":
        if rect.isEmpty():
            return QgsGeometry(GeometryCollection())
        return QgsGeometry(box(*rect._bounds()))

    @staticmethod
    def fromWkb(wkb: bytes) -> "QgsGeometry":
        return QgsGeometry(from_wkb(wkb))

    @staticmethod
    def unaryUnion(geometries: Iterable[Any]) -> "QgsGeometry":
        geoms = [g._geom for g in geometries if isinstance(g, QgsGeometry) and not g.isEmpty()]
        if not geoms:
            return QgsGeometry(GeometryCollection())
        return QgsGeometry(union_all(geoms))

    @staticmethod
    def createGeometryEngine(geometry: Any) -> "QgsGeometryEngine":
        return QgsGeometryEngine(geometry)

    def isEmpty(self) -> bool:
        return self._geom is None or bool(self._geom.is_empty)

    def isNull(self) -> bool:
        return self._geom is None

    def __bool__(self) -> bool:
        return not self.isEmpty()

    def isValid(self) -> bool:
        return self._geom is not None and bool(self._geom.is_valid)

    def isMultipart(self) -> bool:
        return self._geom is not None and self._geom.geom_type in {
            "MultiPoint", "MultiLineString", "MultiPolygon", "GeometryCollection"
        }

    def constGet(self) -> Optional[BaseGeometry]:
        return self._geom

    def boundingBox(self) -> QgsRectangle:
        return QgsRectangle(self._geom) if self._geom is not None and not self._geom.is_empty else QgsRectangle()

    def area(self) -> float:
        return 0.0 if self._geom is None else _qgis_planar_area(self._geom)

    def length(self) -> float:
        return 0.0 if self._geom is None else float(self._geom.length)

    def distance(self, other: Any) -> float:
        target = _as_geometry(other)
        if self.isEmpty() or target.isEmpty():
            return 0.0
        return float(self._geom.distance(target._geom))

    def intersects(self, other: Any) -> bool:
        target = _as_geometry(other)
        return bool(self._geom is not None and target._geom is not None and self._geom.intersects(target._geom))

    def touches(self, other: Any) -> bool:
        target = _as_geometry(other)
        return bool(self._geom is not None and target._geom is not None and self._geom.touches(target._geom))

    def contains(self, other: Any) -> bool:
        target = _as_geometry(other)
        return bool(self._geom is not None and target._geom is not None and self._geom.contains(target._geom))

    def crosses(self, other: Any) -> bool:
        target = _as_geometry(other)
        return bool(self._geom is not None and target._geom is not None and self._geom.crosses(target._geom))

    def overlaps(self, other: Any) -> bool:
        target = _as_geometry(other)
        return bool(self._geom is not None and target._geom is not None and self._geom.overlaps(target._geom))

    def buffer(self, distance: float, segments: int = 8) -> "QgsGeometry":
        if self._geom is None:
            return QgsGeometry()
        return QgsGeometry(self._geom.buffer(float(distance), quad_segs=max(1, int(segments))))

    def intersection(self, other: Any) -> "QgsGeometry":
        return self._overlay(other, "intersection")

    def difference(self, other: Any) -> "QgsGeometry":
        return self._overlay(other, "difference")

    def union(self, other: Any) -> "QgsGeometry":
        return self.combine(other)

    def combine(self, other: Any) -> "QgsGeometry":
        return self._overlay(other, "union")

    def _overlay(self, other: Any, op: str) -> "QgsGeometry":
        target = _as_geometry(other)
        if self._geom is None or target._geom is None:
            return QgsGeometry()
        try:
            result = getattr(self._geom, op)(target._geom)
        except Exception:
            return QgsGeometry()
        return QgsGeometry(result)

    def makeValid(self) -> "QgsGeometry":
        if self._geom is None:
            return QgsGeometry()
        try:
            return QgsGeometry(make_valid(self._geom))
        except Exception:
            try:
                return QgsGeometry(self._geom.buffer(0))
            except Exception:
                return QgsGeometry()

    def nearestPoint(self, other: Any) -> "QgsGeometry":
        target = _as_geometry(other)
        if self._geom is None or target._geom is None or self.isEmpty() or target.isEmpty():
            return QgsGeometry()
        return QgsGeometry(nearest_points(self._geom, target._geom)[0])

    def shortestLine(self, other: Any) -> "QgsGeometry":
        target = _as_geometry(other)
        if self._geom is None or target._geom is None or self.isEmpty() or target.isEmpty():
            return QgsGeometry()
        start, end = nearest_points(self._geom, target._geom)
        return QgsGeometry(LineString([start.coords[0], end.coords[0]]))

    def centroid(self) -> "QgsGeometry":
        return QgsGeometry() if self._geom is None else QgsGeometry(self._geom.centroid)

    def boundary(self) -> "QgsGeometry":
        return QgsGeometry() if self._geom is None else QgsGeometry(self._geom.boundary)

    def interpolate(self, distance: float) -> "QgsGeometry":
        if self._geom is None or self.isEmpty():
            return QgsGeometry()
        if self._geom.geom_type not in {"LineString", "LinearRing", "MultiLineString"}:
            return QgsGeometry()
        return QgsGeometry(self._geom.interpolate(float(distance)))

    def densifyByDistance(self, distance: float) -> "QgsGeometry":
        if self._geom is None or distance <= 0:
            return QgsGeometry(self)
        return QgsGeometry(_densify(self._geom, float(distance)))

    def smooth(self, iterations: int = 1, offset: float = 0.25, *args: Any, **kwargs: Any) -> "QgsGeometry":
        if args or kwargs:
            raise NotImplementedError("QGIS smooth options beyond iterations and offset are not implemented")
        if self._geom is None or self.isEmpty() or int(iterations) <= 0:
            return QgsGeometry(self)
        return QgsGeometry(_chaikin(self._geom, int(iterations), float(offset)))

    def asPoint(self) -> QgsPointXY:
        if self._geom is not None and self._geom.geom_type == "Point" and not self._geom.is_empty:
            return QgsPointXY(self._geom.x, self._geom.y)
        return QgsPointXY()

    def asPolyline(self) -> list[QgsPointXY]:
        if self._geom is None or self._geom.geom_type not in {"LineString", "LinearRing"}:
            return []
        return [QgsPointXY(c[0], c[1]) for c in self._geom.coords]

    def asPolygon(self) -> list[list[QgsPointXY]]:
        if self._geom is None or self._geom.geom_type != "Polygon":
            return []
        return [
            [QgsPointXY(c[0], c[1]) for c in self._geom.exterior.coords],
            *[[QgsPointXY(c[0], c[1]) for c in ring.coords] for ring in self._geom.interiors],
        ]

    def asMultiPolygon(self) -> list[list[list[QgsPointXY]]]:
        if self._geom is None:
            return []
        polygons = list(self._geom.geoms) if self._geom.geom_type == "MultiPolygon" else []
        return [QgsGeometry(p).asPolygon() for p in polygons]

    def asGeometryCollection(self) -> list["QgsGeometry"]:
        if self._geom is None:
            return []
        if self._geom.geom_type.startswith("Multi") or self._geom.geom_type == "GeometryCollection":
            return [QgsGeometry(g) for g in self._geom.geoms]
        return [QgsGeometry(self._geom)]

    def vertices(self) -> Iterator[QgsPointXY]:
        if self._geom is None or self._geom.is_empty:
            return
        for x, y, *_ in _all_coordinates(self._geom):
            yield QgsPointXY(x, y)

    def asWkb(self) -> bytes:
        return b"" if self._geom is None else bytes(to_wkb(self._geom))

    def transform(self, coordinate_transform: "QgsCoordinateTransform") -> int:
        if self._geom is None or self._geom.is_empty:
            return 0
        self._geom = transform_geometry(coordinate_transform._transform_xy, self._geom)
        return 0

    def __repr__(self) -> str:
        return "QgsGeometry(NULL)" if self._geom is None else f"QgsGeometry({self._geom.wkt})"


def _as_geometry(value: Any) -> QgsGeometry:
    if isinstance(value, QgsGeometry):
        return value
    if isinstance(value, BaseGeometry):
        return QgsGeometry(value)
    if isinstance(value, QgsPointXY):
        return QgsGeometry.fromPointXY(value)
    raise TypeError(f"Expected geometry or point, got {type(value).__name__}")


def _closed_ring(coords: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if coords and coords[0] != coords[-1]:
        return [*coords, coords[0]]
    return coords


def _all_coordinates(geom: BaseGeometry) -> Iterator[tuple[float, ...]]:
    kind = geom.geom_type
    if kind == "Point":
        if not geom.is_empty:
            yield tuple(geom.coords[0])
    elif kind in {"LineString", "LinearRing"}:
        yield from geom.coords
    elif kind == "Polygon":
        yield from geom.exterior.coords
        for ring in geom.interiors:
            yield from ring.coords
    elif hasattr(geom, "geoms"):
        for part in geom.geoms:
            yield from _all_coordinates(part)


def _qgis_planar_area(geom: BaseGeometry) -> float:
    """Match QgsCurvePolygon/QgsLineString's planar area accumulation.

    QGIS sums each directed edge as ``prevX * (y - prevY) - prevY * (x -
    prevX)`` and halves the result. That operation order can affect area ties
    for large projected coordinates, so Shapely's GEOS area result is not a
    drop-in replacement for the active engine's ``QgsGeometry.area()`` calls.
    """

    def ring_area(ring: Any) -> float:
        coordinates = iter(ring.coords)
        try:
            previous_x, previous_y = next(coordinates)[:2]
        except StopIteration:
            return 0.0
        total = 0.0
        for coordinate in coordinates:
            x, y = coordinate[:2]
            total += previous_x * (y - previous_y) - previous_y * (x - previous_x)
            previous_x, previous_y = x, y
        return abs(total * 0.5)

    kind = geom.geom_type
    if kind == "Polygon":
        return ring_area(geom.exterior) - sum(ring_area(ring) for ring in geom.interiors)
    if kind in {"MultiPolygon", "GeometryCollection"}:
        return sum(_qgis_planar_area(part) for part in geom.geoms)
    return 0.0


def _densify(geom: BaseGeometry, spacing: float) -> BaseGeometry:
    def line(coords: Iterable[Sequence[float]], closed: bool = False) -> list[tuple[float, ...]]:
        points = [tuple(c) for c in coords]
        out: list[tuple[float, ...]] = []
        for a, b in zip(points, points[1:]):
            out.append(a)
            d = math.hypot(b[0] - a[0], b[1] - a[1])
            count = max(0, int(math.ceil(d / spacing)) - 1)
            for i in range(1, count + 1):
                t = i / (count + 1)
                out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(min(len(a), len(b)))))
        if points:
            out.append(points[-1])
        if closed and out and out[0] != out[-1]:
            out.append(out[0])
        return out

    kind = geom.geom_type
    if kind in {"LineString", "LinearRing"}:
        result = line(geom.coords, kind == "LinearRing")
        return LineString(result) if kind == "LineString" else Polygon(result).exterior
    if kind == "Polygon":
        return Polygon(line(geom.exterior.coords, True), [line(r.coords, True) for r in geom.interiors])
    if kind == "MultiPolygon":
        return MultiPolygon([_densify(p, spacing) for p in geom.geoms])
    if kind == "MultiLineString":
        return MultiLineString([_densify(l, spacing) for l in geom.geoms])
    if kind == "GeometryCollection":
        return GeometryCollection([_densify(g, spacing) for g in geom.geoms])
    return geom


def _chaikin(geom: BaseGeometry, iterations: int, offset: float) -> BaseGeometry:
    """QGIS-style Chaikin smoothing; open-line endpoints are retained."""
    offset = min(max(offset, 0.0), 0.5)

    def smooth_ring(coords: Iterable[Sequence[float]], closed: bool) -> list[tuple[float, ...]]:
        pts = [tuple(c) for c in coords]
        if closed and pts and pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) < 3:
            return _closed_ring(pts) if closed else pts
        for _ in range(iterations):
            nxt: list[tuple[float, ...]] = []
            if not closed:
                nxt.append(pts[0])
                for i in range(1, len(pts) - 1):
                    prev, cur, following = pts[i - 1], pts[i], pts[i + 1]
                    q = tuple((1.0 - offset) * cur[k] + offset * prev[k] for k in range(min(len(cur), len(prev))))
                    r = tuple((1.0 - offset) * cur[k] + offset * following[k] for k in range(min(len(cur), len(following))))
                    nxt.extend((q, r))
                nxt.append(pts[-1])
            else:
                pairs: list[tuple[tuple[float, ...], tuple[float, ...]]] = []
                for i, cur in enumerate(pts):
                    prev, following = pts[i - 1], pts[(i + 1) % len(pts)]
                    q = tuple((1.0 - offset) * cur[k] + offset * prev[k] for k in range(min(len(cur), len(prev))))
                    r = tuple((1.0 - offset) * cur[k] + offset * following[k] for k in range(min(len(cur), len(following))))
                    pairs.append((q, r))
                # QGIS starts each smoothed ring with the point immediately
                # after its input start vertex, then emits pairs around the
                # remaining vertices and closes with the point before it.
                nxt.append(pairs[0][1])
                for q, r in pairs[1:]:
                    nxt.extend((q, r))
                nxt.append(pairs[0][0])
            pts = nxt
        return _closed_ring(pts) if closed else pts

    kind = geom.geom_type
    if kind in {"LineString", "LinearRing"}:
        return LineString(smooth_ring(geom.coords, False))
    if kind == "Polygon":
        ext = smooth_ring(geom.exterior.coords, True)
        holes = [smooth_ring(r.coords, True) for r in geom.interiors]
        return Polygon(ext, holes)
    if kind == "MultiLineString":
        return MultiLineString([_chaikin(g, iterations, offset) for g in geom.geoms])
    if kind == "MultiPolygon":
        return MultiPolygon([_chaikin(g, iterations, offset) for g in geom.geoms])
    if kind == "GeometryCollection":
        return GeometryCollection([_chaikin(g, iterations, offset) for g in geom.geoms])
    return geom


class QgsGeometryEngine:
    def __init__(self, geometry: Any):
        self._geom = geometry._geom if isinstance(geometry, QgsGeometry) else geometry
        self._prepared = None

    def prepareGeometry(self) -> None:
        if self._geom is not None and not self._geom.is_empty:
            self._prepared = prep(self._geom)

    def intersects(self, other: Any) -> bool:
        target = other._geom if isinstance(other, QgsGeometry) else other
        if self._geom is None or target is None:
            return False
        return bool((self._prepared or self._geom).intersects(target))

    def touches(self, other: Any) -> bool:
        target = other._geom if isinstance(other, QgsGeometry) else other
        if self._geom is None or target is None:
            return False
        # Prepared geometry exposes touches in current Shapely 2.x.
        return bool((self._prepared or self._geom).touches(target))

    def contains(self, other: Any) -> bool:
        target = other._geom if isinstance(other, QgsGeometry) else other
        if self._geom is None or target is None:
            return False
        return bool((self._prepared or self._geom).contains(target))


class QgsCoordinateReferenceSystem:
    def __init__(self, authid: Any = ""):
        self._crs: Optional[CRS]
        try:
            self._crs = CRS.from_user_input(authid) if authid else None
        except Exception:
            self._crs = None

    def isValid(self) -> bool:
        return self._crs is not None

    def isGeographic(self) -> bool:
        return bool(self._crs is not None and self._crs.is_geographic)

    def authid(self) -> str:
        if self._crs is None:
            return ""
        authority = self._crs.to_authority()
        return f"{authority[0]}:{authority[1]}" if authority else (self._crs.to_string() or "")

    def toWkt(self) -> str:
        return "" if self._crs is None else self._crs.to_wkt()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, QgsCoordinateReferenceSystem) and self._crs == other._crs


class QgsCoordinateTransform:
    def __init__(self, source: QgsCoordinateReferenceSystem, destination: QgsCoordinateReferenceSystem, project: Any = None):
        if not source.isValid() or not destination.isValid():
            raise ValueError("Both source and destination CRS must be valid")
        self.sourceCrs = source
        self.destinationCrs = destination
        self._transformer = Transformer.from_crs(source._crs, destination._crs, always_xy=True)

    def _transform_xy(self, x: Any, y: Any, z: Any = None) -> Any:
        return self._transformer.transform(x, y, z) if z is not None else self._transformer.transform(x, y)

    def transform(self, point: Any) -> QgsPointXY:
        p = _point_xy(point)
        x, y = self._transform_xy(p.x(), p.y())
        return QgsPointXY(x, y)

    def transformBoundingBox(self, rectangle: QgsRectangle) -> QgsRectangle:
        if rectangle.isEmpty():
            return QgsRectangle()
        bounds = self._transformer.transform_bounds(*rectangle._bounds(), densify_pts=21)
        return QgsRectangle(*bounds)


class QgsProject:
    _singleton: Optional["QgsProject"] = None

    def __init__(self):
        self._layers: dict[str, QgsVectorLayer] = {}

    @classmethod
    def instance(cls) -> "QgsProject":
        if cls._singleton is None:
            cls._singleton = cls()
        return cls._singleton

    def addMapLayer(self, layer: "QgsVectorLayer", addToLegend: bool = True) -> "QgsVectorLayer":
        self._layers[layer.id()] = layer
        return layer

    def removeMapLayer(self, layer_or_id: Any) -> bool:
        layer_id = layer_or_id.id() if hasattr(layer_or_id, "id") else str(layer_or_id)
        return self._layers.pop(layer_id, None) is not None

    def mapLayer(self, layer_id: str) -> Optional["QgsVectorLayer"]:
        return self._layers.get(str(layer_id))

    def mapLayers(self) -> dict[str, "QgsVectorLayer"]:
        return dict(self._layers)


class QgsFeature:
    def __init__(self, feature: Optional["QgsFeature"] = None):
        self._id = -1
        self._geometry = QgsGeometry()
        self._attributes: list[Any] = []
        if isinstance(feature, QgsFeature):
            self._id = feature.id()
            self._geometry = QgsGeometry(feature.geometry())
            self._attributes = list(feature._attributes)

    def setGeometry(self, geometry: Any) -> None:
        self._geometry = QgsGeometry(geometry)

    def geometry(self) -> QgsGeometry:
        return QgsGeometry(self._geometry)

    def setId(self, feature_id: int) -> None:
        self._id = int(feature_id)

    def id(self) -> int:
        return self._id

    def setAttributes(self, values: Sequence[Any]) -> None:
        self._attributes = list(values)

    def setAttribute(self, key: Any, value: Any) -> bool:
        if isinstance(key, int):
            while len(self._attributes) <= key:
                self._attributes.append(None)
            self._attributes[key] = value
            return True
        if isinstance(key, str) and hasattr(self, "_field_names"):
            return self.setAttribute(self._field_names.index(key), value)
        return False

    def attribute(self, key: Any) -> Any:
        return self[key]

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._attributes[key]
        if isinstance(key, str) and hasattr(self, "_field_names"):
            return self._attributes[self._field_names.index(key)]
        raise KeyError(key)


class QgsField:
    def __init__(self, name: str, field_type: Any = None):
        self._name = str(name)
        self._type = field_type

    def name(self) -> str:
        return self._name


class QgsFields(list):
    def indexOf(self, name: str) -> int:
        for index, item in enumerate(self):
            if item.name() == name:
                return index
        return -1


class QgsVectorLayer:
    """In-memory input adapter; file I/O belongs to the standalone pipeline."""

    _next_id = itertools.count(1)

    def __init__(self, source: Any = None, name: str = "", provider: str = "memory", *, crs: Any = "EPSG:3857", fields: Optional[Sequence[Any]] = None):
        self._features: list[QgsFeature] = []
        self._crs = crs if isinstance(crs, QgsCoordinateReferenceSystem) else QgsCoordinateReferenceSystem(crs)
        self._fields = QgsFields(fields or [])
        self._name = str(name or "input")
        self._id = f"memory_{next(self._next_id)}"
        self._source = str(source) if isinstance(source, (str, bytes)) else "memory:"
        if source is not None and not isinstance(source, (str, bytes)):
            for sequence_index, feature in enumerate(source):
                copied = QgsFeature(feature)
                if copied.id() < 0:
                    copied.setId(sequence_index)
                copied._field_names = [field.name() if hasattr(field, "name") else str(field) for field in self._fields]
                self._features.append(copied)

    @classmethod
    def from_features(
        cls,
        features: Iterable[QgsFeature],
        *,
        crs: Any = "EPSG:3857",
        fields: Optional[Sequence[Any]] = None,
        name: str = "input",
    ) -> "QgsVectorLayer":
        return cls(features, name, "memory", crs=crs, fields=fields)

    @classmethod
    def from_geometries(
        cls,
        geometries: Iterable[Any],
        *,
        crs: Any = "EPSG:3857",
        name: str = "input",
    ) -> "QgsVectorLayer":
        features = []
        for fid, geometry in enumerate(geometries):
            feature = QgsFeature()
            feature.setId(fid)
            feature.setGeometry(geometry)
            features.append(feature)
        return cls(features, name, "memory", crs=crs)

    def getFeatures(self) -> Iterator[QgsFeature]:
        return iter(self._features)

    def fields(self) -> QgsFields:
        return self._fields

    def crs(self) -> QgsCoordinateReferenceSystem:
        return self._crs

    def extent(self) -> QgsRectangle:
        extent = QgsRectangle()
        for feature in self._features:
            extent.combineExtentWith(feature.geometry().boundingBox())
        return extent

    def featureCount(self) -> int:
        return len(self._features)

    def name(self) -> str:
        return self._name

    def id(self) -> str:
        return self._id

    def source(self) -> str:
        return self._source

    def wkbType(self) -> int:
        return self.geometryType()

    def isValid(self) -> bool:
        return True

    def geometryType(self) -> int:
        for feature in self._features:
            geom = feature.geometry().constGet()
            if geom is not None:
                if "Polygon" in geom.geom_type:
                    return QgsWkbTypes.GeometryType.PolygonGeometry
                if "Line" in geom.geom_type:
                    return QgsWkbTypes.GeometryType.LineGeometry
                if "Point" in geom.geom_type:
                    return QgsWkbTypes.GeometryType.PointGeometry
        return QgsWkbTypes.GeometryType.UnknownGeometry


class QgsSpatialIndex:
    """Bounding-box index preserving feature insertion order in query results."""

    class Flag(IntEnum):
        FlagStoreFeatureGeometries = 1

    def __init__(self, features: Optional[Iterable[QgsFeature]] = None, flags: Any = None):
        self._ids: list[int] = []
        self._geometries: dict[int, QgsGeometry] = {}
        self._tree: Optional[STRtree] = None
        self._tree_ids: list[int] = []
        if features is not None:
            self.addFeatures(features)

    def addFeature(self, feature: QgsFeature) -> bool:
        fid = int(feature.id())
        if fid in self._geometries:
            return False
        geom = feature.geometry()
        self._ids.append(fid)
        self._geometries[fid] = geom
        self._rebuild()
        return True

    def addFeatures(self, features: Iterable[QgsFeature]) -> bool:
        changed = False
        for feature in features:
            fid = int(feature.id())
            if fid in self._geometries:
                continue
            self._ids.append(fid)
            self._geometries[fid] = feature.geometry()
            changed = True
        if changed:
            self._rebuild()
        return changed

    def _rebuild(self) -> None:
        usable = [(fid, geom.constGet()) for fid, geom in self._geometries.items() if not geom.isEmpty()]
        self._tree_ids = [fid for fid, _ in usable]
        self._tree = STRtree([geom for _, geom in usable]) if usable else None

    def intersects(self, rectangle: QgsRectangle) -> list[int]:
        if rectangle is None or rectangle.isEmpty() or self._tree is None:
            return []
        query = box(*rectangle._bounds())
        queried = self._tree.query(query)
        matches = {self._tree_ids[int(i)] for i in queried}
        # QGIS returns index hits in its insertion order for the common addFeatures
        # path. This is material for deterministic tie handling in legacy loops.
        return [fid for fid in self._ids if fid in matches]

    def geometry(self, feature_id: int) -> QgsGeometry:
        return QgsGeometry(self._geometries.get(int(feature_id), QgsGeometry()))

    def deleteFeature(self, feature: Any) -> bool:
        fid = int(feature.id() if hasattr(feature, "id") else feature)
        if fid not in self._geometries:
            return False
        del self._geometries[fid]
        self._ids.remove(fid)
        self._rebuild()
        return True

    def count(self) -> int:
        return len(self._ids)


class QgsWkbTypes:
    class GeometryType(IntEnum):
        UnknownGeometry = 0
        PointGeometry = 1
        LineGeometry = 2
        PolygonGeometry = 3
        NullGeometry = 4

    @staticmethod
    def geometryType(wkb_type: Any) -> int:
        return int(wkb_type)


class _MessageLevel(IntEnum):
    Info = 0
    Warning = 1
    Critical = 2


class Qgis:
    MessageLevel = _MessageLevel


class QgsApplication:
    @staticmethod
    def messageLog() -> Any:
        class _Log:
            @staticmethod
            def logMessage(message: str, tag: str = "", level: Any = None) -> None:
                print(f"{tag}: {message}")
        return _Log()


class QgsVectorFileWriter:
    class SaveVectorOptions:
        pass


class QVariant:
    String = str
    Int = int
    Double = float
    Bool = bool
    Date = object
    DateTime = object


class QUrl:
    @staticmethod
    def fromLocalFile(path: str) -> str:
        return path


__all__ = [
    "Qgis", "QgsApplication", "QgsCoordinateReferenceSystem", "QgsCoordinateTransform",
    "QgsFeature", "QgsField", "QgsFields", "QgsGeometry", "QgsGeometryEngine",
    "QgsPoint", "QgsPointXY", "QgsProject", "QgsRectangle", "QgsSpatialIndex",
    "QgsVectorFileWriter", "QgsVectorLayer", "QgsWkbTypes", "QUrl", "QVariant",
]
