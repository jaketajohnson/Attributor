"""
 SYNOPSIS

     Attributor

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
from logging.handlers import RotatingFileHandler


def start_rotating_logging(log_file=None, max_bytes=10000, backup_count=1, suppress_requests_messages=True):
    """Creates a logger that outputs to stdout and a log file; outputs start and completion of functions or attribution of functions"""

    formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Paths to desired log file
    script_folder = os.path.dirname(sys.argv[0])
    script_name = os.path.basename(sys.argv[0])
    script_name_no_ext = os.path.splitext(script_name)[0]
    log_folder = os.path.join(script_folder, "Log_Files")
    if not log_file:
        log_file = os.path.join(log_folder, f"{script_name_no_ext}.log")

    # Start logging
    the_logger = logging.getLogger(script_name)
    the_logger.setLevel(logging.DEBUG)

    # Add the rotating file handler
    log_handler = RotatingFileHandler(filename=log_file, maxBytes=max_bytes, backupCount=backup_count)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(formatter)
    the_logger.addHandler(log_handler)

    # Add the console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    the_logger.addHandler(console_handler)

    # Suppress SSL warnings in logs if instructed to
    if suppress_requests_messages:
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    return the_logger


def Attributor():
    """Collection of attribution functions"""

    # Paths
    fgdb_folder = r"F:\Shares\FGDB_Services"
    sde = os.path.join(fgdb_folder, r"DatabaseConnections\COSPW@imSPFLD@MCWINTCWDB.sde")
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = r"memory\tempData"

    # Environment
    arcpy.env.overwriteOutput = True

    # Expressions
    spatial_start = "str(int(!NAD83XSTART!))[2:4] + str(int(!NAD83YSTART!))[2:4] + '-' + str(int(!NAD83XSTART!))[4] + str(int(!NAD83YSTART!))[4] + '-' + str(int(!NAD83XSTART!))[-2:] + str(int(!NAD83YSTART!))[-2:]"
    spatial_end = "str(int(!NAD83XEND!))[2:4] + str(int(!NAD83YEND!))[2:4] + '-' + str(int(!NAD83XEND!))[4] + str(int(!NAD83YEND!))[4] + '-' + str(int(!NAD83XEND!))[-2:] + str(int(!NAD83YEND!))[-2:]"
    spatial_id_line_sewer = "!SPATAILSTART! + '_' + !SPATAILEND!"  # Yes it's seriously misspelled
    spatial_id_line_storm = "!SPATIALSTART! + '_' + !SPATIALEND!"
    spatial_id_point = "str(int(!NAD83X!))[2:4] + str(int(!NAD83Y!))[2:4] + '-' + str(int(!NAD83X!))[4] + str(int(!NAD83Y!))[4] + '-' + str(int(!NAD83X!))[-2:] + str(int(!NAD83Y!))[-2:]"

    # Expression to select manholes or inlets to calculate a Facility ID for (if it's stormwater or non-city owned)
    manhole_main_exception = "(WATERTYPE = 'SW' or OWNEDBY = -2) And FACILITYID IS NULL"
    cleanout_exception = "OWNEDBY = -2 and FACILITYID IS NULL"

    def sewer_attribution():
        """Attribute sewer assets

        Takes the list of assets and their type then uses it to calculate the geometry and spatial fields. If the asset is a noted exception, calculate the Facility ID.

        Exceptions:
            * Gravity mains: privately owned sewers or stormwater sewers that output to a combined sewer.
            * Cleanouts: privately owned sewers
            * Inlets: all inlets

        """

        # Paths
        sewer = os.path.join(sde, "SewerStormwater")
        sewer_main = os.path.join(sewer, "ssGravityMain")
        sewer_manhole = os.path.join(sewer, "ssManhole")
        sewer_cleanout = os.path.join(sewer, "ssCleanout")
        sewer_inlet = os.path.join(sewer, "ssInlet")
        sewer_assets = [[sewer_main, "line", "Sewer Mains"],
                        [sewer_manhole, "point", "Sewer Manholes"],
                        [sewer_cleanout, "point", "Sewer Cleanouts"],
                        [sewer_inlet, "point", "Sewer Inlets"]]

        # Attribution
        for asset in sewer_assets:
            logger.info(f"--- --- {asset[2]} Start")
            arcpy.MakeFeatureLayer_management(asset[0], "asset_temp")
            selection_by_date = arcpy.SelectLayerByAttribute_management("asset_temp", "NEW_SELECTION", f"LASTEDITOR <> 'COSPW' and FACILITYID IS NULL")

            # Looping through the list
            if int(arcpy.GetCount_management(selection_by_date).getOutput(0)) > 0:
                if asset[1] == "point":
                    arcpy.CalculateGeometryAttributes_management("asset_temp", [["NAD83X", "POINT_X"],
                                                                                ["NAD83Y", "POINT_Y"]])
                    arcpy.CalculateField_management("asset_temp", "SPATIALID", spatial_id_point, "PYTHON3")
                elif asset[1] == "line":
                    arcpy.CalculateGeometryAttributes_management("asset_temp", [["NAD83XSTART", "LINE_START_X"],
                                                                                ["NAD83YSTART", "LINE_START_Y"],
                                                                                ["NAD83XEND", "LINE_END_X"],
                                                                                ["NAD83YEND", "LINE_END_Y"]])
                    arcpy.CalculateFields_management("asset_temp", "PYTHON3", [["SPATAILSTART", spatial_start],
                                                                               ["SPATAILEND", spatial_end],
                                                                               ["SPATIALID", spatial_id_line_sewer]])

                # Facility ID exceptions
                if asset[0] in {sewer_manhole, sewer_main}:
                    selection = arcpy.SelectLayerByAttribute_management("asset_temp", "NEW_SELECTION", manhole_main_exception)
                    arcpy.CalculateField_management(selection, "FACILITYID", "!SPATIALID!", "PYTHON3")
                elif asset[0] == sewer_cleanout:
                    selection = arcpy.SelectLayerByAttribute_management("asset_temp", "NEW_SELECTION", cleanout_exception)
                    arcpy.CalculateField_management(selection, "FACILITYID", "!SPATIALID!", "PYTHON3")
                elif asset[0] == sewer_inlet:
                    arcpy.CalculateField_management("asset_temp", "FACILITYID", "!SPATIALID!", "PYTHON3")
            logger.info(f"--- --- {asset[2]} Complete")

    def storm_attribution():
        """Attribute storm assets

        Takes the list of assets and their type then uses it to calculate the geometry and spatial fields.

        """

        # Paths
        storm = os.path.join(sde, "Stormwater")
        storm_main = os.path.join(storm, "swGravityMain")
        storm_manhole = os.path.join(storm, "swManhole")
        storm_cleanout = os.path.join(storm, "swCleanout")
        storm_inlet = os.path.join(storm, "swInlet")
        storm_discharge = os.path.join(storm, "swDischargePoint")
        storm_culvert = os.path.join(storm, "swCulvert")
        storm_assets = [[storm_main, "line", "Storm Mains"],
                        [storm_manhole, "point", "Storm Manholes"],
                        [storm_cleanout, "point", "Storm Cleanouts"],
                        [storm_inlet, "point", "Storm Inlets"],
                        [storm_discharge, "point", "Storm Discharge Points"],
                        [storm_culvert, "line", "Storm Culverts"]]

        # Attribution
        for asset in storm_assets:

            # Looping through the list
            logger.info(f"--- --- {asset[2]} Start")
            arcpy.MakeFeatureLayer_management(asset[0], "asset_temp")
            selection_by_date = arcpy.SelectLayerByAttribute_management("asset_temp", "NEW_SELECTION", f"LASTEDITOR <> 'COSPW' and FACILITYID IS NULL")

            if int(arcpy.GetCount_management(selection_by_date).getOutput(0)) > 0:
                if asset[1] == "line":
                    arcpy.CalculateGeometryAttributes_management("asset_temp", [["NAD83XSTART", "LINE_START_X"],
                                                                                ["NAD83YSTART", "LINE_START_Y"],
                                                                                ["NAD83XEND", "LINE_END_X"],
                                                                                ["NAD83YEND", "LINE_END_Y"]])
                    arcpy.CalculateFields_management("asset_temp", "PYTHON3", [["SPATIALSTART", spatial_start],
                                                                               ["SPATIALEND", spatial_end],
                                                                               ["SPATIALID", spatial_id_line_storm],
                                                                               ["FACILITYID", spatial_id_line_storm]])
                elif asset[1] == "point":
                    arcpy.CalculateGeometryAttributes_management("asset_temp", [["NAD83X", "POINT_X"],
                                                                                ["NAD83Y", "POINT_Y"]])
                    arcpy.CalculateFields_management("asset_temp", "PYTHON3", [["SPATIALID", spatial_id_point],
                                                                               ["FACILITYID", spatial_id_point]])
            logger.info(f"--- --- {asset[2]} Complete")

    def gps_attribution():
        """Append new GPS shapefiles in the Y: drive to the gpsNode feature class on the SDE then calculate their facility ID

        Use regex and the text file to sort through folders in the Y: drive to find those with the correct formatting and create a list of those. Use this list to append the shapefiles
        within the folders to gpsNode. After this, update the text file with the current date. Any folder with a date before this new date will not be appended next runtime.

        """

        # Paths
        engineering = os.path.join(sde, "SewerEngineering")
        gps_points = os.path.join(engineering, "gpsNode")
        shape_folder = "Y:\\"

        # Grab last updated date from a text file
        f = open("last_updated.txt", "r")
        last_updated = [f.read()]
        datetime_format = "%Y-%m-%d"

        # Create a list of folders to be appended
        folder_list = []
        for root, dirs, files in os.walk(shape_folder, topdown=False):
            [folder_list.append(name) for name in dirs if re.search("[-]", name) and not re.search("[a-zA-z. ]", name) and
             datetime.datetime.strptime(last_updated[0], datetime_format) < datetime.datetime.strptime(name, datetime_format)]  # Add any folder without a letter in it

        # Append new folders
        if len(folder_list) > 0:
            for folder in folder_list:
                directory = os.path.join(shape_folder, folder)
                for file in os.listdir(directory):
                    if file.endswith("insMACP.shp"):
                        file_path = os.path.join(directory, file)
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
            f = open("last_updated.txt", "w")
            f.write(f"{new_date}")
            f.close()

    # Log file paths
    script_folder = os.path.dirname(sys.argv[0])
    script_name_no_ext = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    log_folder = os.path.join(script_folder, "Log_Files")
    log_file = os.path.join(log_folder, f"{script_name_no_ext}.log")
    logger = start_rotating_logging(log_file, 10000, 1, True)

    # Run the above functions with logger error catching and formatting
    try:

        logger.info("")
        logger.info("--- Script Execution Started ---")

        logger.info("--- --- --- --- Sewer Attribution Start")
        sewer_attribution()
        logger.info("--- --- --- --- Sewer Attribution Complete")

        logger.info("--- --- --- --- Storm Attribution Start")
        storm_attribution()
        logger.info("--- --- --- --- Storm Attribution Complete")

        logger.info("--- --- --- --- GPS Attribution Start")
        gps_attribution()
        logger.info("--- --- --- --- GPS Attribution Complete")

    except ValueError as e:
        exc_traceback = sys.exc_info()[2]
        error_text = f'Line: {exc_traceback.tb_lineno} --- {e}'
        try:
            logger.error(error_text)
        except NameError:
            print(error_text)

    except (IOError, KeyError, NameError, IndexError, TypeError, UnboundLocalError):
        tbinfo = traceback.format_exc()
        try:
            logger.error(tbinfo)
        except NameError:
            print(tbinfo)

    finally:
        try:
            logger.info("--- Script Execution Completed ---")
            logging.shutdown()
        except NameError:
            pass


def main():
    Attributor()


if __name__ == '__main__':
    main()
