from src.model import FacilityLocationOptimizer
from src import save
import pandas as pd, numpy as np
def TargetSpectrum(config_path):
	# Initialize model
	s = FacilityLocationOptimizer(config_path=config_path)
	
	# Initialize the saving controller
	fig = save.MeetTheTarget(config_path=config_path)

	# Loop through targets
	for target in range(50, 201,50):
		s.predict(method='Relax', target=(target/1000.0))
		fig.update(s);

	# Save the results to excel file
	fig.save()

def RunScenarios():
	# S1
	config_path = 'config/S1_max_gasoline.ini'
	s = FacilityLocationOptimizer(scenario='GASOLINE', config_path=config_path)
	s.predict();
	save.supply_network(s)
	#TargetSpectrum(config_path)

	# S2
	config_path = 'config/S2_max_diesel.ini'
	s = FacilityLocationOptimizer(scenario='DIESEL', config_path=config_path)
	s.predict();
	save.supply_network(s)
	#TargetSpectrum(config_path)

	# S3
	config_path = 'config/S3_centralized_new_construction.ini'
	s = FacilityLocationOptimizer(config_path=config_path)
	s.predict();
	save.supply_network(s)
	#TargetSpectrum(config_path)

	# S4
	config_path = 'config/S4_centralized_co_locate.ini'
	s = FacilityLocationOptimizer(config_path=config_path)
	s.predict();
	save.supply_network(s)
	#TargetSpectrum(config_path)

	# S5
	config_path = 'config/S5_distributed_ca.ini'
	s = FacilityLocationOptimizer(config_path=config_path)
	s.predict();
	save.supply_network(s)
	#TargetSpectrum(config_path)

	# S6

	config_path = 'config/S6_even_distribution.ini'
	s = FacilityLocationOptimizer(config_path=config_path)
	s.predict();
	save.supply_network(s)
	#TargetSpectrum(config_path)
	

RunScenarios()

"""
config_path = 'config/S5_distributed_ca.ini'
s = FacilityLocationOptimizer(config_path=config_path)
s.predict();
save.store_at_mid(s);
save.store_at_down(s);
save.state_summary(s)
save.supply_network(s)
"""




