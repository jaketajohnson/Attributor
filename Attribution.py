"""
 SYNOPSIS

     Main script for sewer stormwater/stormwater attribution

 DESCRIPTION

    * Simply the main script file where functions from other scripts are added for running all at once

 REQUIREMENTS

     Python 3
     arcpy
 """

import Logging
import GPS
import Sewer
import Storm


if __name__ == "__main__":
    Logging.logger.info("Script Execution Start")

    # Sewer Stormwater
    Logging.logger.info("Sewer Start")
    Sewer.manholes()
    Sewer.inlets()
    Sewer.cleanouts()
    Sewer.gravity_mains()
    Logging.logger.info("Sewer Finish")

    # Stormwater
    Logging.logger.info("Storm Start")
    Storm.manholes()
    Storm.inlets()
    Storm.cleanouts()
    Storm.discharges()
    Storm.culverts()
    Storm.gravity_mains()
    Logging.logger.info("Storm Start")

    # GPS Points
    Logging.logger.info("GPS Start")
    GPS.gps_attribution()
    Logging.logger.info("GPS End")

    Logging.logger.info("Script Execution Finish")
