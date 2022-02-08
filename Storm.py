"""
 SYNOPSIS

    Attribution for stormwater assets

 DESCRIPTION


    Features
    * Organized by feature
    * Calculates both point and line features
    * Fully automated
    * Checks only null values and only performs an operation if more than 0 features need operated on
    * Comprehensive logging
    * Error logging

    1. For point assets:
        * Calculates NAD83X and NAD83Y geometry fields
        * Calculates a Spatial ID and Facility ID using geometry fields
    2. For line assets:
        * Calculates NAD83XSTART, NAD83YSTART, NAD83XEND, NAD83YEND geometry fields
        * Calculates Spatial Start, Spatial End, Spatial ID, and Facility ID fields using geometry fields

 REQUIREMENTS

     Python 3
     arcpy
 """

import arcpy
import os
import traceback
import sys
sys.path.insert(0, "Y:/Scripts")
import Logging

# Paths - Geodatabase
geodatabase_services_folder = "Z:\\"
sde = os.path.join(geodatabase_services_folder, r"DatabaseConnections\COSPW@imSPFLD@MCWINTCWDB.sde")
data = os.path.join(geodatabase_services_folder, "Data")

# Paths - Storm
storm_dataset = os.path.join(sde, "Stormwater")
storm_mains = os.path.join(storm_dataset, "swGravityMain")
storm_manholes = os.path.join(storm_dataset, "swManhole")
storm_cleanouts = os.path.join(storm_dataset, "swCleanout")
storm_inlets = os.path.join(storm_dataset, "swInlet")
storm_discharges = os.path.join(storm_dataset, "swDischargePoint")
storm_culverts = os.path.join(storm_dataset, "swCulvert")

# Paths - Engineering
sewer_engineering = os.path.join(sde, "SewerEngineering")
gps_nodes = os.path.join(sewer_engineering, "gpsNode")

# Field calculator expressions
spatial_start = "str(int(!NAD83XSTART!))[2:4] + str(int(!NAD83YSTART!))[2:4] + '-' + str(int(!NAD83XSTART!))[4] + " \
                "str(int(!NAD83YSTART!))[4] + '-' + str(int(!NAD83XSTART!))[-2:] + str(int(!NAD83YSTART!))[-2:]"
spatial_end = "str(int(!NAD83XEND!))[2:4] + str(int(!NAD83YEND!))[2:4] + '-' + str(int(!NAD83XEND!))[4] + str(int(!NAD83YEND!))[4] + '-' + str(int(!NAD83XEND!))[-2:] + str(int(!NAD83YEND!))[-2:]"
spatial_id_line_storm = "!SPATIALSTART! + '_' + !SPATIALEND!"
spatial_id_point = "str(int(!NAD83X!))[2:4] + str(int(!NAD83Y!))[2:4] + '-' + str(int(!NAD83X!))[4] + str(int(!NAD83Y!))[4] + '-' + str(int(!NAD83X!))[-2:] + str(int(!NAD83Y!))[-2:]"


# Template functions
def template_geometry_calculator(input_feature, layer_name, field_name, geometry_name):
    arcpy.MakeFeatureLayer_management(input_feature, layer_name, f"{field_name} IS NULL")
    selected_nulls_count = arcpy.GetCount_management(layer_name).getOutput(0)
    if int(selected_nulls_count) > 0:
        Logging.logger.info(f"---------START {field_name} - COUNT={selected_nulls_count}")
        geometry_string = [[field_name, geometry_name]]
        arcpy.CalculateGeometryAttributes_management(layer_name, geometry_string)
        Logging.logger.info(f"---------FINISH {field_name} - COUNT={selected_nulls_count}")
    else:
        Logging.logger.info(f"---------PASS {field_name} - COUNT={selected_nulls_count}")


