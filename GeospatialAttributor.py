"""
 SYNOPSIS

     GeospatialAttributor

 DESCRIPTION

    * Attributes the spatial and facility identifiers for the sewer and stormwater tables
    * Calculates the GXPCity field for sewer gravity mains by finding only gravity mains in that ward polygon
    * Appends new GPS points from the Y: drive and calculates a spatial identifier

 REQUIREMENTS

     Python 3
     arcpy
 """

import arcpy
import datetime
import logging
import os
import sys
import traceback
import re


def ScriptLogging():
    """Enables console and log file logging; see test script for comments on functionality"""
    current_directory = os.getcwd()
    script_filename = os.path.basename(sys.argv[0])
    log_filename = os.path.splitext(script_filename)[0]
    log_file = os.path.join(current_directory, f"{log_filename}.log")
    if not os.path.exists(log_file):
        with open(log_file, "w"):
            pass
    message_formatting = "%(asctime)s - %(levelname)s - %(message)s"
    date_formatting = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=message_formatting, datefmt=date_formatting)
    logging_output = logging.getLogger(f"{log_filename}")
    logging_output.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logging_output.addHandler(console_handler)
    logging.basicConfig(format=message_formatting, datefmt=date_formatting, filename=log_file, filemode="w", level=logging.INFO)
    return logging_output


