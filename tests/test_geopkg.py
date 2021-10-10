# -*- coding: utf-8 -*-
"""
Test GeoPackage
"""


from math import isnan
from random import randint, choice
from string import ascii_uppercase, digits

from pytest import fixture, mark, raises

from fudgeo.enumeration import GeometryType, SQLFieldType
from fudgeo.geometry import Point
from fudgeo.geopkg import (
    FeatureClass, Field, GeoPackage, SpatialReferenceSystem, Table)

WGS_1984_UTM_Zone_23N = (
    """PROJCS["WGS_1984_UTM_Zone_23N",
       GEOGCS["GCS_WGS_1984",
       DATUM["D_WGS_1984",
       SPHEROID["WGS_1984",6378137.0,298.257223563]],
       PRIMEM["Greenwich",0.0],
       UNIT["Degree",0.0174532925199433]],
       PROJECTION["Transverse_Mercator"],
       PARAMETER["False_Easting",500000.0],
       PARAMETER["False_Northing",0.0],
       PARAMETER["Central_Meridian",-45.0],
       PARAMETER["Scale_Factor",0.9996],
       PARAMETER["Latitude_Of_Origin",0.0],
       UNIT["Meter",1.0]];IsHighPrecision""")


INSERT_ROWS = """
    INSERT INTO test1 (SHAPE, int_fld, text_fld, test_fld_size, test_bool) 
    VALUES (?, ?, ?, ?, ?)
"""


@fixture
def setup_geopackage(tmp_path):
    """
    Setup Basics
    """
    path = tmp_path.joinpath('test.gpkg')
    gpkg = GeoPackage.create(path)
    srs = SpatialReferenceSystem(
        'WGS_1984_UTM_Zone_23N', 'EPSG', 32623, WGS_1984_UTM_Zone_23N)
    fields = (
        Field('int_fld', SQLFieldType.integer),
        Field('text_fld', SQLFieldType.text),
        Field('test_fld_size', SQLFieldType.text, 100),
        Field('test_bool', SQLFieldType.boolean))
    yield path, gpkg, srs, fields
    path.unlink(missing_ok=True)
# End setup_geopackage function


def random_points_and_attrs(count, srs_id):
    """
    Generate Random Points and attrs (Use some UTM Zone)
    """
    points = generate_utm_points(count, srs_id)
    rows = []
    for p in points:
        rand_str = ''.join(choice(ascii_uppercase + digits) for _ in range(10))
        rand_bool = bool(randint(0, 1))
        rand_int = randint(0, 1000)
        rows.append((p, rand_int, rand_str, rand_str, rand_bool))
    return rows
# End random_points_and_attrs function


def generate_utm_points(count, srs_id):
    """
    Generate UTM points in the boundaries of the UTM coordinate space
    """
    eastings = [randint(300000, 700000) for _ in range(count)]
    northings = [randint(0, 4000000) for _ in range(count)]
    return [Point(x=easting, y=northing, srs_id=srs_id)
            for easting, northing in zip(eastings, northings)]
# End generate_utm_points function


def test_create_geopackage(tmp_path):
    """
    Test create geopackage
    """
    path = tmp_path.joinpath('does_not_exist', 'abc')
    with raises(ValueError):
        GeoPackage.create(path)
    path = tmp_path / 'abc'
    geo = GeoPackage.create(path)
    assert geo.path.is_file()
    assert isinstance(geo, GeoPackage)
    with raises(ValueError):
        GeoPackage.create(path)
    geo.connection.close()
    path.unlink(missing_ok=True)
# End test_create_geopackage function


def test_create_table(tmp_path):
    """
    Create Table
    """
    path = tmp_path / 'tbl'
    geo = GeoPackage.create(path)
    fields = [Field('AAA', SQLFieldType.integer),
              Field('BBB', SQLFieldType.text, size=10),
              Field('CCC', SQLFieldType.text),
              Field('DDD', SQLFieldType.double)]
    name = 'TTT'
    table = geo.create_table(name, fields)
    assert isinstance(table, Table)
    with raises(ValueError):
        geo.create_table(name, fields)
    cursor = geo.connection.execute(f"""SELECT count(fid) FROM {name}""")
    count, = cursor.fetchone()
    assert count == 0
    table = geo.create_table('ANOTHER')
    assert isinstance(table, Table)
    geo.connection.close()
    path.unlink(missing_ok=True)
