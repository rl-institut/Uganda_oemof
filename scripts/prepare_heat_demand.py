# coding: utf-8
r"""
Inputs
-------
in_path1 : str
    ``raw/weatherdata``: path of input directory with weather data
in_path2 : str
    ``raw/distribution_households.csv``: path of input file with household distributions data
     as .csv
in_path3 : str
    ``raw/holidays.csv``: path of input file with holidays of all states in Germany as .csv
in_path4 : str
    ``raw/scalars.csv``: path of template for scalar data as .csv
in_path5 : str
    ``oemof_b3/schema/timeseries.csv``: path of input file with times series format as .csv
out_path : str
    ``results/_resources/load_profile_heat.csv``: path of output file with prepared data as .csv

Outputs
---------
pandas.DataFrame
    with grouped and aggregated data of heat demands.
    Data is grouped by region, energy source, technology and chp capability and contains
    net capacity and efficiency.

Description
-------------
The script...

"""
import datetime
import itertools
import os
import sys

import numpy as np
import pandas as pd
from demandlib import bdew

import oemof_b3.tools.data_processing as dp


def find_regional_files(path, region):
    """
    This function returns a list with file names to region

    Parameters
    ----------
    path : str
        Path to data

    region : str
        Region (eg. Brandenburg)

    Returns
    -------
    files_region : list
        List of file names of region
    """
    files_region = [file for file in os.listdir(path) if region in file]
    files_region = sorted(files_region)

    if not files_region:
        raise FileNotFoundError(
            f"No data of region {region} could be found in directory: {path}."
        )

    return files_region


def get_year(file_name):
    """
    This function returns a year from file name

    Parameters
    ----------
    file_name : str
        Name of file with year in it

    Returns
    -------
    year : int
        Year
    """
    # Add array with years to be searched for in file name
    years_search_array = np.arange(1990, 2051)
    newline = "\n"

    year_in_file = [
        year_searched
        for year_searched in years_search_array
        if str(year_searched) in file_name
    ]
    if len(year_in_file) == 1:
        year = year_in_file[0]
    else:
        raise ValueError(
            f"Your file {file_name} is missing a year or has multiple years "
            f"in its name." + newline + "Please provide data for a single year "
            "with that year in the file name."
        )

    return year


def get_holidays(path, year, region):
    """
    This function determines all holidays of a given region in a given year

    Parameters
    ----------
    path : str
        Input path
    year : int
        Year
    Returns
    -------
    holidays_dict : dict
        Dictionary with holidays

    """
    # Read all national holidays per state
    all_holidays = pd.read_csv(path)
    holidays_dict = {}

    # Get holidays in region
    holidays_filtered = all_holidays.loc[all_holidays["year"] == year]
    holidays_filtered = holidays_filtered[
        holidays_filtered["region"].str.contains(region)
    ]

    for row in holidays_filtered.iterrows():
        holidays_dict[
            datetime.date(row[1]["year"], row[1]["month"], row[1]["day"])
        ] = row[1]["holiday"]

    return holidays_dict


def check_central_decentral(demands, value, consumer, carrier):
    """
    This function checks whether the kind of heat is central or decentral adds it
    to yearly demands if it exists and otherwise to a new column in Dataframe

    Parameters
    ----------
    demands : pd.DataFrame
         DataFrame that contains yearly demands
    value : float
         Value of the yearly demand
    consumer : str
         Name of the consumer (eg.: ghd, efh, mfh)
    carrier : str
         Name of carrier (eg.: heat_central, heat_decentral)

    Returns
    -------
    demands : pd.DataFrame
         Updated DataFrame that contains yearly demands
    """
    if consumer + "_" + carrier in demands.columns:
        demands[consumer + "_" + carrier].values[0] = np.add(
            demands[consumer + "_" + carrier].values[0], value
        )
    else:
        demands[consumer + "_" + carrier] = [value]
    return demands


