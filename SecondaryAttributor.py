"""
 SYNOPSIS

     SecondaryAttributor

 DESCRIPTION

    * Attributes location based fields such as wards or sewer districts

 REQUIREMENTS

     Python 3
     arcpy
     natsort
 """

import arcpy
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


def SecondaryAttributor():
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

    @logging_lines("Wards")
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

    @logging_lines("Districts")
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
                    arcpy.CalculateField_management(sewer_selection, "DISTRICT", f"'{row[1]}'", "PYTHON3")
        del cursor

    @logging_lines("Plants")
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
                    arcpy.CalculateField_management(sewer_selection, "PLANT", f"'{row[1]}'", "PYTHON3")
        del cursor

    @logging_lines("Ponds")
    def pond_attribution():
        """Calculate the Facility ID of detention ponds using its centroid coordinates"""

        # Paths
        storm = os.path.join(sde, "Stormwater")
        detention_areas = os.path.join(storm, "swDetention")

        # Attribution
        facility_id = "str(!SHAPE!.centroid.X)[2:4] + str(!SHAPE!.centroid.Y)[2:4] + '-' + str(!SHAPE!.centroid.X)[4] + str(!SHAPE!.centroid.Y)[4] + '-' + " \
                      "str(!SHAPE!.centroid.X)[-2:] + str(!SHAPE!.centroid.Y)[-2:]"
        arcpy.CalculateField_management(detention_areas, "FACILITYID", facility_id, "PYTHON3")

    # Try running above scripts
    try:
        ward_attribution()
        district_attribution()
        plant_attribution()
        pond_attribution()
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
    SecondaryAttributor()


if __name__ == '__main__':
    main()