def GeospatialAttributor():
    """Collection of attribution functions"""

    # Logging
    def logging_lines(name):
        """Use this wrapper to insert a message before and after the function for logging purposes"""
        if type(name) == str:
            def logging_decorator(function):
                def logging_wrapper():
                    logger.info(f"{name} Start")
                    function()
                    logger.info(f"{name} Complete")

                return logging_wrapper

            return logging_decorator

    logger = ScriptLogging()
    logger.info("Script Execution Start")

    # Paths
    geodatabase_services_folder = r"F:\Shares\FGDB_Services"
    sde = os.path.join(geodatabase_services_folder, r"DatabaseConnections\COSPW@imSPFLD@MCWINTCWDB.sde")
    data = os.path.join(geodatabase_services_folder, "Data")

    # Field calculator expressions
    spatial_start = "str(int(!NAD83XSTART!))[2:4] + str(int(!NAD83YSTART!))[2:4] + '-' + str(int(!NAD83XSTART!))[4] + " \
                    "str(int(!NAD83YSTART!))[4] + '-' + str(int(!NAD83XSTART!))[-2:] + str(int(!NAD83YSTART!))[-2:]"
    spatial_end = "str(int(!NAD83XEND!))[2:4] + str(int(!NAD83YEND!))[2:4] + '-' + str(int(!NAD83XEND!))[4] + str(int(!NAD83YEND!))[4] + '-' + str(int(!NAD83XEND!))[-2:] + str(int(!NAD83YEND!))[-2:]"
    spatial_id_line_sewer = "!SPATAILSTART! + '_' + !SPATAILEND!"  # Yes it's seriously misspelled
    spatial_id_line_storm = "!SPATIALSTART! + '_' + !SPATIALEND!"
    spatial_id_point = "str(int(!NAD83X!))[2:4] + str(int(!NAD83Y!))[2:4] + '-' + str(int(!NAD83X!))[4] + str(int(!NAD83Y!))[4] + '-' + str(int(!NAD83X!))[-2:] + str(int(!NAD83Y!))[-2:]"

    # Selection expressions
    manhole_main_exception = "(WATERTYPE = 'SW' or OWNEDBY = -2) AND FACILITYID IS NULL"
    cleanout_exception = "OWNEDBY = -2 AND FACILITYID IS NULL"
    inlet_exception = "FACILITYID IS NULL"

    # Environment settings
    arcpy.env.overwriteOutput = True

    @logging_lines("Sewer")
    def sewer_attribution():
        """Attribute sewer assets

        Takes the list of assets and their type then uses it to calculate the geometry and spatial fields.
            * Calculates spatial coordinates and SPATIALID of all assets
            * Calculates FACILITYID for unnamed manholes using map pages.
            * Calculate FACILITYID for unnamed gravity mains using manholes at endpoints
            * Calculate FACILITYID for other gravity mains, cleanouts, and inlets using spatial information

        """

        # Paths
        sewer_dataset = os.path.join(sde, "SewerStormwater")
        sewer_main = os.path.join(sewer_dataset, "ssGravityMain")
        sewer_manhole = os.path.join(sewer_dataset, "ssManhole")
        sewer_cleanout = os.path.join(sewer_dataset, "ssCleanout")
        sewer_inlet = os.path.join(sewer_dataset, "ssInlet")
        sewer_assets = [[sewer_manhole, "point", "Sewer Manholes"],
                        [sewer_main, "line", "Sewer Mains"],
                        [sewer_cleanout, "point", "Sewer Cleanouts"],
                        [sewer_inlet, "point", "Sewer Inlets"]]
        cadastral_dataset = os.path.join(sde, "CadastralReference")
        quarter_sections = os.path.join(cadastral_dataset, "PLSSQuarterSection")

        # Attribution
        for asset in sewer_assets:
            logger.info(f"{asset[2]} Start")
            arcpy.MakeFeatureLayer_management(asset[0], "asset_temp")
            selection_by_date = arcpy.SelectLayerByAttribute_management("asset_temp", "NEW_SELECTION", f"LASTEDITOR <> 'COSPW' AND FACILITYID IS NULL")

            # Looping through the list
            if int(arcpy.GetCount_management(selection_by_date).getOutput(0)) > 0:
                if asset[1] == "point":
                    arcpy.CalculateGeometryAttributes_management(selection_by_date, [["NAD83X", "POINT_X"],
                                                                                     ["NAD83Y", "POINT_Y"]])
                    arcpy.CalculateField_management(selection_by_date, "SPATIALID", spatial_id_point, "PYTHON3")
                elif asset[1] == "line":
                    arcpy.CalculateGeometryAttributes_management(selection_by_date, [["NAD83XSTART", "LINE_START_X"],
                                                                                     ["NAD83YSTART", "LINE_START_Y"],
                                                                                     ["NAD83XEND", "LINE_END_X"],
                                                                                     ["NAD83YEND", "LINE_END_Y"]])
                    arcpy.CalculateFields_management(selection_by_date, "PYTHON3", [["SPATAILSTART", spatial_start],
                                                                                    ["SPATAILEND", spatial_end],
                                                                                    ["SPATIALID", spatial_id_line_sewer]])

                # Facility ID naming for sewer manholes
                if asset[0] == sewer_manhole:

                    # Select all null manholes
                    arcpy.SelectLayerByAttribute_management(sewer_manhole, "NEW_SELECTION", "FACILITYID IS NULL AND OWNEDBY = 1 AND STAGE = 0")

                    # Select all quarter sections with nulls inside
                    with arcpy.da.SearchCursor(sewer_manhole, "WATERTYPE") as cursor:
                        for row in cursor:
                            arcpy.SelectLayerByLocation_management(quarter_sections, "COMPLETELY_CONTAINS", sewer_manhole)

                    # Create a list of quarter sections then sanitized it
                    quarter_section_list = []
                    with arcpy.da.SearchCursor(quarter_sections, "SEWMAP") as cursor:
                        for row in cursor:
                            quarter_section_list.append(row[0])
                    sanitized_quarter_section_list = [(section, section.replace("-", "")) for section in quarter_section_list]

                    # Loop through each section, selecting all manholes, and create the next name
                    for section in sanitized_quarter_section_list:
                        arcpy.SelectLayerByAttribute_management(sewer_manhole, "NEW_SELECTION", f"FACILITYID LIKE '%{section[1]}%' AND OWNEDBY = 1 AND STAGE = 0")
                        with arcpy.da.SearchCursor(sewer_manhole, "FACILITYID") as cursor:
                            current_maximum = max(cursor)
                            current_maximum_number = int(current_maximum[0].replace("SD", "")[-3:])

                        # Code block to calculate the Facility ID field while incrementing the number by 1 for each row (126-->127-->128)
                        code_block = """
                    index = 0
                    def increment():
                        global index
                        start = 1
                        interval = 1

                        if index == 0:
                            index = start
                        else:
                            index = index + interval

                        new_maximum_number = current_maximum_number + index
                        new_maximum = f"{section[1]}{new_maximum_number:03}"
                        return new_maximum"""

                        # Select the null manholes inside the current quarter section then name each one
                        arcpy.SelectLayerByAttribute_management(quarter_sections, "NEW_SELECTION", f"SEWMAP LIKE '%{section[0]}%'")
                        arcpy.SelectLayerByLocation_management(sewer_manhole, "COMPLETELY_WITHIN", quarter_sections)
                        arcpy.SelectLayerByAttribute_management(sewer_manhole, "SUBSET_SELECTION", "FACILITYID IS NULL AND OWNEDBY = 1 AND STAGE = 0")
                        if int(arcpy.GetCount_management(sewer_manhole).getOutput(0)) > 0:
                            with arcpy.da.SearchCursor(sewer_manhole, "FACILITYID") as cursor:
                                for row in cursor:
                                    arcpy.CalculateField_management(sewer_manhole, "FACILITYID", f"increment()", "PYTHON3", code_block)

                # Facility ID naming for sewer gravity mains
                if asset[0] == sewer_main:

                    # Paths
                    attributor = os.path.join(data, "Attributor.gdb")
                    start_vertices = os.path.join(attributor, "StartVertices")
                    start_join = os.path.join(attributor, "StartJoin")
                    end_vertices = os.path.join(attributor, "EndVertices")
                    end_join = os.path.join(attributor, "EndJoin")

                    # Select all null gravity mains
                    arcpy.SelectLayerByAttribute_management(sewer_main, "NEW_SELECTION", "FACILITYID IS NULL And FROMMH IS NULL And TOMH IS NULL And STAGE = 0 And OWNEDBY = 1 And WATERTYPE = 'SS'")

                    # Upstream features
                    arcpy.FeatureVerticesToPoints_management(sewer_main, start_vertices, "START")
                    upstream_manholes = arcpy.SelectLayerByLocation_management(sewer_manhole, "INTERSECT", start_vertices)

                    # Spatial join
                    start_join_map = fr"ORIG_FID 'ORIG_FID' true true false 255 Text 0 0,First,#,{start_vertices},ORIG_FID,-1,-1;\
                    FROMMH 'FROMMH' true true false 255 Text 0 0,First,#,{upstream_manholes},FACILITYID,-1,-1"
                    arcpy.SpatialJoin_analysis(upstream_manholes, start_vertices, start_join, "JOIN_ONE_TO_MANY", "KEEP_COMMON", start_join_map)
                    arcpy.MakeFeatureLayer_management(start_join, "StartJoin")

                    # Loop through start vertices and calculate
                    with arcpy.da.SearchCursor("StartJoin", ["ORIG_FID", "F__FROMMH"]) as cursor:
                        for row in cursor:
                            arcpy.SelectLayerByAttribute_management(sewer_main, "NEW_SELECTION", f"OBJECTID = {row[0]}")
                            arcpy.CalculateField_management(sewer_main, "FROMMH", f"'{row[1]}'", "PYTHON3")

                    # Select all null gravity mains
                    arcpy.SelectLayerByAttribute_management(sewer_main, "NEW_SELECTION", "FACILITYID IS NULL And TOMH IS NULL And STAGE = 0 And OWNEDBY = 1 And WATERTYPE = 'SS'")

                    # Downstream features
                    arcpy.FeatureVerticesToPoints_management(sewer_main, end_vertices, "END")
                    downstream_manholes = arcpy.SelectLayerByLocation_management(sewer_manhole, "INTERSECT", end_vertices)

                    # Spatial join
                    end_join_map = fr"ORIG_FID 'ORIG_FID' true true false 255 Text 0 0,First,#,{end_vertices},ORIG_FID,-1,-1;\
                    TOMH 'TOMH' true true false 255 Text 0 0,First,#,{downstream_manholes},FACILITYID,0,20"
                    arcpy.SpatialJoin_analysis(downstream_manholes, end_vertices, end_join, "JOIN_ONE_TO_MANY", "KEEP_COMMON", end_join_map)
                    arcpy.MakeFeatureLayer_management(end_join, "EndJoin")

                    # Loop through start vertices and calculate
                    with arcpy.da.SearchCursor("EndJoin", ["ORIG_FID", "F__TOMH"]) as cursor:
                        for row in cursor:
                            arcpy.SelectLayerByAttribute_management(sewer_main, "NEW_SELECTION", f"OBJECTID = {row[0]}")
                            arcpy.CalculateField_management(sewer_main, "TOMH", f"'{row[1]}'", "PYTHON3")

                    # Finalize facility id as FROMMH_TOMH
                    arcpy.SelectLayerByAttribute_management(sewer_main, "NEW_SELECTION", "FACILITYID IS NULL AND STAGE = 0 And OWNEDBY = 1 And WATERTYPE = 'SS'")
                    arcpy.CalculateField_management(sewer_main, "FACILITYID", "!FROMMH! + '-' + !TOMH!", "PYTHON3")

                # Facility ID exceptions
                if asset[0] in {sewer_manhole, sewer_main}:
                    selection = arcpy.SelectLayerByAttribute_management("asset_temp", "NEW_SELECTION", manhole_main_exception)
                    arcpy.CalculateField_management(selection, "FACILITYID", "!SPATIALID!", "PYTHON3")
                elif asset[0] == sewer_cleanout:
                    selection = arcpy.SelectLayerByAttribute_management("asset_temp", "NEW_SELECTION", cleanout_exception)
                    arcpy.CalculateField_management(selection, "FACILITYID", "!SPATIALID!", "PYTHON3")
                elif asset[0] == sewer_inlet:
                    selection = arcpy.SelectLayerByAttribute_management("asset_temp", "NEW_SELECTION", inlet_exception)
                    arcpy.CalculateField_management(selection, "FACILITYID", "!SPATIALID!", "PYTHON3")
            logger.info(f"{asset[2]} Complete")

    @logging_lines("Storm")
    def storm_attribution():
        """Takes the list of stormwater assets and their type then uses it to calculate the geometry and spatial fields."""

        # Paths
        storm_dataset = os.path.join(sde, "Stormwater")
        storm_main = os.path.join(storm_dataset, "swGravityMain")
        storm_manhole = os.path.join(storm_dataset, "swManhole")
        storm_cleanout = os.path.join(storm_dataset, "swCleanout")
        storm_inlet = os.path.join(storm_dataset, "swInlet")
        storm_discharge = os.path.join(storm_dataset, "swDischargePoint")
        storm_culvert = os.path.join(storm_dataset, "swCulvert")
        storm_assets = [[storm_main, "line", "Storm Mains"],
                        [storm_manhole, "point", "Storm Manholes"],
                        [storm_cleanout, "point", "Storm Cleanouts"],
                        [storm_inlet, "point", "Storm Inlets"],
                        [storm_discharge, "point", "Storm Discharge Points"],
                        [storm_culvert, "line", "Storm Culverts"]]

        # Attribution
        for asset in storm_assets:

            # Looping through the list
            logger.info(f"{asset[2]} Start")
            arcpy.MakeFeatureLayer_management(asset[0], "asset_temp")
            selection_by_date = arcpy.SelectLayerByAttribute_management("asset_temp", "NEW_SELECTION", f"LASTEDITOR <> 'COSPW' and FACILITYID IS NULL")

            if int(arcpy.GetCount_management(selection_by_date).getOutput(0)) > 0:
                if asset[1] == "line":
                    arcpy.CalculateGeometryAttributes_management(selection_by_date, [["NAD83XSTART", "LINE_START_X"],
                                                                                     ["NAD83YSTART", "LINE_START_Y"],
                                                                                     ["NAD83XEND", "LINE_END_X"],
                                                                                     ["NAD83YEND", "LINE_END_Y"]])
                    arcpy.CalculateFields_management(selection_by_date, "PYTHON3", [["SPATIALSTART", spatial_start],
                                                                                    ["SPATIALEND", spatial_end],
                                                                                    ["SPATIALID", spatial_id_line_storm],
                                                                                    ["FACILITYID", spatial_id_line_storm]])
                elif asset[1] == "point":
                    arcpy.CalculateGeometryAttributes_management(selection_by_date, [["NAD83X", "POINT_X"],
                                                                                     ["NAD83Y", "POINT_Y"]])
                    arcpy.CalculateFields_management(selection_by_date, "PYTHON3", [["SPATIALID", spatial_id_point],
                                                                                    ["FACILITYID", spatial_id_point]])

            logger.info(f"{asset[2]} Complete")

    @logging_lines("GPS")
    def gps_attribution():
        """Append new GPS shapefiles in the Y: drive to the gpsNode feature class on the SDE then calculate their facility ID

            1. Use regex and the text file to sort through folders in the Y: drive to find those with the correct formatting and date and create a list of those.
            2. Use this list to append the shapefiles within the folders to gpsNode.
            3. After this, update the text file with the current date. Any folder with a date before this new date will not be appended next runtime.

        """

        # Paths
        engineering = os.path.join(sde, "SewerEngineering")
        gps_points = os.path.join(engineering, "gpsNode")
        shape_folder = "Y:\\"

        # Grab last updated date from a text file
        last_updated_file = open("last_updated.txt", "r")
        last_updated = [last_updated_file.read()]
        datetime_format = "%Y-%m-%d"
        logger.info(f"Last updated: {last_updated[0]}")

        # Create a list of folders to be appended
        folder_list = []
        for root, dirs, files in os.walk(shape_folder, topdown=False):
            [folder_list.append(folders) for folders in dirs if re.search("[-]", folders) and not re.search("[a-zA-z. ]", folders) and
             datetime.datetime.strptime(last_updated[0], datetime_format) < datetime.datetime.strptime(folders, datetime_format)]  # Add any folder without a letter in it

        # Append new folders
        if len(folder_list) > 0:
            for folder in folder_list:
                folder_path = os.path.join(shape_folder, folder)
                for file in os.listdir(folder_path):
                    if file.endswith("insMACP.shp"):
                        file_path = os.path.join(folder_path, file)
                        arcpy.Append_management(file_path, gps_points, "NO_TEST",
                                                fr'SPATIALID "Spatial Identifier" true true false 20 Text 0 0,First,#;'
                                                fr'NAD83X "Easting (X)" true true false 8 Double 8 38,First,#,{file_path},Easting,-1,-1;'
                                                fr'NAD83Y "Northing (Y)" true true false 8 Double 8 38,First,#,{file_path},Northing,-1,-1;'
                                                fr'NAVD88Z "Elevation" true true false 8 Double 8 38,First,#,{file_path},Elevation,-1,-1;'
                                                fr'GlobalID "GlobalID" false false true 38 GlobalID 0 0,First,#;'
                                                fr'INSSTATUS "Inspection Status" true true false 2 Text 0 0,First,#,{file_path},INSSTATUS,0,2;'
                                                fr'INSPECTOR "Surveyed By" true true false 50 Text 0 0,First,#,{file_path},INSPECTOR,0,13;'
                                                fr'INSSTART "Date" true true false 8 Date 0 0,First,#{file_path},INSSTART,-1,-1;'
                                                fr'INSTIME "Time" true true false 8 Date 0 0,First,#,{file_path},INSTIME,0,11;'
                                                fr'LOCDESC "Location Details" true true false 50 Text 0 0,First,#,{file_path},LOCDESC,0,11;'
                                                fr'RIMTOGRADE "Rim to Grade" true true false 8 Double 8 38,First,#;'
                                                fr'WATERTYPE "MH Use" true true false 50 Text 0 0,First,#,{file_path},WATERTYPE,0,2;'
                                                fr'ACCESSTYPE "Access Type" true true false 10 Text 0 0,First,#,{file_path},ACCESSTYPE,0,3;'
                                                fr'DIM1 "Dimension 1" true true false 8 Double 8 38,First,#;'
                                                fr'DIM2 "Dimension 2" true true false 8 Double 8 38,First,#;'
                                                fr'CVSHAPE "Cover Shape" true true false 5 Text 0 0,First,#,{file_path},CVSHAPE,0,1;'
                                                fr'CVMATL "Cover Material" true true false 10 Text 0 0,First,#,{file_path},CVMATL,0,3;'
                                                fr'CVTYPE "Cover Type" true true false 25 Text 0 0,First,#,{file_path},CVTYPE,0,5;'
                                                fr'CVFIT "Cover Frame Fit" true true false 5 Text 0 0,First,#;'
                                                fr'CVCOND "Cover Condition" true true false 10 Text 0 0,First,#;'
                                                fr'COMMENTS "Additional Info" true true false 100 Text 0 0,First,#,{file_path},COMMENTS,0,18;'
                                                fr'GEOID "GEOID" true true false 20 Text 0 0,First,#', '', '')
            arcpy.CalculateField_management(gps_points, "SPATIALID", spatial_id_point, "PYTHON3")

            # Update last_update.txt
            new_date = datetime.datetime.now().strftime(datetime_format)
            last_updated_file = open("last_updated.txt", "w")
            last_updated_file.write(f"{new_date}")
            last_updated_file.close()

    # Try running above scripts
    try:
        sewer_attribution()
        storm_attribution()
        gps_attribution()
    except (IOError, KeyError, NameError, IndexError, TypeError, UnboundLocalError, ValueError):
        traceback_info = traceback.format_exc()
        try:
            logger.info(traceback_info)
        except NameError:
            print(traceback_info)
    except arcpy.ExecuteError:
        try:
            logger.error(arcpy.GetMessages(2))
        except NameError:
            print(arcpy.GetMessages(2))
    except:
        logger.exception("Picked up an exception!")
    finally:
        try:
            logger.info("Script Execution Complete")
        except NameError:
            pass


def main():
    GeospatialAttributor()


if __name__ == '__main__':
    main()
