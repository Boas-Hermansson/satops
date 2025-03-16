#!/bin/bash

# URL to fetch the TLE data
TLE_URL="https://celestrak.org/NORAD/elements/gp.php?NAME=$(echo $1 | sed 's/ /%20/g')&FORMAT=TLE"

# Fetch the TLE data and store it in a variable
TLE_DATA=$(curl -s "$TLE_URL")

# Write the TLE data to the file "disco.tle"
SCRIPT_DIR=$(dirname "$0")
echo "$TLE_DATA" > "$SCRIPT_DIR/disco.tle"
echo "Successfully updated TLE data for $1"