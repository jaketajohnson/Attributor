"""
 SYNOPSIS

     Geospatial (WIP script update, do not use)

 DESCRIPTION

    * Attributes the spatial and facility identifiers for the sewer and stormwater tables
    * Calculates the GXPCity field for sewer gravity mains by finding only gravity mains in that ward polygon
    * Appends new GPS points from the Y: drive and calculates a spatial identifier

 REQUIREMENTS

     Python 3
     arcpy
 """

import GPS
import Logging
import Sewer
import Storm


if __name__ == "__main__":
    Logging.logger.info("Script Execution Start")

    Logging.logger.info("---Sewer Start")
    Sewer.manholes()
    Sewer.inlets()
    Sewer.cleanouts()
    Sewer.gravity_mains()
    Logging.logger.info("---Sewer Finish")

    Logging.logger.info("---Storm Start")
    Storm.manholes()
    Storm.inlets()
    # Storm.cleanouts()
    Storm.gravity_mains()
    Logging.logger.info("---Storm Start")

    Logging.logger.info("---GPS Start")
    GPS.gps_attribution()
    Logging.logger.info("---GPS End")

    Logging.logger.info("Script Execution Finish")