def template_geometry_z_calculator(input_feature, layer_name, field_name):
    arcpy.MakeFeatureLayer_management(input_feature, layer_name, f"{field_name} IS NULL AND STAGE = 0")
    arcpy.MakeFeatureLayer_management(gps_nodes, "gps_nodes")
    gps_identical = arcpy.SelectLayerByLocation_management("gps_nodes", "ARE_IDENTICAL_TO", layer_name)
    selected_nulls_count = arcpy.GetCount_management(gps_identical).getOutput(0)
    if int(selected_nulls_count) > 0:
        Logging.logger.info(f"---------START {field_name} - COUNT={selected_nulls_count}")
        with arcpy.da.SearchCursor(gps_identical, ["OBJECTID", "NAVD88Z"]) as cursor:
            for row in cursor:
                selected_node = arcpy.SelectLayerByAttribute_management(gps_identical, "NEW_SELECTION", f"OBJECTID = {row[0]}")
                selected_manhole = arcpy.SelectLayerByLocation_management(layer_name, "ARE_IDENTICAL_TO", selected_node)
                arcpy.CalculateField_management(selected_manhole, field_name, f"{row[1]}", "PYTHON3")
        Logging.logger.info(f"---------FINISH {field_name} - COUNT={selected_nulls_count}")
    else:
        Logging.logger.info(f"---------PASS {field_name} - COUNT={selected_nulls_count}")


def template_spatial_calculator(input_feature, layer_name, field_name, expression):
    arcpy.MakeFeatureLayer_management(input_feature, layer_name, f"{field_name} IS NULL")
    selected_nulls_count = arcpy.GetCount_management(layer_name).getOutput(0)
    if int(selected_nulls_count) > 0:
        Logging.logger.info(f"---------START {field_name} - COUNT={selected_nulls_count}")
        arcpy.CalculateField_management(layer_name, field_name, expression)
        Logging.logger.info(f"---------FINISH {field_name} - COUNT={selected_nulls_count}")
    else:
        Logging.logger.info(f"---------PASS {field_name} - COUNT={selected_nulls_count}")


