"""
 SYNOPSIS

     SnowLines.py

 DESCRIPTION

     This script performs RouteStats and SnowLines processing

 REQUIREMENTS

     Python 3
     arcpy
 """

import arcpy
import logging
import os
import sys
import traceback
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


def is_valid_path(parser, path):
    """
    Check to see if a provided path is valid.  Works with argparse

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser object
    path : str
        The path to evaluate whether it exists or not

    Returns
    ----------
    path : str
        If the path exists, it is returned  if not, a
        parser.error is raised.
    """
    if not os.path.exists(path):
        parser.error("The path {0} does not exist!".format(path))
    else:
        return path


def Attributor():
    # Paths
    fgdb_folder = r"F:\Shares\FGDB_Services"
    # sde = os.path.join(fgdb_folder, r"DatabaseConnections\COSPW@imSPFLD@MCWINTCWDB.sde")
    # script_folder = os.path.dirname(sys.argv[0])
    temp_fgdb = os.path.join(fgdb_folder, "Data/Attributor.gdb")

    # Environment
    arcpy.env.overwriteOutput = True
    spatial_reference = arcpy.SpatialReference(3436)
    arcpy.env.workspace = temp_fgdb

    # Feature Datasets
    sewer = os.path.join(temp_fgdb, "SewerStormwater")
    storm = os.path.join(temp_fgdb, "Stormwater")

    # Feature Classes - Sewer Stormwater
    sewer_main = os.path.join(sewer, "ssGravityMain")
    sewer_manhole = os.path.join(sewer, "ssManhole")
    sewer_cleanout = os.path.join(sewer, "ssCleanout")
    sewer_inlet = os.path.join(sewer, "ssInlet")
    sewer_fitting = os.path.join(sewer, "ssFitting")

    # Feature Classes - Storm
    storm_main = os.path.join(storm, "swGravityMain")
    storm_manhole = os.path.join(storm, "swManhole")
    storm_cleanout = os.path.join(storm, "swCleanout")
    storm_inlet = os.path.join(storm, "swInlet")
    storm_discharge = os.path.join(storm, "swDischargePoint")
    storm_culvert = os.path.join(storm, "swCulvert")

    # List of feature classes for looping
    # [0] = feature class, [1] = point/line
    sewer_assets = [[sewer_main, "point"],
                    [sewer_manhole, "point"],
                    [sewer_cleanout, "point"],
                    [sewer_inlet, "point"],
                    [sewer_fitting, "point"]]

    storm_assets = [[storm_main, "line"],
                    [storm_manhole, "point"],
                    [storm_cleanout, "point"],
                    [storm_inlet, "point"],
                    [storm_discharge, "point"],
                    [storm_culvert, "line"]]

    # Expressions
    spatial_start = "str(int(!NAD83XSTART!))[2:4] + str(int(!NAD83YSTART!))[2:4] + '-' + str(int(!NAD83XSTART!))[4] + str(int(!NAD83YSTART!))[4] + '-' + str(int(!NAD83XSTART!)"
    spatial_end = "str(int(!NAD83XEND!))[2:4] + str(int(!NAD83YEND!))[2:4] + '-' + str(int(!NAD83XEND!))[4] + str(int(!NAD83YEND!))[4] + '-' + str(int(!NAD83XEND!))[-2:] + str(int(!NAD83YEND!))[-2:]"
    spatial_id_line_sewer = "!SPATAILSTART! + '_' + !SPATAILEND!"  # Yes it's seriously misspelled
    spatial_id_line_storm = "!SPATIALSTART! + '_' + !SPATIALEND!"
    spatial_id_point = "str(int(!NAD83X!))[2:4] + str(int(!NAD83Y!))[2:4] + '-' + str(int(!NAD83X!))[4] + str(int(!NAD83Y!))[4] + '-' + str(int(!NAD83X!))[-2:] + str(int(!NAD83Y!))[-2:]"

    def sewer_attribution():

        for asset in sewer_assets:

            # Make a temp feature layer then calculate fields depending on if asset is a point or a line
            arcpy.MakeFeatureLayer_management(asset[0], "asset_temp")

            if asset[1] == "line":
                arcpy.CalculateGeometryAttributes_management("asset_temp", [["NAD83XSTART", "LINE_START_X"],
                                                                            ["NAD83YSTART", "LINE_START_Y"],
                                                                            ["NAD83XEND", "LINE_END_X"],
                                                                            ["NAD83YEND", "LINE_END_Y"]], spatial_reference)
                arcpy.CalculateFields_management("asset_temp", "PYTHON3", [["SPATIALSTART", spatial_start],
                                                                           ["SPATIALEND", spatial_end],
                                                                           ["SPATIAL_ID", spatial_id_line_sewer]])
            elif asset[0] == "point":
                arcpy.CalculateGeometryAttributes_management("asset_temp", [["NAD83X", "POINT_X"],
                                                                            ["NAD83Y", "POINT_Y"]], spatial_reference)
                arcpy.CalculateFields_management("asset_temp", "PYTHON3", [["SPATIALID", spatial_id_point],
                                                                           ["FACILITYID", spatial_id_point]])

    def storm_attribution():

        for asset in storm_assets:

            # Make a temp feature layer then calculate fields depending on if asset is a point or a line
            arcpy.MakeFeatureLayer_management(asset[0], "asset_temp")

            if asset[1] == "line":
                arcpy.CalculateGeometryAttributes_management("asset_temp", [["NAD83XSTART", "LINE_START_X"],
                                                                            ["NAD83YSTART", "LINE_START_Y"],
                                                                            ["NAD83XEND", "LINE_END_X"],
                                                                            ["NAD83YEND", "LINE_END_Y"]], spatial_reference)
                arcpy.CalculateFields_management("asset_temp", "PYTHON3", [["SPATIALSTART", spatial_start],
                                                                           ["SPATIALEND", spatial_end],
                                                                           ["SPATIALID", spatial_id_line_storm],
                                                                           ["FACILITYID", spatial_id_line_storm]])
            elif asset[1] == "point":
                arcpy.CalculateGeometryAttributes_management("asset_temp", [["NAD83X", "POINT_X"],
                                                                            ["NAD83Y", "POINT_Y"]], spatial_reference)
                arcpy.CalculateFields_management("asset_temp", "PYTHON3", [["SPATIALID", spatial_id_point],
                                                                           ["FACILITYID", spatial_id_point]])

    # Run nested functions
    sewer_attribution()
    storm_attribution()


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
                                        max_bytes=100000,
                                        backup_count=2,
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
