"""pydantic models for GeoJSON Geometry objects."""
from __future__ import annotations

import abc
import warnings
from typing import Any, Iterator, List, Literal, Optional, Union

from pydantic import BaseModel, Field, ValidationError, validator
from pydantic.error_wrappers import ErrorWrapper
from typing_extensions import Annotated

from geojson_pydantic.geo_interface import GeoInterfaceMixin
from geojson_pydantic.types import (
    BBox,
    LinearRing,
    LineStringCoords,
    MultiLineStringCoords,
    MultiPointCoords,
    MultiPolygonCoords,
    PolygonCoords,
    Position,
)


def _position_wkt_coordinates(coordinates: Position, force_z: bool = False) -> str:
    """Converts a Position to WKT Coordinates."""
    wkt_coordinates = " ".join(str(number) for number in coordinates)
    if force_z and len(coordinates) < 3:
        wkt_coordinates += " 0.0"
    return wkt_coordinates


def _position_has_z(position: Position) -> bool:
    return len(position) == 3


def _position_list_wkt_coordinates(
    coordinates: List[Position], force_z: bool = False
) -> str:
    """Converts a list of Positions to WKT Coordinates."""
    return ", ".join(
        _position_wkt_coordinates(position, force_z) for position in coordinates
    )


def _position_list_has_z(positions: List[Position]) -> bool:
    """Checks if any position in a list has a Z."""
    return any(_position_has_z(position) for position in positions)


def _lines_wtk_coordinates(
    coordinates: List[LineStringCoords], force_z: bool = False
) -> str:
    """Converts lines to WKT Coordinates."""
    return ", ".join(
        f"({_position_list_wkt_coordinates(line, force_z)})" for line in coordinates
    )


def _lines_has_z(lines: List[LineStringCoords]) -> bool:
    """Checks if any position in a list has a Z."""
    return any(
        _position_has_z(position) for positions in lines for position in positions
    )


def _polygons_wkt_coordinates(
    coordinates: List[PolygonCoords], force_z: bool = False
) -> str:
    return ",".join(
        f"({_lines_wtk_coordinates(polygon, force_z)})" for polygon in coordinates
    )


class _GeometryBase(BaseModel, abc.ABC, GeoInterfaceMixin):
    """Base class for geometry models"""

    type: str
    coordinates: Any
    bbox: Optional[BBox] = None

    @abc.abstractmethod
    def __wkt_coordinates__(self, coordinates: Any, force_z: bool) -> str:
        """return WKT coordinates."""
        ...

    @property
    @abc.abstractmethod
    def has_z(self) -> bool:
        """Checks if any coordinate has a Z value."""
        ...

    @property
    def wkt(self) -> str:
        """Return the Well Known Text representation."""
        # Start with the WKT Type
        wkt = self.type.upper()
        has_z = self.has_z
        if self.coordinates:
            # If any of the coordinates have a Z add a "Z" to the WKT
            wkt += " Z " if has_z else " "
            # Add the rest of the WKT inside parentheses
            wkt += f"({self.__wkt_coordinates__(self.coordinates, force_z=has_z)})"
        else:
            # Otherwise it will be "EMPTY"
            wkt += " EMPTY"

        return wkt


class Point(_GeometryBase):
    """Point Model"""

    type: Literal["Point"]
    coordinates: Position

    def __wkt_coordinates__(self, coordinates: Any, force_z: bool) -> str:
        """return WKT coordinates."""
        return _position_wkt_coordinates(coordinates, force_z)

    @property
    def has_z(self) -> bool:
        """Checks if any coordinate has a Z value."""
        return _position_has_z(self.coordinates)


class MultiPoint(_GeometryBase):
    """MultiPoint Model"""

    type: Literal["MultiPoint"]
    coordinates: MultiPointCoords

    def __wkt_coordinates__(self, coordinates: Any, force_z: bool) -> str:
        """return WKT coordinates."""
        return _position_list_wkt_coordinates(coordinates, force_z)

    @property
    def has_z(self) -> bool:
        """Checks if any coordinate has a Z value."""
        return _position_list_has_z(self.coordinates)


class LineString(_GeometryBase):
    """LineString Model"""

    type: Literal["LineString"]
    coordinates: LineStringCoords

    def __wkt_coordinates__(self, coordinates: Any, force_z: bool) -> str:
        """return WKT coordinates."""
        return _position_list_wkt_coordinates(coordinates, force_z)

    @property
    def has_z(self) -> bool:
        """Checks if any coordinate has a Z value."""
        return _position_list_has_z(self.coordinates)


class MultiLineString(_GeometryBase):
    """MultiLineString Model"""

    type: Literal["MultiLineString"]
    coordinates: MultiLineStringCoords

    def __wkt_coordinates__(self, coordinates: Any, force_z: bool) -> str:
        """return WKT coordinates."""
        return _lines_wtk_coordinates(coordinates, force_z)

    @property
    def has_z(self) -> bool:
        """Checks if any coordinate has a Z value."""
        return _lines_has_z(self.coordinates)


