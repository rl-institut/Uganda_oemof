import sys

from oemof.solph import EnergySystem
from oemoflex.model.datapackage import ResultsDataPackage


if __name__ == "__main__":

    optimized = sys.argv[1]

    scenario_name = sys.argv[2]

    destination = sys.argv[3]

    es = EnergySystem()

    es.restore(optimized)

    rdp = ResultsDataPackage.from_energysytem(es)

    rdp.set_scenario_name(scenario_name)

    rdp.to_csv_dir(destination)