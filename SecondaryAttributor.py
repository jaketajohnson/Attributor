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
import traceback
import os
import re
import sys
sys.path.insert(0, "Y:/Scripts")
import Logging

# Paths - Geodatabase
geodatabase_services_folder = "Z:\\"
sde = os.path.join(geodatabase_services_folder, r"DatabaseConnections\COSPW@imSPFLD@MCWINTCWDB.sde")
data = os.path.join(geodatabase_services_folder, "Data")
attributor = os.path.join(data, "Attributor.gdb")

# Environment
arcpy.env.overwriteOutput = True

# Common feature classes and selecting edited assets
sewer = os.path.join(sde, "SewerStormwater")
sewer_main = os.path.join(sewer, "ssGravityMain")
sewer_manhole = os.path.join(sewer, "ssManhole")
arcpy.MakeFeatureLayer_management(sewer_main, "asset_temp_mains")
arcpy.MakeFeatureLayer_management(sewer_manhole, "asset_temp_manholes")
sewer_assets = ["asset_temp_mains", "asset_temp_manholes"]


@Logging.insert("Wards", 1)
def ward():
    """Attribute the sewer main GXPCity field using the administrative area polygons' label field its center is in. If it's a ward, add text to the label."""

    # Paths
    area = os.path.join(attributor, "AdministrativeArea")  # Townships and wards polygon

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


@Logging.insert("Sewer Districts", 1)
def sewer_districts():
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


@Logging.insert("Sewer Plants", 1)
def sewer_plants():
    """Attribute the sewer treatment plant field; uses a modified district layer where districts with the same plant are merged."""

    # Paths
    plants = os.path.join(attributor, "TreatmentPlants")

    # Attribution
    with arcpy.da.SearchCursor(plants, ["OID@", "NAME"]) as cursor:
        for row in cursor:
            selection = arcpy.SelectLayerByAttribute_management(plants, "NEW_SELECTION", f"OBJECTID = {row[0]}")
            for asset in sewer_assets:
                sewer_selection = arcpy.SelectLayerByLocation_management(asset, "HAVE_THEIR_CENTER_IN", selection, None, "NEW_SELECTION")
                arcpy.CalculateField_management(sewer_selection, "PLANT", f"'{row[1]}'", "PYTHON3")


@Logging.insert("Detention Ponds", 1)
def detention_ponds():
    """Calculate the Facility ID of detention ponds using its centroid coordinates"""

    # Paths
    storm = os.path.join(sde, "Stormwater")
    detention_areas = os.path.join(storm, "swDetention")

    # Attribution
    facility_id = "str(!SHAPE!.centroid.X)[2:4] + str(!SHAPE!.centroid.Y)[2:4] + '-' + str(!SHAPE!.centroid.X)[4] + str(!SHAPE!.centroid.Y)[4] + '-' + " \
                  "str(!SHAPE!.centroid.X)[-2:] + str(!SHAPE!.centroid.Y)[-2:]"
    arcpy.CalculateField_management(detention_areas, "FACILITYID", facility_id, "PYTHON3")


if __name__ == "__main__":
    traceback_info = traceback.format_exc()
    try:
        Logging.logger.info("Script Execution Started")
        ward()
        sewer_districts()
        sewer_plants()
        detention_ponds()
        Logging.logger.info("Script Execution Finished")
    except (IOError, NameError, KeyError, IndexError, TypeError, UnboundLocalError, ValueError):
        Logging.logger.info(traceback_info)
    except NameError:
        print(traceback_info)
    except arcpy.ExecuteError:
        Logging.logger.error(arcpy.GetMessages(2))
    except:
        Logging.logger.info("An unspecified exception occurred")