class Polygon(_GeometryBase):
    """Polygon Model"""

    type: Literal["Polygon"]
    coordinates: PolygonCoords

    def __wkt_coordinates__(self, coordinates: Any, force_z: bool) -> str:
        """return WKT coordinates."""
        return _lines_wtk_coordinates(coordinates, force_z)

    @validator("coordinates")
    def check_closure(cls, coordinates: List) -> List:
        """Validate that Polygon is closed (first and last coordinate are the same)."""
        if any([ring[-1] != ring[0] for ring in coordinates]):
            raise ValueError("All linear rings have the same start and end coordinates")

        return coordinates

    @property
    def exterior(self) -> Union[LinearRing, None]:
        """Return the exterior Linear Ring of the polygon."""
        return self.coordinates[0] if self.coordinates else None

    @property
    def interiors(self) -> Iterator[LinearRing]:
        """Interiors (Holes) of the polygon."""
        yield from (
            interior for interior in self.coordinates[1:] if len(self.coordinates) > 1
        )

    @property
    def has_z(self) -> bool:
        """Checks if any coordinates have a Z value."""
        return _lines_has_z(self.coordinates)

    @classmethod
    def from_bounds(
        cls, xmin: float, ymin: float, xmax: float, ymax: float
    ) -> "Polygon":
        """Create a Polygon geometry from a boundingbox."""
        return cls(
            type="Polygon",
            coordinates=[
                [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)]
            ],
        )


class MultiPolygon(_GeometryBase):
    """MultiPolygon Model"""

    type: Literal["MultiPolygon"]
    coordinates: MultiPolygonCoords

    def __wkt_coordinates__(self, coordinates: Any, force_z: bool) -> str:
        """return WKT coordinates."""
        return _polygons_wkt_coordinates(coordinates, force_z)

    @property
    def has_z(self) -> bool:
        """Checks if any coordinates have a Z value."""
        return any(_lines_has_z(polygon) for polygon in self.coordinates)

    @validator("coordinates")
    def check_closure(cls, coordinates: List) -> List:
        """Validate that Polygon is closed (first and last coordinate are the same)."""
        if any([ring[-1] != ring[0] for polygon in coordinates for ring in polygon]):
            raise ValueError("All linear rings have the same start and end coordinates")

        return coordinates


Geometry = Annotated[
    Union[Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon],
    Field(discriminator="type"),
]


class GeometryCollection(BaseModel, GeoInterfaceMixin):
    """GeometryCollection Model"""

    type: Literal["GeometryCollection"]
    geometries: List[Union[Geometry, GeometryCollection]]
    bbox: Optional[BBox] = None

    def __iter__(self) -> Iterator[Union[Geometry, GeometryCollection]]:  # type: ignore [override]
        """iterate over geometries"""
        return iter(self.geometries)

    def __len__(self) -> int:
        """return geometries length"""
        return len(self.geometries)

    def __getitem__(self, index: int) -> Union[Geometry, GeometryCollection]:
        """get geometry at a given index"""
        return self.geometries[index]

    @property
    def wkt(self) -> str:
        """Return the Well Known Text representation."""
        # Each geometry will check its own coordinates for Z and include "Z" in the wkt
        # if necessary. Rather than looking at the coordinates for each of the geometries
        # again, we can just get the wkt from each of them and check if there is a Z
        # anywhere in the text.

        # Get the wkt from each of the geometries in the collection
        geometries = (
            f'({", ".join(geom.wkt for geom in self.geometries)})'
            if self.geometries
            else "EMPTY"
        )
        # If any of them contain `Z` add Z to the output wkt
        z = " Z " if "Z" in geometries else " "
        return f"{self.type.upper()}{z}{geometries}"

    @validator("geometries")
    def check_geometries(cls, geometries: List) -> List:
        """Add warnings for conditions the spec does not explicitly forbid."""
        if len(geometries) == 1:
            warnings.warn(
                "GeometryCollection should not be used for single geometries."
            )
        if any(geom.type == "GeometryCollection" for geom in geometries):
            warnings.warn(
                "GeometryCollection should not be used for nested GeometryCollections."
            )
        if len(set(geom.type for geom in geometries)) == 1:
            warnings.warn(
                "GeometryCollection should not be used for homogeneous collections."
            )
        return geometries


def parse_geometry_obj(obj: Any) -> Geometry:
    """
    `obj` is an object that is supposed to represent a GeoJSON geometry. This method returns the
    reads the `"type"` field and returns the correct pydantic Geometry model.
    """
    if "type" not in obj:
        raise ValidationError(
            errors=[
                ErrorWrapper(ValueError("Missing 'type' field in geometry"), loc="type")
            ],
            model=_GeometryBase,
        )
    if obj["type"] == "Point":
        return Point.parse_obj(obj)
    elif obj["type"] == "MultiPoint":
        return MultiPoint.parse_obj(obj)
    elif obj["type"] == "LineString":
        return LineString.parse_obj(obj)
    elif obj["type"] == "MultiLineString":
        return MultiLineString.parse_obj(obj)
    elif obj["type"] == "Polygon":
        return Polygon.parse_obj(obj)
    elif obj["type"] == "MultiPolygon":
        return MultiPolygon.parse_obj(obj)
    raise ValidationError(
        errors=[ErrorWrapper(ValueError("Unknown type"), loc="type")],
        model=_GeometryBase,
    )