# Main functions
@Logging.insert("Manholes", 1)
def manholes():
    """Calculate fields for sewer manholes"""
    # Geometry fields
    geometry_fields_to_calculate = [
        ["manholes_null_x", "NAD83X", "POINT_X"],
        ["manholes_null_y", "NAD83Y", "POINT_Y"]
        ]

    Logging.logger.info("------START Geometry Calculation")
    for field in geometry_fields_to_calculate:
        template_geometry_calculator(storm_manholes, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Geometry Calculation")

    Logging.logger.info("------START Geometry (Z) Calculation")
    template_geometry_z_calculator(storm_manholes, "manholes_null_z", "NAVD88INLET")
    Logging.logger.info("------FINISH Geometry (Z) Calculation")

    # Spatial fields
    spatial_fields_to_calculate = [
        ["manholes_spatial_id", "SPATIALID", spatial_id_point],
        ["manholes_facility_id", "FACILITYID", "!SPATIALID!"]
    ]

    Logging.logger.info("------START Spatial Calculation")
    for field in spatial_fields_to_calculate:
        template_spatial_calculator(storm_manholes, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Spatial Calculation")


@Logging.insert("Inlets", 1)
def inlets():
    """Calculate fields for sewer manholes"""
    # Geometry fields
    geometry_fields_to_calculate = [
        ["inlets_null_x", "NAD83X", "POINT_X"],
        ["inlets_null_y", "NAD83Y", "POINT_Y"]
        ]

    Logging.logger.info("------START Geometry Calculation")
    for field in geometry_fields_to_calculate:
        template_geometry_calculator(storm_inlets, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Geometry Calculation")

    Logging.logger.info("------START Geometry (Z) Calculation")
    template_geometry_z_calculator(storm_inlets, "inlets_null_z", "NAVD88RIM")
    Logging.logger.info("------FINISH Geometry (Z) Calculation")

    # Spatial fields
    spatial_fields_to_calculate = [
        ["inlets_spatial_id", "SPATIALID", spatial_id_point],
        ["inlets_facility_id", "FACILITYID", "!SPATIALID!"]
    ]

    Logging.logger.info("------START Spatial Calculation")
    for field in spatial_fields_to_calculate:
        template_spatial_calculator(storm_inlets, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Spatial Calculation")


@Logging.insert("Cleanouts", 1)
def cleanouts():
    """Calculate fields for sewer manholes"""
    # Geometry fields
    geometry_fields_to_calculate = [
        ["cleanouts_null_x", "NAD83X", "POINT_X"],
        ["cleanouts_null_y", "NAD83Y", "POINT_Y"]
        ]

    Logging.logger.info("------START Geometry Calculation")
    for field in geometry_fields_to_calculate:
        template_geometry_calculator(storm_inlets, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Geometry Calculation")

    Logging.logger.info("------START Geometry (Z) Calculation")
    template_geometry_z_calculator(storm_cleanouts, "cleanouts_null_z", "NAVD88LID")
    Logging.logger.info("------FINISH Geometry (Z) Calculation")

    # Spatial fields
    spatial_fields_to_calculate = [
        ["cleanouts_spatial_id", "SPATIALID", spatial_id_point],
        ["cleanouts_facility_id", "FACILITYID", "!SPATIALID!"]
    ]

    Logging.logger.info("------START Spatial Calculation")
    for field in spatial_fields_to_calculate:
        template_spatial_calculator(storm_inlets, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Spatial Calculation")


@Logging.insert("Discharge Points", 1)
def discharges():
    """Calculate fields for sewer manholes"""
    # Geometry fields
    geometry_fields_to_calculate = [
        ["discharge_null_x", "NAD83X", "POINT_X"],
        ["discharge_null_y", "NAD83Y", "POINT_Y"]
        ]

    Logging.logger.info("------START Geometry Calculation")
    for field in geometry_fields_to_calculate:
        template_geometry_calculator(storm_discharges, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Geometry Calculation")

    # Spatial fields
    spatial_fields_to_calculate = [
        ["discharge_spatial_id", "SPATIALID", spatial_id_point],
        ["discharge_facility_id", "FACILITYID", "!SPATIALID!"]
    ]

    Logging.logger.info("------START Spatial Calculation")
    for field in spatial_fields_to_calculate:
        template_spatial_calculator(storm_discharges, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Spatial Calculation")


@Logging.insert("Culverts", 1)
def culverts():
    """Calculate fields for sewer gravity mains"""
    # Geometry fields
    geometry_fields_to_calculate = [
        ["culverts_null_x_start", "NAD83XSTART", "LINE_START_X"],
        ["culverts_null_y_start", "NAD83YSTART", "LINE_START_Y"],
        ["culverts_null_x_end", "NAD83XEND", "LINE_END_X"],
        ["culverts_null_y_end", "NAD83YEND", "LINE_END_Y"]]

    Logging.logger.info("------START Geometry Calculation")
    for field in geometry_fields_to_calculate:
        template_geometry_calculator(storm_mains, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Geometry Calculation")

    # Spatial fields
    spatial_fields_to_calculate = [
        ["culverts_null_spatial_start", "SPATIALSTART", spatial_start],
        ["culverts_null_spatial_end", "SPATIALEND", spatial_end],
        ["culverts_null_spatial_id", "SPATIALID", spatial_id_line_storm],
        ["culverts_null_facility_id", "FACILITYID", spatial_id_line_storm]
    ]

    Logging.logger.info("------START Spatial Calculation")
    for field in spatial_fields_to_calculate:
        template_spatial_calculator(storm_mains, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Spatial Calculation")


@Logging.insert("Gravity Mains", 1)
def gravity_mains():
    """Calculate fields for sewer gravity mains"""
    # Geometry fields
    geometry_fields_to_calculate = [
        ["mains_null_x_start", "NAD83XSTART", "LINE_START_X"],
        ["mains_null_y_start", "NAD83YSTART", "LINE_START_Y"],
        ["mains_null_x_end", "NAD83XEND", "LINE_END_X"],
        ["mains_null_y_end", "NAD83YEND", "LINE_END_Y"]]

    Logging.logger.info("------START Geometry Calculation")
    for field in geometry_fields_to_calculate:
        template_geometry_calculator(storm_mains, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Geometry Calculation")

    # Spatial fields
    spatial_fields_to_calculate = [
        ["mains_null_spatial_start", "SPATIALSTART", spatial_start],
        ["mains_null_spatial_end", "SPATIALEND", spatial_end],
        ["mains_null_spatial_id", "SPATIALID", spatial_id_line_storm],
        ["mains_null_facility_id", "FACILITYID", spatial_id_line_storm]
    ]

    Logging.logger.info("------START Spatial Calculation")
    for field in spatial_fields_to_calculate:
        template_spatial_calculator(storm_mains, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Spatial Calculation")

    # Commented out because Storm FROMMH and TOMH fields need to be lengthened from 11 to 12 characters
    """"# Paths
    attributor = os.path.join(data, "Attributor.gdb")
    start_vertices = os.path.join(attributor, "StormStartVertices")
    start_join = os.path.join(attributor, "StormStartJoin")
    end_vertices = os.path.join(attributor, "StormEndVertices")
    end_join = os.path.join(attributor, "StormEndJoin")

    # FROMMH
    arcpy.MakeFeatureLayer_management(storm_mains, "storm_mains_null_frommh", "FROMMH IS NULL AND STAGE = 0 AND OWNEDBY = 1")
    selected_null_frommh_count = arcpy.GetCount_management("storm_mains_null_frommh").getOutput(0)
    if int(selected_null_frommh_count) > 0:
        Logging.logger.info(f"---------START FROMMH - COUNT={selected_null_frommh_count}")
        arcpy.FeatureVerticesToPoints_management("storm_mains_null_frommh", start_vertices, "START")
        upstream_features = arcpy.SelectLayerByLocation_management(storm_manholes, "INTERSECT", start_vertices)
        arcpy.SpatialJoin_analysis(upstream_features, start_vertices, start_join, "JOIN_ONE_TO_MANY", "KEEP_COMMON",
                                   f"FACILITYID 'Facility ID' true true false 20 Text 0 0,First,#,{storm_manholes},FACILITYID,0,20;"
                                   f"ORIG_FID 'ORIG_FID' true true false 4 Long 0 0,First,#,{start_vertices},ORIG_FID,-1,-1")
        arcpy.MakeFeatureLayer_management(start_join, "StartJoin")

        with arcpy.da.SearchCursor("StartJoin", ["ORIG_FID", "FACILITYID"]) as cursor:
            for row in cursor:
                print(f"------------{row[0]}-{row[1]}")
                selected_target_main = arcpy.SelectLayerByAttribute_management(storm_mains, "NEW_SELECTION", f"OBJECTID = {row[0]}")
                arcpy.CalculateField_management(selected_target_main, "FROMMH", f"'{row[1]}'", "PYTHON3")
        Logging.logger.info(f"---------FINISH FROMMH - COUNT={selected_null_frommh_count}")
    else:
        Logging.logger.info(f"---------PASS FROMMH - COUNT={selected_null_frommh_count}")

    # TOMH
    arcpy.MakeFeatureLayer_management(storm_mains, "storm_mains_null_tomh", "TOMH IS NULL AND STAGE = 0 AND OWNEDBY = 1")
    selected_null_tomh_count = arcpy.GetCount_management("storm_mains_null_tomh").getOutput(0)
    if int(selected_null_tomh_count) > 0:
        Logging.logger.info(f"---------START TOMH - COUNT={selected_null_tomh_count}")
        arcpy.FeatureVerticesToPoints_management("storm_mains_null_tomh", end_vertices, "END")
        downstream_features = arcpy.SelectLayerByLocation_management(storm_manholes, "INTERSECT", end_vertices)
        arcpy.SpatialJoin_analysis(downstream_features, end_vertices, end_join, "JOIN_ONE_TO_MANY", "KEEP_COMMON",
                                   f"FACILITYID 'Facility ID' true true false 20 Text 0 0,First,#,{storm_manholes},FACILITYID,0,20;"
                                   f"ORIG_FID 'ORIG_FID' true true false 4 Long 0 0,First,#,{end_vertices},ORIG_FID,-1,-1")
        arcpy.MakeFeatureLayer_management(end_join, "EndJoin")

        with arcpy.da.SearchCursor("EndJoin", ["ORIG_FID", "FACILITYID"]) as cursor:
            for row in cursor:
                print(f"------------MAIN - {row[0]};{row[1]}")
                selected_target_main = arcpy.SelectLayerByAttribute_management(storm_mains, "NEW_SELECTION", f"OBJECTID = {row[0]}")
                arcpy.CalculateField_management(selected_target_main, "TOMH", f"'{row[1]}'", "PYTHON3")
        Logging.logger.info(f"---------FINISH TOMH - COUNT={selected_null_tomh_count}")
    else:
        Logging.logger.info(f"---------PASS TOMH - COUNT={selected_null_tomh_count}")"""


if __name__ == "__main__":
    traceback_info = traceback.format_exc()
    try:
        Logging.logger.info("Script Execution Started")
        manholes()
        inlets()
        cleanouts()
        discharges()
        culverts()
        gravity_mains()
        Logging.logger.info("Script Execution Finished")
    except (IOError, NameError, KeyError, IndexError, TypeError, UnboundLocalError, ValueError):
        Logging.logger.info(traceback_info)
    except NameError:
        print(traceback_info)
    except arcpy.ExecuteError:
        Logging.logger.error(arcpy.GetMessages(2))
    except:
        Logging.logger.info("An unspecified exception occurred")
