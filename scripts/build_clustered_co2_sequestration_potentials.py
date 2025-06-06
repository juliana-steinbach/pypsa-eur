# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Build regionalised geological sequestration potential for carbon dioxide using
data from `CO2Stop <https://setis.ec.europa.eu/european-co2-storage-
database_en>`_.
"""

import logging

import geopandas as gpd
import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)


def area(gdf):
    """
    Returns area of GeoDataFrame geometries in square kilometers.
    """
    return gdf.to_crs(epsg=3035).area.div(1e6)


def allocate_sequestration_potential(
    gdf, regions, attr="conservative estimate Mt", threshold=3
):
    if isinstance(attr, str):
        attr = [attr]
    gdf = gdf.loc[gdf[attr].sum(axis=1) > threshold, attr + ["geometry"]]
    gdf["area_sqkm"] = area(gdf)
    overlay = gpd.overlay(regions, gdf, keep_geom_type=True)
    overlay["share"] = area(overlay) / overlay["area_sqkm"]
    adjust_cols = overlay.columns.difference({"name", "area_sqkm", "geometry", "share"})
    overlay[adjust_cols] = overlay[adjust_cols].multiply(overlay["share"], axis=0)
    return overlay.dissolve("name", aggfunc="sum")[attr].sum(axis=1)


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("build_sequestration_potentials", clusters="128")

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    cf = snakemake.params.sequestration_potential

    gdf = gpd.read_file(snakemake.input.sequestration_potential)

    regions = gpd.read_file(snakemake.input.regions_offshore)
    if cf["include_onshore"]:
        onregions = gpd.read_file(snakemake.input.regions_onshore)
        regions = pd.concat([regions, onregions]).dissolve(by="name").reset_index()

    s = allocate_sequestration_potential(
        gdf, regions, attr=cf["attribute"], threshold=cf["min_size"]
    )

    s = s.where(s > cf["min_size"]).dropna()

    s.to_csv(snakemake.output.sequestration_potential)