def get_heat_demand(path, scenario, carrier, region):
    """
    This function returns ghd and hh demands together with their unit of a given region and a
    given scenario

    Parameters
    ----------
    path : str
        Input path
    scenario : str
        Scenario e.g. "base"
    carrier : str
         Name of carrier (eg.: heat_central, heat_decentral)
    region : str
        Region (eg. Brandenburg)

    Returns
    -------
    demands : DataFrame
        Dataframe with total yearly demand of central and decentral heat per consumer
        (eg.: ghd, efh, mfh)
    demand_unit : str
        Unit of total demands (eg. GWh)

    """
    # Read state heat demands of ghd and hh sectors
    sc = dp.load_b3_scalars(path)  # TODO: Add ', sep=";"' if from schema
    consumers = ["ghd", "efh", "mfh"]
    demands = pd.DataFrame()
    newline = "\n"

    sc_filtered = dp.filter_df(sc, "tech", "demand")
    sc_filtered = dp.filter_df(sc_filtered, "carrier", carrier)
    sc_filtered = dp.filter_df(sc_filtered, "region", region)
    sc_filtered = dp.filter_df(sc_filtered, "scenario", scenario)

    if not (sc_filtered["var_unit"].values[0] == sc_filtered["var_unit"].values).all():
        raise ValueError(
            f"Unit mismatch in scalar data of heat demands. "
            f"Please make sure units match in {path}."
        )

    demand_unit = list(set(sc_filtered["var_unit"]))

    for consumer in consumers:
        sc_filtered_consumer = sc_filtered[sc_filtered["name"].str.contains(consumer)]

        if len(sc_filtered_consumer) > 1:
            print(
                f"User warning: There is duplicate demand of carrier '{carrier}', consumer "
                f"'{consumer}', region '{region}' and scenario '{scenario}' in {path}."
                + newline
                + "The demand is going to be summed up. "
                "Otherwise you have to rerun the calculation and provide only one demand of the "
                "same carrier, consumer, region and scenario."
            )

        for demand_value in sc_filtered_consumer["var_value"].values:
            check_central_decentral(demands, demand_value, consumer, carrier)

    return demands, demand_unit


def calculate_heat_load(carrier, holidays, temperature, yearly_demands):
    """
    This function calculates a heat load profile of Industry, trade,
    service (ghd: Gewerbe, Handel, Dienstleistung) and Household (hh: Haushalt)
    sectors

    Parameters
    ----------
    carrier : str
         Name of carrier (eg.: heat_central, heat_decentral)
    holidays : dict
        Dictionary with holidays
    temperature : DataFrame
         DataFrame with temperatures
    yearly_demands: DataFrame
         DataFrame with yearly demands per consumer

    Returns
    -------
    heat_load_total : pd.DataFrame
         DataFrame with total normalized heat load in year aggretated by consumers
         (eg.: ghd, efh, mfh)

    """
    # Add empty DataFrame for yearly heat loads
    heat_load_total = pd.DataFrame()

    # Add DataFrame time index for consumers heat loads
    heat_load_consumer = pd.DataFrame(
        index=pd.date_range(
            datetime.datetime(year, 1, 1, 0), periods=len(temperature), freq="H"
        )
    )

    # Calculate sfh (efh: Einfamilienhaus) heat load
    heat_load_consumer["efh" + "_" + carrier] = bdew.HeatBuilding(
        heat_load_consumer.index,
        holidays=holidays,
        temperature=temperature,
        shlp_type="EFH",
        building_class=6,
        wind_class=0,
        annual_heat_demand=yearly_demands["efh" + "_" + carrier][0],
        name="EFH",
        ww_incl=True,
    ).get_bdew_profile()

    # Calculate mfh (mfh: Mehrfamilienhaus) heat load
    heat_load_consumer["mfh" + "_" + carrier] = bdew.HeatBuilding(
        heat_load_consumer.index,
        holidays=holidays,
        temperature=temperature,
        shlp_type="MFH",
        building_class=2,
        wind_class=0,
        annual_heat_demand=yearly_demands["mfh" + "_" + carrier][0],
        name="MFH",
        ww_incl=True,
    ).get_bdew_profile()

    # Calculate industry, trade, service (ghd: Gewerbe, Handel, Dienstleistung)
    # heat load
    heat_load_consumer["ghd" + "_" + carrier] = bdew.HeatBuilding(
        heat_load_consumer.index,
        holidays=holidays,
        temperature=temperature,
        shlp_type="ghd",
        wind_class=0,
        annual_heat_demand=yearly_demands["ghd" + "_" + carrier][0],
        name="ghd",
        ww_incl=True,
    ).get_bdew_profile()

    # Calculate total heat load in year
    heat_load_total[carrier + "-load-profile"] = heat_load_consumer.sum(axis=1)

    # Normalize heat load profile
    heat_load_total[carrier + "-load-profile"] = np.divide(
        heat_load_total[carrier + "-load-profile"],
        heat_load_total[carrier + "-load-profile"].sum(),
    )

    return heat_load_total


