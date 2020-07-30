import arcpy
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


def SecondaryAttributor():
    """Collection of attribution functions"""

    # Paths
    fgdb_folder = r"F:\Shares\FGDB_Services"
    sde = os.path.join(fgdb_folder, r"DatabaseConnections\COSPW@imSPFLD@MCWINTCWDB.sde")
    temp_fgdb = os.path.join(fgdb_folder, r"Data\Attributor.gdb")
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = r"memory\tempData"

    # Environment
    arcpy.env.overwriteOutput = True

    # Common feature classes and selecting edited assets
    sewer = os.path.join(sde, "SewerStormwater")

    sewer_main = os.path.join(sewer, "ssGravityMain")
    arcpy.MakeFeatureLayer_management(sewer_main, "asset_temp_mains")

    sewer_manhole = os.path.join(sewer, "ssManhole")
    arcpy.MakeFeatureLayer_management(sewer_manhole, "asset_temp_manholes")
    sewer_assets = ["asset_temp_mains", "asset_temp_manholes"]

    # Selection edited assets

    def ward_attribution():
        """Attribute the sewer main GXPCity field using the administrative area polygons' label field its center is in. If it's a ward, add text to the label."""

        # Paths
        area = os.path.join(temp_fgdb, "AdministrativeArea")  # Townships and wards polygon

        # Attribution
        with arcpy.da.SearchCursor(area, ["OID@", "Label"]) as cursor:
            for row in cursor:
                if re.search(fr"\bWard\b", str(row[1])):
                    city = f"'Springfield ({row[1]})'"
                else:
                    city = f"'{row[1]}'"
                selection = arcpy.SelectLayerByAttribute_management(area, "NEW_SELECTION", f"OBJECTID = {row[0]}")
                sewer_selection = arcpy.SelectLayerByLocation_management("asset_temp_mains", "HAVE_THEIR_CENTER_IN", selection, None, "NEW_SELECTION")
                arcpy.CalculateField_management(sewer_selection, "GXPCity", f"{city}", "PYTHON3")
        del cursor

    def district_attribution():
        """Attribute the sewer main Sewer District field using the Sewer Engineering polygons' label field its center is in."""

        # Paths
        engineering = os.path.join(sde, "SewerEngineering")
        districts = os.path.join(engineering, "ssSewerDistrict")

        # Attribution
        with arcpy.da.SearchCursor(districts, ["OID@", "NAME"]) as cursor:
            for row in cursor:
                selection = arcpy.SelectLayerByAttribute_management(districts, "NEW_SELECTION", f"OBJECTID = {row[0]}")
                for asset in sewer_assets:
                    sewer_selection = arcpy.SelectLayerByLocation_management(asset, "HAVE_THEIR_CENTER_IN", selection, None, "NEW_SELECTION")
                    sewer_selection = arcpy.SelectLayerByAttribute_management(sewer_selection, "NEW_SELECTION", f"DISTRICT <> '{row[1]}'")
                    arcpy.CalculateField_management(sewer_selection, "DISTRICT", f"'{row[1]}'", "PYTHON3")
        del cursor

    def plant_attribution():
        """Attribute the sewer treatment plant field; uses a modified district layer where districts with the same plant are merged."""

        # Paths
        plants = os.path.join(temp_fgdb, "TreatmentPlants")

        # Attribution
        with arcpy.da.SearchCursor(plants, ["OID@", "NAME"]) as cursor:
            for row in cursor:
                selection = arcpy.SelectLayerByAttribute_management(plants, "NEW_SELECTION", f"OBJECTID = {row[0]}")
                for asset in sewer_assets:
                    sewer_selection = arcpy.SelectLayerByLocation_management(asset, "HAVE_THEIR_CENTER_IN", selection, None, "NEW_SELECTION")
                    sewer_selection = arcpy.SelectLayerByAttribute_management(sewer_selection, "NEW_SELECTION", f"PLANT <> '{row[1]}'")
                    arcpy.CalculateField_management(sewer_selection, "PLANT", f"'{row[1]}'", "PYTHON3")
        del cursor

    def pond_attribution():
        """Calculate the Facility ID of detention ponds using its centroid coordinates"""

        # Paths
        storm = os.path.join(sde, "Stormwater")
        detention_areas = os.path.join(storm, "swDetention")

        # Attribution
        facility_id = "str(!SHAPE!.centroid.X)[2:4] + str(!SHAPE!.centroid.Y)[2:4] + '-' + str(!SHAPE!.centroid.X)[4] + str(!SHAPE!.centroid.Y)[4] + '-' + " \
                      "str(!SHAPE!.centroid.X)[-2:] + str(!SHAPE!.centroid.Y)[-2:]"
        arcpy.CalculateField_management(detention_areas, "FACILITYID", facility_id, "PYTHON3")

    # Log file paths
    script_folder = os.path.dirname(sys.argv[0])
    script_name_no_ext = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    log_folder = os.path.join(script_folder, "Log_Files")
    log_file = os.path.join(log_folder, f"{script_name_no_ext}.log")
    logger = start_rotating_logging(log_file, 10000, 1, True)

    # Run the above functions with logger error catching and formatting
    try:

        logger.info("--- --- --- --- Ward Attribution Start")
        ward_attribution()
        logger.info("--- --- --- --- Ward Attribution Complete")

        logger.info("--- --- --- --- District Attribution Start")
        district_attribution()
        logger.info("--- --- --- --- District Attribution Complete")

        logger.info("--- --- --- --- Treatment Plant Attribution Start")
        plant_attribution()
        logger.info("--- --- --- --- Treatment Plant Attribution Complete")

        logger.info("--- --- --- --- Pond Attribution Start")
        pond_attribution()
        logger.info("--- --- --- --- Pond Attribution Complete")

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

    except arcpy.ExecuteError:
        try:
            logger.error(arcpy.GetMessages(2))
        except NameError:
            print(arcpy.GetMessages(2))

    finally:
        try:
            logger.info("--- Script Execution Completed ---")
            logging.shutdown()
        except NameError:
            pass


def main():
    SecondaryAttributor()


if __name__ == '__main__':
    main()
