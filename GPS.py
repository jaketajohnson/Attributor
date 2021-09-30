"""
 SYNOPSIS

    Organizes new GPS shape files and appends them to the server-side list

 DESCRIPTION

    * Locates folders containing shape files and selects only the newer ones
    * Appends the points in the shapefile to the server-side list
    * Updates last-updated.txt to the current date; this is used to define what is "new" when this is run next

 REQUIREMENTS

     Python 3
     arcpy
 """

import arcpy
import os
import datetime
import traceback
import re
import sys
sys.path.insert(0, "Y:/Scripts")
import Logging

# Paths - Geodatabase
geodatabase_services_folder = "Z:\\"
sde = os.path.join(geodatabase_services_folder, r"DatabaseConnections\COSPW@imSPFLD@MCWINTCWDB.sde")
data = os.path.join(geodatabase_services_folder, "Data")

# Paths - GPS
engineering = os.path.join(sde, "SewerEngineering")
gps_points = os.path.join(engineering, "gpsNode")
shape_folder = "V:\\"

# Expressions
spatial_id_point = "str(int(!NAD83X!))[2:4] + str(int(!NAD83Y!))[2:4] + '-' + str(int(!NAD83X!))[4] + str(int(!NAD83Y!))[4] + '-' + str(int(!NAD83X!))[-2:] + str(int(!NAD83Y!))[-2:]"


def gps_attribution():
    """Append new GPS shapefiles in the Y: drive to the gpsNode feature class on the SDE then calculate their facility ID

        1. Use regex and the text file to sort through folders in the Y: drive to find those with the correct formatting and date and create a list of those.
        2. Use this list to append the shapefiles within the folders to gpsNode.
        3. After this, update the text file with the current date. Any folder with a date before this new date will not be appended next runtime.

    """

    # Grab last updated date from a text file
    last_updated_file = open("last_updated.txt", "r")
    last_updated = [last_updated_file.read()]
    datetime_format = "%Y-%m-%d"
    Logging.logger.info(f"---Last updated: {last_updated[0]}")

    # Create a list of folders to be appended
    folder_list = []
    for root, dirs, files in os.walk(shape_folder, topdown=False):
        [folder_list.append(folders) for folders in dirs if re.search("[-]", folders) and not re.search("[a-zA-z. ]", folders) and
         datetime.datetime.strptime(last_updated[0], datetime_format) < datetime.datetime.strptime(folders, datetime_format)]  # Add any folder without a letter in it

    # Append new folders
    folder_list_length = len(folder_list)
    if folder_list_length > 0:
        Logging.logger.info(f"---START Append and Spatial ID - COUNT={folder_list_length}")
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
        Logging.logger.info(f"---FINISH Append and Spatial ID - COUNT={folder_list_length}")

        Logging.logger.info(f"---START Update Last_Updated")
        # Update last_update.txt
        new_date = datetime.datetime.now().strftime(datetime_format)
        last_updated_file = open("last_updated.txt", "w")
        last_updated_file.write(f"{new_date}")
        last_updated_file.close()
        Logging.logger.info(f"---FINISH Update Last_Updated - DATE={new_date}")
    else:
        Logging.logger.info(f"---PASS Append and Update - COUNT={folder_list_length}")


if __name__ == "__main__":
    traceback_info = traceback.format_exc()
    try:
        Logging.logger.info("Script Execution Started")
        gps_attribution()
        Logging.logger.info("Script Execution Finished")
    except (IOError, NameError, KeyError, IndexError, TypeError, UnboundLocalError, ValueError):
        Logging.logger.info(traceback_info)
    except NameError:
        print(traceback_info)
    except arcpy.ExecuteError:
        Logging.logger.error(arcpy.GetMessages(2))
    except:
        Logging.logger("An unspecified exception occurred")
