"""
 SYNOPSIS

    Attribution for sewer stormwater assets

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
        * Calculates a Spatial ID using geometry fields
        * Calculates a Facility ID using the current map page number and the highest existing 3-digit value plus one (ie if the existing high value is 1414GH065 the new features will start from ...066 onwards)
    2. For line assets:
        * Calculates NAD83XSTART, NAD83YSTART, NAD83XEND, NAD83YEND geometry fields
        * Calculates Spatial Start, Spatial End, and Spatial ID fields using geometry fields
        * Calculates FROMMH and TOMH fields using upstream/downstream vertices that intersect manholes
        * Uses FROMM and TOMH to create a new Facility ID

 REQUIREMENTS

     Python 3
     arcpy
 """

import arcpy
import Logging
import os
import traceback

# Global variables for manhole naming
current_maximum_number = 0
section = "0000AA000"

# Paths - Geodatabase
geodatabase_services_folder = "Z:\\"
sde = os.path.join(geodatabase_services_folder, r"DatabaseConnections\COSPW@imSPFLD@MCWINTCWDB.sde")
data = os.path.join(geodatabase_services_folder, "Data")

# Paths - Sewer
sewer_dataset = os.path.join(sde, "SewerStormwater")
sewer_mains = os.path.join(sewer_dataset, "ssGravityMain")
sewer_manholes = os.path.join(sewer_dataset, "ssManhole")
sewer_cleanouts = os.path.join(sewer_dataset, "ssCleanout")
sewer_inlets = os.path.join(sewer_dataset, "ssInlet")
cadastral_dataset = os.path.join(sde, "CadastralReference")
quarter_sections = os.path.join(cadastral_dataset, "PLSSQuarterSection")

# Field calculator expressions
spatial_start = "str(int(!NAD83XSTART!))[2:4] + str(int(!NAD83YSTART!))[2:4] + '-' + str(int(!NAD83XSTART!))[4] + " \
                "str(int(!NAD83YSTART!))[4] + '-' + str(int(!NAD83XSTART!))[-2:] + str(int(!NAD83YSTART!))[-2:]"
spatial_end = "str(int(!NAD83XEND!))[2:4] + str(int(!NAD83YEND!))[2:4] + '-' + str(int(!NAD83XEND!))[4] + str(int(!NAD83YEND!))[4] + '-' + str(int(!NAD83XEND!))[-2:] + str(int(!NAD83YEND!))[-2:]"
spatial_id_line_sewer = "!SPATAILSTART! + '_' + !SPATAILEND!"  # Yes it's seriously misspelled
spatial_id_line_storm = "!SPATIALSTART! + '_' + !SPATIALEND!"
spatial_id_point = "str(int(!NAD83X!))[2:4] + str(int(!NAD83Y!))[2:4] + '-' + str(int(!NAD83X!))[4] + str(int(!NAD83Y!))[4] + '-' + str(int(!NAD83X!))[-2:] + str(int(!NAD83Y!))[-2:]"

# Selection expressions
manhole_main_exception = "FACILITYID IS NULL AND (WATERTYPE = 'SW' OR OWNEDBY = -2)"
cleanout_exception = "FACILITYID IS NULL"
inlet_exception = "FACILITYID IS NULL"

# Environments
arcpy.env.overwriteOutput = True


# Template functions
def template_geometry_calculator(input_feature, layer_name, field_name, geometry_name):
    arcpy.MakeFeatureLayer_management(input_feature, layer_name, f"{field_name} IS NULL")
    selected_nulls_count = arcpy.GetCount_management(layer_name).getOutput(0)
    if int(selected_nulls_count) > 0:
        Logging.logger.info(f"---------START {field_name} - COUNT={selected_nulls_count}")
        geometry_list = [[field_name, geometry_name]]
        arcpy.CalculateGeometryAttributes_management(layer_name, geometry_list)
        Logging.logger.info(f"---------FINISH {field_name} - COUNT={selected_nulls_count}")
    else:
        Logging.logger.info(f"---------PASS {field_name} - COUNT={selected_nulls_count}")