# End test_create_table function


def test_create_feature_class(tmp_path):
    """
    Create Feature Class
    """
    path = tmp_path / 'fc'
    geo = GeoPackage.create(path)
    fields = [Field('AAA', SQLFieldType.integer),
              Field('BBB', SQLFieldType.text, size=10),
              Field('CCC', SQLFieldType.text),
              Field('DDD', SQLFieldType.double)]
    name = 'FFF'
    srs = SpatialReferenceSystem(
        'WGS_1984_UTM_Zone_23N', 'EPSG', 32623, WGS_1984_UTM_Zone_23N)
    table = geo.create_feature_class(name, srs=srs, fields=fields)
    assert isinstance(table, FeatureClass)
    with raises(ValueError):
        geo.create_feature_class(name, srs=srs, fields=fields)
    cursor = geo.connection.execute(f"""SELECT count(fid) FROM {name}""")
    count, = cursor.fetchone()
    assert count == 0
    table = geo.create_feature_class('ANOTHER', srs=srs)
    assert isinstance(table, FeatureClass)
    geo.connection.close()
    path.unlink(missing_ok=True)
# End test_create_feature_class function


@mark.parametrize('name, geom, has_z, has_m', [
    ('test_points', GeometryType.point, False, False),
    ('test_points_z', GeometryType.point, True, False),
    ('test_points_m', GeometryType.point, False, True),
    ('test_points_zm', GeometryType.point, True, True),
    ('test_lines', GeometryType.linestring, False, False),
    ('test_lines_z', GeometryType.linestring, True, False),
    ('test_lines_m', GeometryType.linestring, False, True),
    ('test_lines_zm', GeometryType.linestring, True, True),
    ('test_polygons', GeometryType.polygon, False, False),
    ('test_polygons_z', GeometryType.polygon, True, False),
])
def test_create_feature_class_options(setup_geopackage, name, geom, has_z, has_m):
    """
    Test creating feature classes with different shape options
    """
    _, gpkg, srs, fields = setup_geopackage
    fc = gpkg.create_feature_class(
        name, srs=srs, fields=fields, m_enabled=has_m, z_enabled=has_z)
    assert isinstance(fc, FeatureClass)
    conn = gpkg.connection
    cursor = conn.execute(f"""SELECT count(fid) FROM {name}""")
    count, = cursor.fetchone()
    assert count == 0
    assert fc.spatial_reference_system.srs_id == 32623
    assert fc.has_z is has_z
    assert fc.has_m is has_m
# End test_create_feature_class_options method


def test_insert_point_rows(setup_geopackage):
    """
    Test Insert Point Rows
    """
    _, gpkg, srs, fields = setup_geopackage
    fc = gpkg.create_feature_class(
        'test1', srs, fields=fields, shape_type=GeometryType.point)
    assert isinstance(fc, FeatureClass)
    count = 10000
    rows = random_points_and_attrs(count, srs.srs_id)
    conn = gpkg.connection
    conn.executemany(INSERT_ROWS, rows)
    conn.commit()
    cursor = conn.execute("""SELECT count(fid) from test1""")
    row_count, = cursor.fetchone()
    assert row_count == count
    cursor = conn.execute("""SELECT SHAPE FROM test1 LIMIT 10""")
    points = [rec[0] for rec in cursor.fetchall()]
    assert all([isinstance(pt, Point) for pt in points])
    assert all(pt.srs_id == srs.srs_id for pt in points)
    assert all(isnan(v) for v in fc.extent)
    fc.extent = (300000, 1, 700000, 4000000)
    assert (300000, 1, 700000, 4000000) == fc.extent
# End test_insert_point_rows method


if __name__ == '__main__':
    pass
