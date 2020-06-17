"""
 SYNOPSIS

     Attributor

 DESCRIPTION

     This script attributes sewer/stormwater tables

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


def start_rotating_logging(log_path=None,
                           max_bytes=100000,
                           backup_count=2,
                           suppress_requests_messages=True):
    """
    This function starts logging with a rotating file handler.  If no log
    path is provided it will start logging in the same folder as the script,
    with the same name as the script.

    Parameters
    ----------
    log_path : str
        the path to use in creating the log file
    max_bytes : int
        the maximum number of bytes to use in each log file
    backup_count : int
        the number of backup files to create
    suppress_requests_messages : bool
        If True, then SSL warnings from the requests and urllib3
        modules will be suppressed

    Returns
    -------
    the_logger : logging.logger
        the logger object, ready to use
    """
    formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(message)s",
                                  datefmt="%Y-%m-%d %H:%M:%S")

    # If no log path was provided, construct one
    script_path = sys.argv[0]
    script_folder = os.path.dirname(script_path)
    script_name = os.path.splitext(os.path.basename(script_path))[0]
    if not log_path:
        log_path = os.path.join(script_folder, "{}.log".format(script_name))

    # Start logging
    the_logger = logging.getLogger(script_name)
    the_logger.setLevel(logging.DEBUG)

    # Add the rotating file handler
    log_handler = RotatingFileHandler(filename=log_path,
                                      maxBytes=max_bytes,
                                      backupCount=backup_count)
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

    # Paths
    fgdb_folder = r"F:\Shares\FGDB_Services"
    sde = os.path.join(fgdb_folder, r"DatabaseConnections\COSPW@imSPFLD@MCWINTCWDB.sde")
    temp_fgdb = os.path.join(fgdb_folder, r"Data\Attributor.gdb")

    # Environment
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = r"memory\tempData"

    # Expressions
    spatial_start = "str(int(!NAD83XSTART!))[2:4] + str(int(!NAD83YSTART!))[2:4] + '-' + str(int(!NAD83XSTART!))[4] + str(int(!NAD83YSTART!))[4] + '-' + str(int(!NAD83XSTART!))[-2:] + str(int(!NAD83YSTART!))[-2:]"
    spatial_end = "str(int(!NAD83XEND!))[2:4] + str(int(!NAD83YEND!))[2:4] + '-' + str(int(!NAD83XEND!))[4] + str(int(!NAD83YEND!))[4] + '-' + str(int(!NAD83XEND!))[-2:] + str(int(!NAD83YEND!))[-2:]"
    spatial_id_line_sewer = "!SPATAILSTART! + '_' + !SPATAILEND!"  # Yes it's seriously misspelled
    spatial_id_line_storm = "!SPATIALSTART! + '_' + !SPATIALEND!"
    spatial_id_point = "str(int(!NAD83X!))[2:4] + str(int(!NAD83Y!))[2:4] + '-' + str(int(!NAD83X!))[4] + str(int(!NAD83Y!))[4] + '-' + str(int(!NAD83X!))[-2:] + str(int(!NAD83Y!))[-2:]"

    # Special case expressions
    sewer_stormwater_storm = "WATERTYPE = 'SW' And FACILITYID IS NULL"
    sewer_stormwater_private = "OWNEDBY = -2 And FACILITYID IS NULL"

    def facility_id_exceptions(asset, filter_selection):
        # Template for calculating FACILITYID under special cases (e.g.: stormwater sewers in sewer tables or private sewers)
        # [0] = input asset, [1] = expression to filter features
        selection = arcpy.SelectLayerByAttribute_management(asset, "NEW_SELECTION", filter_selection)
        if int(arcpy.GetCount_management(selection).getOutput(0)) > 0:
            arcpy.CalculateField_management(selection, "FACILITYID", "!SPATIALID!", "PYTHON3")
        else:
            pass

    def sewer_attribution():

        # Feature Classes
        sewer = os.path.join(sde, "SewerStormwater")
        sewer_main = os.path.join(sewer, "ssGravityMain")
        sewer_manhole = os.path.join(sewer, "ssManhole")
        sewer_cleanout = os.path.join(sewer, "ssCleanout")
        sewer_inlet = os.path.join(sewer, "ssInlet")

        sewer_assets = [[sewer_main, "line"],
                        [sewer_manhole, "point"],
                        [sewer_cleanout, "point"],
                        [sewer_inlet, "point"]]

        for asset in sewer_assets:

            # Make a temp feature layer then calculate fields depending on if asset is a point or a line
            arcpy.MakeFeatureLayer_management(asset[0], "asset_temp")

            if asset[1] == "line":
                arcpy.CalculateGeometryAttributes_management("asset_temp", [["NAD83XSTART", "LINE_START_X"],
                                                                            ["NAD83YSTART", "LINE_START_Y"],
                                                                            ["NAD83XEND", "LINE_END_X"],
                                                                            ["NAD83YEND", "LINE_END_Y"]])
                arcpy.CalculateFields_management("asset_temp", "PYTHON3", [["SPATAILSTART", spatial_start],
                                                                           ["SPATAILEND", spatial_end],
                                                                           ["SPATIALID", spatial_id_line_sewer]])
                facility_id_exceptions(asset[0], sewer_stormwater_storm)
                facility_id_exceptions(asset[0], sewer_stormwater_private)

            elif asset[1] == "point":
                arcpy.CalculateGeometryAttributes_management("asset_temp", [["NAD83X", "POINT_X"],
                                                                            ["NAD83Y", "POINT_Y"]])
                arcpy.CalculateField_management("asset_temp", "SPATIALID", spatial_id_point, "PYTHON3")

                # Only sewer_inlet and sewer_manhole need to have Facility ID calculated for type points
                if asset[0] == sewer_manhole:
                    facility_id_exceptions(asset[0], sewer_stormwater_storm)
                    facility_id_exceptions(asset[0], sewer_stormwater_private)
                elif asset[0] == sewer_inlet:
                    arcpy.CalculateField_management(asset[0], "FACILITYID", "!SPATIALID!", "PYTHON3")
                elif asset[0] == sewer_cleanout:
                    facility_id_exceptions(asset[0], sewer_stormwater_private)

            else:
                pass

    def storm_attribution():

        # Feature Classes
        storm = os.path.join(sde, "Stormwater")
        storm_main = os.path.join(storm, "swGravityMain")
        storm_manhole = os.path.join(storm, "swManhole")
        storm_cleanout = os.path.join(storm, "swCleanout")
        storm_inlet = os.path.join(storm, "swInlet")
        storm_discharge = os.path.join(storm, "swDischargePoint")
        storm_culvert = os.path.join(storm, "swCulvert")

        storm_assets = [[storm_main, "line"],
                        [storm_manhole, "point"],
                        [storm_cleanout, "point"],
                        [storm_inlet, "point"],
                        [storm_discharge, "point"],
                        [storm_culvert, "line"]]

        for asset in storm_assets:

            # Make a temp feature layer then calculate fields depending on if asset is a point or a line
            arcpy.MakeFeatureLayer_management(asset[0], "asset_temp")

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
            else:
                pass

    def gps_attribution():

        # Feature Classes
        engineering = os.path.join(sde, "SewerEngineering")
        gps_points = os.path.join(engineering, "gpsNode")

        # Paths
        shape_folder = "Y:\\"

        # Grab last updated date from a text file, define a date format to use (YYYY-mm-dd)
        f = open("last_updated.txt", "r")
        last_updated = [f.read()]
        datetime_format = "%Y-%m-%d"

        # Using os.walk, append folders to folder_list if the folder name has a dash and no letters, period, or spaces.
        folder_list = []
        for root, dirs, files in os.walk(shape_folder, topdown=False):
            [folder_list.append(name) for name in dirs if re.search("[-]", name) and not re.search("[a-zA-z. ]", name) and
             datetime.datetime.strptime(last_updated[0], datetime_format) < datetime.datetime.strptime(name, datetime_format)]  # Add any folder without a letter in it

        # If the list is not empty, select files in each folder that end in " insMACP.shp" and append them to SewerEngineering/gpsNodes
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

            # Update last_update.txt to show new date. Next time this runs it will compare folder names to the date this last ran. To work you MUST close the file after writing
            new_date = datetime.datetime.now().strftime(datetime_format)
            f = open("last_updated.txt", "w")
            f.write(f"{new_date}")
            f.close()
        else:
            pass

    def ward_attribution():

        # Feature Classes
        sewer = os.path.join(sde, "SewerStormwater")
        sewer_main = os.path.join(sewer, "ssGravityMain")

        # Paths
        area = os.path.join(temp_fgdb, "AdministrativeArea")  # Townships and wards polygons

        with arcpy.da.SearchCursor(area, ["OID@", "Label"]) as cursor:
            for row in cursor:

                # Uses the OID to create a label to be used as the city field in sewer_mains
                if re.search(fr"\bWard\b", str(row[1])):
                    city = f"'Springfield ({row[1]})'"
                else:
                    city = f"'{row[1]}'"

                # Selects sewer mains inside the current area polygon
                selection = arcpy.SelectLayerByAttribute_management(area, "NEW_SELECTION", fr"OBJECTID = {row[0]}")
                sewer_selection = arcpy.SelectLayerByLocation_management(sewer_main, "HAVE_THEIR_CENTER_IN", selection, None, "NEW_SELECTION")

                arcpy.CalculateField_management(sewer_selection, 'GXPCity', f"{city}", 'PYTHON3')
        del cursor

    # Run nested functions
    sewer_attribution()
    storm_attribution()
    gps_attribution()
    ward_attribution()


def main():
    """
    Main execution code
    """
    # Make a few variables to use
    # script_folder = os.path.dirname(sys.argv[0])
    log_file_folder = r"C:\Scripts\Attributor\Log_Files"
    script_name_no_ext = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    log_file = os.path.join(log_file_folder, "{}.log".format(script_name_no_ext))
    logger = None

    try:

        # Get logging going
        logger = start_rotating_logging(log_path=log_file,
                                        max_bytes=500000,
                                        backup_count=1,
                                        suppress_requests_messages=True)
        logger.info("")
        logger.info("--- Script Execution Started ---")

        Attributor()
        logger.info("Completed Attributor processing")

    except ValueError as e:
        exc_traceback = sys.exc_info()[2]
        error_text = 'Line: {0} --- {1}'.format(exc_traceback.tb_lineno, e)
        try:
            logger.error(error_text)
        except NameError:
            print(error_text)

    except (IOError, KeyError, NameError, IndexError, TypeError, UnboundLocalError, arcpy.ExecuteError):
        tbinfo = traceback.format_exc()
        try:
            logger.error(tbinfo)
        except NameError:
            print(tbinfo)

    finally:
        # Shut down logging
        try:
            logger.info("--- Script Execution Completed ---")
            logging.shutdown()
        except NameError:
            pass


if __name__ == '__main__':
    main()