def template_spatial_calculator(input_feature, layer_name, field_name, expression):
    # Check if a special selection is given
    if input_feature == sewer_cleanouts and field_name == "FACILITYID":
        selection = "FACILITYID IS NULL AND OWNEDBY = -2"
    else:
        selection = "FACILITYID IS NULL"
    arcpy.MakeFeatureLayer_management(input_feature, layer_name, selection)
    selected_nulls_count = arcpy.GetCount_management(layer_name).getOutput(0)
    if int(selected_nulls_count) > 0:
        Logging.logger.info(f"---------START {field_name} - COUNT={selected_nulls_count}")
        arcpy.CalculateField_management(layer_name, field_name, expression)
        Logging.logger.info(f"---------FINISH {field_name} - COUNT={selected_nulls_count}")
    else:
        Logging.logger.info(f"---------PASS {field_name} - COUNT={selected_nulls_count}")


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
        template_geometry_calculator(sewer_manholes, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Geometry Calculation")

    # Spatial fields
    spatial_fields_to_calculate = [
        ["manholes_spatial_id", "SPATIALID", spatial_id_point]
    ]

    Logging.logger.info("------START Spatial Calculation")
    for field in spatial_fields_to_calculate:
        template_spatial_calculator(sewer_manholes, field[0], field[1], field[2])

    # Select all null manholes and quarter sections that contain it
    selected_manholes = arcpy.SelectLayerByAttribute_management(sewer_manholes, "NEW_SELECTION", "FACILITYID IS NULL AND STAGE = 0 AND OWNEDBY = 1")
    selected_quarter_sections = arcpy.SelectLayerByLocation_management(quarter_sections, "COMPLETELY_CONTAINS", selected_manholes)
    selected_manholes_count = arcpy.GetCount_management(selected_manholes).getOutput(0)
    if int(selected_manholes_count) > 0:
        Logging.logger.info(f"---------START FACILITYID - COUNT={selected_manholes_count}")

        # Create a list of quarter sections then sanitize it
        quarter_section_list = []
        with arcpy.da.SearchCursor(selected_quarter_sections, "SEWMAP") as cursor:
            for row in cursor:
                quarter_section_list.append(row[0])
        sanitized_quarter_section_list = [(section, section.replace("-", "")) for section in quarter_section_list]

        # Select all relevant manholes in the current quarter section
        global section
        for section in sanitized_quarter_section_list:
            selected_manholes_in_section = arcpy.SelectLayerByAttribute_management(sewer_manholes, "NEW_SELECTION", f"FACILITYID LIKE '%{section[1]}%' AND STAGE = 0")

            # For the current quarter section, find the highest last three digits of selected manholes
            with arcpy.da.SearchCursor(selected_manholes_in_section, "FACILITYID") as maximum_cursor:
                global current_maximum_number
                current_maximum = max(maximum_cursor)
                current_maximum_number = int(current_maximum[0].replace("SD", "")[-3:])

            # Select the null manholes inside the current quarter section
            selected_quarter_sections = arcpy.SelectLayerByAttribute_management(quarter_sections, "NEW_SELECTION", f"SEWMAP LIKE '%{section[0]}%'")
            selected_within_manholes = arcpy.SelectLayerByLocation_management(sewer_manholes, "COMPLETELY_WITHIN", selected_quarter_sections)
            selected_null_manholes = arcpy.SelectLayerByAttribute_management(selected_within_manholes, "SUBSET_SELECTION", "FACILITYID IS NULL AND STAGE = 0")

            # Calculate the Facility IDs of each null manhole selected in the current quarter section, incrementing the last three digits per feature using the function below (indentation is correct)
            increment_function = """index = 0
def increment():
    global index
    global current_maximum_number
    start = 1

    if index == 0:
        index = start
    else:
        index += 1

    new_maximum_number = current_maximum_number + index
    new_name = f"{section[1]}{new_maximum_number:03}"
    print(f"{index} + {current_maximum_number} = {new_name}")
    return new_name"""
            arcpy.CalculateField_management(selected_null_manholes, "FACILITYID", f"increment()", "PYTHON3", increment_function)
            arcpy.Delete_management("SewerManholes")
        Logging.logger.info(f"---------FINISH FACILITYID - COUNT={selected_manholes_count}")
    else:
        Logging.logger.info(f"---------PASS FACILITYID - COUNT={selected_manholes_count}")
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
        template_geometry_calculator(sewer_inlets, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Geometry Calculation")

    # Spatial fields
    spatial_fields_to_calculate = [
        ["inlets_null_spatial_id", "SPATIALID", spatial_id_point],
        ["inlets_null_facility_id", "FACILITYID", "!SPATIALID!"]
    ]

    Logging.logger.info("------START Spatial Calculation")
    for field in spatial_fields_to_calculate:
        template_spatial_calculator(sewer_manholes, field[0], field[1], field[2])
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
        template_geometry_calculator(sewer_cleanouts, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Geometry Calculation")

    # Spatial fields
    spatial_fields_to_calculate = [
        ["cleanouts_spatial_id", "SPATIALID", spatial_id_point],
        ["cleanouts_facility_id", "FACILITYID", spatial_id_point]
    ]

    Logging.logger.info("------START Spatial Calculation")
    for field in spatial_fields_to_calculate:
        template_spatial_calculator(sewer_cleanouts, field[0], field[1], field[2])

    selected_cleanouts = arcpy.SelectLayerByAttribute_management(sewer_cleanouts, "NEW_SELECTION", "FACILITYID IS NULL AND OWNEDBY = 1")
    selected_quarter_sections = arcpy.SelectLayerByLocation_management(quarter_sections, "COMPLETELY_CONTAINS", selected_cleanouts)
    selected_cleanouts_count = arcpy.GetCount_management(selected_cleanouts).getOutput(0)
    if int(selected_cleanouts_count) > 0:
        Logging.logger.info(f"---------START FACILITYID (City) - COUNT={selected_cleanouts_count}")

        # Create a list of quarter sections then sanitize it
        quarter_section_list = []
        with arcpy.da.SearchCursor(selected_quarter_sections, "SEWMAP") as cursor:
            for row in cursor:
                quarter_section_list.append(row[0])
        sanitized_quarter_section_list = [(section, section.replace("-", "")) for section in quarter_section_list]

        # Select all relevant manholes in the current quarter section
        global section
        for section in sanitized_quarter_section_list:
            selected_manholes_in_section = arcpy.SelectLayerByAttribute_management(sewer_manholes, "NEW_SELECTION", f"FACILITYID LIKE '%{section[1]}%' AND STAGE = 0")

            # For the current quarter section, find the highest last three digits of selected cleanouts
            with arcpy.da.SearchCursor(selected_manholes_in_section, "FACILITYID") as maximum_cursor:
                global current_maximum_number
                current_maximum = max(maximum_cursor)
                current_maximum_number = int(current_maximum[0].replace("SD", "")[-3:])

            # Select the null cleanouts inside the current quarter section
            selected_quarter_sections = arcpy.SelectLayerByAttribute_management(quarter_sections, "NEW_SELECTION", f"SEWMAP LIKE '%{section[0]}%'")
            selected_within_cleanouts = arcpy.SelectLayerByLocation_management(sewer_cleanouts, "COMPLETELY_WITHIN", selected_quarter_sections)
            selected_null_cleanouts = arcpy.SelectLayerByAttribute_management(selected_within_cleanouts, "SUBSET_SELECTION", "FACILITYID IS NULL AND OWNEDBY = 1")

            # Calculate the Facility IDs of each null cleanouts selected in the current quarter section, incrementing the last three digits per feature using the function below (indentation is correct)
            increment_function = """index = 0
def increment():
    global index
    global current_maximum_number
    start = 1

    if index == 0:
        index = start
    else:
        index += 1

    new_maximum_number = current_maximum_number + index
    new_name = f"{section[1]}{new_maximum_number:03}C"
    print(f"{index} + {current_maximum_number} = {new_name}")
    return new_name"""
            arcpy.CalculateField_management(selected_null_cleanouts, "FACILITYID", f"increment()", "PYTHON3", increment_function)
            arcpy.Delete_management("SewerCleanouts")
        Logging.logger.info(f"---------FINISH FACILITYID (City) - COUNT={selected_cleanouts_count}")
    else:
        Logging.logger.info(f"---------PASS FACILITYID (City) - COUNT={selected_cleanouts_count}")
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
        template_geometry_calculator(sewer_mains, field[0], field[1], field[2])
    Logging.logger.info("------FINISH Geometry Calculation")

    # Spatial fields
    spatial_fields_to_calculate = [
        ["null_spatial_start", "SPATAILSTART", spatial_start],
        ["null_spatial_end", "SPATAILEND", spatial_end],
        ["null_spatial_id", "SPATIALID", spatial_id_line_sewer]
    ]

    Logging.logger.info("------START Spatial Calculation")
    for field in spatial_fields_to_calculate:
        template_spatial_calculator(sewer_mains, field[0], field[1], field[2])

    # Paths
    attributor = os.path.join(data, "Attributor.gdb")
    start_vertices = os.path.join(attributor, "SewerStartVertices")
    start_join = os.path.join(attributor, "SewerStartJoin")
    end_vertices = os.path.join(attributor, "SewerEndVertices")
    end_join = os.path.join(attributor, "SewerEndJoin")

    # Delete existing temp feature classes
    Logging.logger.info("---------START DELETE Temp")
    if arcpy.Exists(start_vertices):
        arcpy.Delete_management(start_vertices)
    if arcpy.Exists(end_vertices):
        arcpy.Delete_management(end_vertices)
    if arcpy.Exists(start_join):
        arcpy.Delete_management(start_join)
    if arcpy.Exists(end_join):
        arcpy.Delete_management(end_join)
    Logging.logger.info("---------FINISH DELETE Temp")

    # FROMMH (map page)
    arcpy.MakeFeatureLayer_management(sewer_mains, "sewer_mains_null_frommh", "FROMMH IS NULL AND STAGE = 0 AND OWNEDBY = 1 AND (WATERTYPE = 'SS' OR WATERTYPE ='CB')")
    selected_null_frommh_count = arcpy.GetCount_management("sewer_mains_null_frommh").getOutput(0)
    if int(selected_null_frommh_count) > 0:
        Logging.logger.info(f"---------START FROMMH - COUNT={selected_null_frommh_count}")
        arcpy.FeatureVerticesToPoints_management("sewer_mains_null_frommh", start_vertices, "START")
        upstream_features = arcpy.SelectLayerByLocation_management(sewer_manholes, "INTERSECT", start_vertices)
        arcpy.SpatialJoin_analysis(upstream_features, start_vertices, start_join, "JOIN_ONE_TO_MANY", "KEEP_COMMON",
                                   f"FACILITYID 'Facility ID' true true false 20 Text 0 0,First,#,{sewer_manholes},FACILITYID,0,20;"
                                   f"ORIG_FID 'ORIG_FID' true true false 4 Long 0 0,First,#,{start_vertices},ORIG_FID,-1,-1")
        arcpy.MakeFeatureLayer_management(start_join, "StartJoin")

        with arcpy.da.SearchCursor("StartJoin", ["ORIG_FID", "FACILITYID"]) as cursor:
            for row in cursor:
                print(f"------------{row[0]}-{row[1]}")
                selected_target_main = arcpy.SelectLayerByAttribute_management(sewer_mains, "NEW_SELECTION", f"OBJECTID = {row[0]}")
                arcpy.CalculateField_management(selected_target_main, "FROMMH", f"'{row[1]}'", "PYTHON3")
        Logging.logger.info(f"---------FINISH FROMMH - COUNT={selected_null_frommh_count}")
    else:
        Logging.logger.info(f"---------PASS FROMMH - COUNT={selected_null_frommh_count}")

    # TOMH (map page)
    arcpy.MakeFeatureLayer_management(sewer_mains, "sewer_mains_null_tomh", "TOMH IS NULL AND STAGE = 0 AND OWNEDBY = 1 AND (WATERTYPE = 'SS' OR WATERTYPE ='CB')")
    selected_null_tomh_count = arcpy.GetCount_management("sewer_mains_null_tomh").getOutput(0)
    if int(selected_null_tomh_count) > 0:
        Logging.logger.info(f"---------START TOMH - COUNT={selected_null_tomh_count}")
        arcpy.FeatureVerticesToPoints_management("sewer_mains_null_tomh", end_vertices, "END")
        downstream_features = arcpy.SelectLayerByLocation_management(sewer_manholes, "INTERSECT", end_vertices)
        arcpy.SpatialJoin_analysis(downstream_features, end_vertices, end_join, "JOIN_ONE_TO_MANY", "KEEP_COMMON",
                                   f"FACILITYID 'Facility ID' true true false 20 Text 0 0,First,#,{sewer_manholes},FACILITYID,0,20;"
                                   f"ORIG_FID 'ORIG_FID' true true false 4 Long 0 0,First,#,{end_vertices},ORIG_FID,-1,-1")
        arcpy.MakeFeatureLayer_management(end_join, "EndJoin")

        with arcpy.da.SearchCursor("EndJoin", ["ORIG_FID", "FACILITYID"]) as cursor:
            for row in cursor:
                print(f"------------MAIN - {row[0]};{row[1]}")
                selected_target_main = arcpy.SelectLayerByAttribute_management(sewer_mains, "NEW_SELECTION", f"OBJECTID = {row[0]}")
                arcpy.CalculateField_management(selected_target_main, "TOMH", f"'{row[1]}'", "PYTHON3")
        Logging.logger.info(f"---------FINISH TOMH - COUNT={selected_null_tomh_count}")
    else:
        Logging.logger.info(f"---------PASS TOMH - COUNT={selected_null_tomh_count}")

    # Facility ID (map page)
    selected_null_facilityid = arcpy.SelectLayerByAttribute_management(sewer_mains, "NEW_SELECTION", "FACILITYID IS NULL AND STAGE = 0 AND (WATERTYPE = 'SS' OR WATERTYPE = 'CB')")
    selected_null_facilityid_count = arcpy.GetCount_management(selected_null_facilityid).getOutput(0)
    if int(selected_null_facilityid_count) > 0:
        Logging.logger.info(f"---------START FACILITYID (Map Page) - COUNT={selected_null_facilityid_count}")
        arcpy.CalculateField_management(selected_null_facilityid, "FACILITYID", "!FROMMH! + '-' + !TOMH!", "PYTHON3")
        Logging.logger.info(f"---------FINISH FACILITYID (Map Page) - COUNT={selected_null_facilityid_count}")
    else:
        Logging.logger.info(f"---------PASS FACILITYID (Map Page) - COUNT={selected_null_facilityid_count}")

    # Facility ID (stormwater)
    selected_null_facilityid_storm = arcpy.SelectLayerByAttribute_management(sewer_mains, "NEW_SELECTION", "FACILITYID IS NULL AND STAGE = 0 AND WATERTYPE = 'SW'")
    selected_null_facilityid_storm_count = arcpy.GetCount_management(selected_null_facilityid_storm).getOutput(0)
    if int(selected_null_facilityid_storm_count) > 0:
        Logging.logger.info(f"---------START FACILITYID (Spatial) - COUNT={selected_null_facilityid_storm_count}")
        arcpy.CalculateField_management(selected_null_facilityid_storm, "FACILITYID", "!SPATIALID!", "PYTHON3")
        Logging.logger.info(f"---------FINISH FACILITYID (Spatial) - COUNT={selected_null_facilityid_storm_count}")
    else:
        Logging.logger.info(f"---------PASS FACILITYID (Spatial) - COUNT={selected_null_facilityid_storm_count}")
    Logging.logger.info("------FINISH Spatial Calculation")


if __name__ == "__main__":
    traceback_info = traceback.format_exc()
    try:
        Logging.logger.info("Script Execution Started")
        manholes()
        inlets()
        cleanouts()
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