def postprocess_data(heat_load_postprocessed, heat_load_year, region, scenario, unit):
    """
    This function stacks time series of heat load profile and addes it to result DataFrame

    Parameters
    ----------
    heat_load_postprocessed : pd.Dataframe
        Empty Dataframe as result DataFrame
    heat_load_year : pd.Dataframe
        DataFrame with total normalized heat load in year to be processed
    region : str
        Region (eg. Brandenburg)
    scenario : str
        Scenario e.g. "base
    unit : str
        Unit of total demands (eg. GWh)

    Returns
    -------
    heat_load_postprocessed : pd.DataFrame
         DataFrame that contains stacked heat load profile

    """
    # Stack time series with total heat load in year
    heat_load_year_stacked = dp.stack_timeseries(heat_load_year)

    heat_load_year_stacked["region"] = region
    heat_load_year_stacked["scenario"] = scenario
    heat_load_year_stacked["var_unit"] = unit[0]

    # Append stacked heat load of year to stacked time series with total heat loads
    heat_load_postprocessed = pd.concat(
        [heat_load_postprocessed, heat_load_year_stacked], ignore_index=True
    )

    return heat_load_postprocessed


if __name__ == "__main__":
    in_path1 = sys.argv[1]  # path to weather data
    in_path2 = sys.argv[2]  # path to household distributions data
    in_path3 = sys.argv[3]  # path to holidays
    in_path4 = sys.argv[4]  # path to b3 scalars.csv
    out_path = sys.argv[5]

    REGION = ["BB", "BE"]
    SCENARIO = "base"
    CARRIERS = ["heat_central", "heat_decentral"]

    # Add empty data frame for results / output
    total_heat_load = pd.DataFrame(columns=dp.HEADER_B3_TS)

    for region in REGION:
        weather_file_names = find_regional_files(in_path1, region)

        for weather_file_name, carrier in itertools.product(
            weather_file_names, CARRIERS
        ):
            # Read year from weather file name
            year = get_year(weather_file_name)

            # Get holidays
            holidays = get_holidays(in_path3, year, region)

            # Read temperature from weather data
            path_weather_data = os.path.join(in_path1, weather_file_name)
            temperature = pd.read_csv(path_weather_data, usecols=["temp_air"], header=0)

            # Get heat demand in region and scenario
            yearly_demands, sc_demand_unit = get_heat_demand(
                in_path4, SCENARIO, carrier, region
            )

            heat_load_year = calculate_heat_load(
                carrier, holidays, temperature, yearly_demands
            )
            total_heat_load = postprocess_data(
                total_heat_load, heat_load_year, region, SCENARIO, sc_demand_unit
            )

    # Rearrange stacked time series
    head_load = dp.format_header(
        df=total_heat_load,
        header=dp.HEADER_B3_TS,
        index_name="id_ts",
    )
    dp.save_df(head_load, out_path)
