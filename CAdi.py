from src.model import FacilityLocationOptimizer
from src import save

def RunScenarios():
	# S1.A
	config_path = 'config/S1A_max_gasoline.ini'
	s = FacilityLocationOptimizer(scenario='GASOLINE', config_path=config_path)
	s.predict();
	save.supply_network(s)

	# S1.B
	config_path = 'config/S1B_max_diesel.ini'
	s = FacilityLocationOptimizer(scenario='DIESEL', config_path=config_path)
	s.predict();
	save.supply_network(s)

	# S2
	config_path = 'config/S2_max_fuel.ini'
	s = FacilityLocationOptimizer(scenario='FUEL', config_path=config_path)
	s.predict();
	save.supply_network(s)

	# S3
	config_path = 'config/S3_centralized_new_construction.ini'
	s = FacilityLocationOptimizer(config_path=config_path)
	s.predict();
	save.supply_network(s)

	# S4
	config_path = 'config/S4_centralized_co_locate.ini'
	s = FacilityLocationOptimizer(config_path=config_path)
	s.predict();
	save.supply_network(s)

	# S5
	config_path = 'config/S5_distributed_ca.ini'
	s = FacilityLocationOptimizer(config_path=config_path)
	s.predict();
	save.supply_network(s)

	# S6
	config_path = 'config/S6_even_distribution.ini'
	s = FacilityLocationOptimizer(config_path=config_path)
	s.predict();
	save.supply_network(s)
	

RunScenarios()



