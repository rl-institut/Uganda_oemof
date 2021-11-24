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
import os
import sys

import numpy as np
import pandas as pd
from demandlib import bdew

import oemof_b3.tools.data_processing as dp


def find_regional_weather_data(path, region):
    """
    This function returns a list with weather data to region

    Parameters
    ----------
    path : str
        Path to all weather data

    region : str
        Region (eg. Brandenburg)

    Returns
    -------
    weather_data_region : list
        List of weather data file names of region
    """
    weather_data_region = [file for file in os.listdir(path) if region in file]
    weather_data_region = sorted(weather_data_region)

    if not weather_data_region:
        raise FileNotFoundError(
            f"No weather data of region {region} could be found in directory: {path}."
        )

    return weather_data_region


def get_years(file_list):
    """
    This function returns years from available weather data

    Parameters
    ----------
    file_list : list
        List of file names with year

    Returns
    -------
    years_list : list
        List of years
    """
    years_array = np.arange(1990, 2051)
    years_list = []
    newline = "\n"

    for file in file_list:
        year_in_file = [
            year_array for year_array in years_array if str(year_array) in file
        ]
        if len(year_in_file) == 1:
            years_list.append(year_in_file[0])
        else:
            raise ValueError(
                f"Your file {file} is missing a year or has multiple years "
                f"in its name."
                + newline
                + "Please provide weather data for a single year "
                  "with that year in the file name."
            )

    years_list = sorted(years_list)
    return years_list


def get_holidays(path, year):
    """
    This function determines all holidays of a given region in a given year

    Parameters
    ----------
    path : str
        input path
    year : int
        year
    Returns
    -------
    holidays_dict : dict
        dictionary with holidays

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
    to demands DataFrame to value if it exists and otherwise to a new column

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


def get_heat_demand(path, scenario, carrier):
    """
    This function returns ghd and hh demands together with their unit of a given region and a
    given scenario

    Parameters
    ----------
    path : str
        input path
    scenario : str
        scenario e.g. "base"
    carrier : str
         Name of carrier (eg.: heat_central, heat_decentral)

    Returns
    -------
    demand : DataFrame
        Dataframe with total yearly demand of central and decentral heat per consumer
        (eg.: ghd, efh, mfh)
    demand_unit : str
        unit of total demands

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
                + f"The demand is going to be summed up. "
                "Otherwise you have to rerun the calculation and provide only one demand of the "
                "same carrier, consumer, region and scenario."
            )

        for demand_value in sc_filtered_consumer["var_value"].values:
            check_central_decentral(demands, demand_value, consumer, carrier)

    return demands, demand_unit


def calculate_heat_load():
    """
    This function calculates a heat load profile of Industry, trade,
    service (ghd: Gewerbe, Handel, Dienstleistung) and Household (hh: Haushalt)
    sectors

    Parameters
    ----------

    Returns
    -------
    heat_load_total : pd.DataFrame
         DataFrame with total yearly heat load aggretated by consumers
         (eg.: ghd, efh, mfh)

    """

    # Calculate sfh (efh: Einfamilienhaus) heat load
    demand["efh" + "_" + carrier] = bdew.HeatBuilding(
        demand.index,
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
    demand["mfh" + "_" + carrier] = bdew.HeatBuilding(
        demand.index,
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
    demand["ghd" + "_" + carrier] = bdew.HeatBuilding(
        demand.index,
        holidays=holidays,
        temperature=temperature,
        shlp_type="ghd",
        wind_class=0,
        annual_heat_demand=yearly_demands["ghd" + "_" + carrier][0],
        name="ghd",
        ww_incl=True,
    ).get_bdew_profile()

    # Calculate total heat load in year
    heat_load_year[carrier + "-load-profile"] = demand.sum(axis=1)
    # TODO: Normalize heat load profile

    return heat_load_year


def postprocess_data(heat_load):
    """
    This function stacks time series of heat load profile and addes it to result DataFrame

    Parameters
    ----------
    heat_load : pd.Dataframe
        Empty Dataframe as result DataFrame

    Returns
    -------
    heat_load : pd.DataFrame
         DataFrame that contains the stacked heat load profile

    """
    # Stack time series with total heat load in year
    heat_load_year_stacked = dp.stack_timeseries(heat_load_year)

    heat_load_year_stacked["region"] = region
    heat_load_year_stacked["scenario"] = SCENARIO
    heat_load_year_stacked["var_unit"] = sc_demand_unit

    # Append stacked heat load of year to stacked time series with total heat loads
    heat_load = pd.concat([heat_load, heat_load_year_stacked], ignore_index=True)

    return heat_load


if __name__ == "__main__":
    # path_this_file = os.path.realpath(__file__)
    # raw_data = os.path.abspath(
    #     os.path.join(path_this_file, os.pardir, os.pardir, "raw")
    # )
    # schema = os.path.abspath(
    #     os.path.join(path_this_file, os.pardir, os.pardir, "oemof_b3", "schema")
    # )
    # results = os.path.abspath(
    #     os.path.join(path_this_file, os.pardir, os.pardir, "results", "_resources")
    # )
    #
    # in_path1 = os.path.join(raw_data, "weatherdata")  # path to weather data
    # in_path2 = os.path.join(
    #     raw_data, "distribution_households.csv"
    # )  # path to household distributions data
    # in_path3 = os.path.join(raw_data, "holidays.csv")  # path to holidays
    # in_path4 = os.path.join(raw_data, "scalars.csv")  # path to b3 schema scalars.csv
    # out_path = os.path.join(results, "load_profile_heat.csv")

    in_path1 = sys.argv[1]  # path to weather data
    in_path2 = sys.argv[2]  # path to household distributions data
    in_path3 = sys.argv[3]  # path to holidays
    in_path4 = sys.argv[4]  # path to b3 scalars.csv
    out_path = sys.argv[5]

    REGION = ["BB", "BE"]
    SCENARIO = "base"
    CARRIERS = ["heat_central", "heat_decentral"]

    # Add empty data frame for results / output
    heat_load = pd.DataFrame(columns=dp.HEADER_B3_TS)

    for region in REGION:

        weather_data = find_regional_weather_data(in_path1, region)
        years = get_years(weather_data)

        for index, year in enumerate(years):
            # Get holidays
            holidays = get_holidays(in_path3, year)

            # Read temperature from weather data
            path_weather_data = os.path.join(in_path1, weather_data[index])
            temperature = pd.read_csv(path_weather_data, usecols=["temp_air"], header=0)

            # Add DataFrame time index for demands
            demand = pd.DataFrame(
                index=pd.date_range(
                    datetime.datetime(year, 1, 1, 0), periods=len(temperature), freq="H"
                )
            )

            heat_load_year = pd.DataFrame()
            for carrier in CARRIERS:
                # Get heat demand in region and scenario
                yearly_demands, sc_demand_unit = get_heat_demand(
                    in_path4, SCENARIO, carrier
                )

                heat_load_year = calculate_heat_load()

            heat_load = postprocess_data(heat_load)

    # Rearrange stacked time series
    heat_load["id_ts"] = heat_load.index
    head_load = dp.format_header(
        df=heat_load,
        header=heat_load.columns,
        index_name="id_ts",
    )
    dp.save_df(heat_load, out_path)
