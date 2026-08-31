from dataclasses import dataclass
import math


WGS84 = "wgs84"
GCJ02 = "gcj02"

_PI = math.pi
_GCJ_SEMI_MAJOR_AXIS = 6_378_245.0
_GCJ_ECCENTRICITY_SQUARED = 0.00669342162296594323


@dataclass(frozen=True)
class CoordinateTransform:
    latitude: float
    longitude: float
    source_system: str
    target_system: str
    converted: bool


def normalize_coordinate_system(value: str | None) -> str:
    normalized = "".join(
        character
        for character in str(value or "").strip().lower()
        if character.isalnum()
    )
    aliases = {
        "wgs84": WGS84,
        "epsg4326": WGS84,
        "gps": WGS84,
        "gcj02": GCJ02,
        "mars": GCJ02,
    }
    coordinate_system = aliases.get(normalized)
    if coordinate_system is None:
        raise ValueError("坐标系必须是 wgs84 或 gcj02")
    return coordinate_system


def is_gcj02_applicable(latitude: float, longitude: float) -> bool:
    """Return whether the mainland GCJ-02 transform applies."""
    latitude = float(latitude)
    longitude = float(longitude)
    if not (
        0.8293 <= latitude <= 55.8271
        and 72.004 <= longitude <= 137.8347
    ):
        return False
    # The common bounding rectangle includes Taiwan; exclude it here.
    if 21.5 <= latitude <= 25.5 and 119.0 <= longitude <= 124.5:
        return False
    return True


def _latitude_offset(longitude: float, latitude: float) -> float:
    value = (
        -100.0
        + 2.0 * longitude
        + 3.0 * latitude
        + 0.2 * latitude * latitude
        + 0.1 * longitude * latitude
        + 0.2 * math.sqrt(abs(longitude))
    )
    value += (
        20.0 * math.sin(6.0 * longitude * _PI)
        + 20.0 * math.sin(2.0 * longitude * _PI)
    ) * 2.0 / 3.0
    value += (
        20.0 * math.sin(latitude * _PI)
        + 40.0 * math.sin(latitude / 3.0 * _PI)
    ) * 2.0 / 3.0
    value += (
        160.0 * math.sin(latitude / 12.0 * _PI)
        + 320.0 * math.sin(latitude * _PI / 30.0)
    ) * 2.0 / 3.0
    return value


def _longitude_offset(longitude: float, latitude: float) -> float:
    value = (
        300.0
        + longitude
        + 2.0 * latitude
        + 0.1 * longitude * longitude
        + 0.1 * longitude * latitude
        + 0.1 * math.sqrt(abs(longitude))
    )
    value += (
        20.0 * math.sin(6.0 * longitude * _PI)
        + 20.0 * math.sin(2.0 * longitude * _PI)
    ) * 2.0 / 3.0
    value += (
        20.0 * math.sin(longitude * _PI)
        + 40.0 * math.sin(longitude / 3.0 * _PI)
    ) * 2.0 / 3.0
    value += (
        150.0 * math.sin(longitude / 12.0 * _PI)
        + 300.0 * math.sin(longitude / 30.0 * _PI)
    ) * 2.0 / 3.0
    return value


def wgs84_to_gcj02(
    latitude: float,
    longitude: float,
) -> tuple[float, float]:
    latitude = float(latitude)
    longitude = float(longitude)
    if not is_gcj02_applicable(latitude, longitude):
        return latitude, longitude

    latitude_delta = _latitude_offset(
        longitude - 105.0,
        latitude - 35.0,
    )
    longitude_delta = _longitude_offset(
        longitude - 105.0,
        latitude - 35.0,
    )
    radians = latitude / 180.0 * _PI
    sine = math.sin(radians)
    magic = 1.0 - _GCJ_ECCENTRICITY_SQUARED * sine * sine
    square_root = math.sqrt(magic)
    latitude_delta = (
        latitude_delta * 180.0
        / (
            (_GCJ_SEMI_MAJOR_AXIS * (1.0 - _GCJ_ECCENTRICITY_SQUARED))
            / (magic * square_root)
            * _PI
        )
    )
    longitude_delta = (
        longitude_delta * 180.0
        / (
            _GCJ_SEMI_MAJOR_AXIS
            / square_root
            * math.cos(radians)
            * _PI
        )
    )
    return latitude + latitude_delta, longitude + longitude_delta


def transform_wgs84_for_target(
    latitude: float,
    longitude: float,
    target_system: str,
) -> CoordinateTransform:
    target = normalize_coordinate_system(target_system)
    latitude = float(latitude)
    longitude = float(longitude)
    if target == WGS84:
        return CoordinateTransform(
            latitude=latitude,
            longitude=longitude,
            source_system=WGS84,
            target_system=WGS84,
            converted=False,
        )
    transformed_latitude, transformed_longitude = wgs84_to_gcj02(
        latitude,
        longitude,
    )
    converted = (
        transformed_latitude != latitude
        or transformed_longitude != longitude
    )
    return CoordinateTransform(
        latitude=transformed_latitude,
        longitude=transformed_longitude,
        source_system=WGS84,
        target_system=GCJ02,
        converted=converted,
    )


def coordinate_distance_meters(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> float:
    earth_radius = 6_371_000.0
    first_radians = math.radians(float(first_latitude))
    second_radians = math.radians(float(second_latitude))
    latitude_delta = math.radians(
        float(second_latitude) - float(first_latitude)
    )
    longitude_delta = math.radians(
        float(second_longitude) - float(first_longitude)
    )
    haversine = (
        math.sin(latitude_delta / 2.0) ** 2
        + math.cos(first_radians)
        * math.cos(second_radians)
        * math.sin(longitude_delta / 2.0) ** 2
    )
    normalized_haversine = min(max(haversine, 0.0), 1.0)
    return 2.0 * earth_radius * math.asin(
        math.sqrt(normalized_haversine)
    )
