import os
from sqlalchemy import create_engine
import pandas as pd, json
from ConfigParser import ConfigParser


class CreateConfigScenario:
	def __init__(s,scenario,quick_build=False, config_path='config/', config_template='Test/config_template.ini', emissions='GHG'):
		# Record pollutant
		s.emissions = emissions

		# Set up the blank configuration file
		s.create_config(scenario+".ini", config_path, config_template);

		# Create new file directory for scenario data
		s.scenario_path_setup(scenario)

		# Start the server 
		s.start_server()

		# If true, set up the baseline scenario
		if quick_build: s.build_baseline() 

	def create_config(s, config_file, config_path, config_template):
		s.config_path = config_path+config_file;
		config = ConfigParser()
		config.read(config_template);
		s.config = config

	def scenario_path_setup(s, scenario):
		s.scenario = scenario;
		if '../' in s.config_path:
			s.scenario_path = '../scenarios/%s' % (scenario);
		else:
			s.scenario_path = 'scenarios/%s' % (scenario);
		if not os.path.exists(s.scenario_path+'/input'): os.makedirs(s.scenario_path+'/input')
		if not os.path.exists(s.scenario_path+'/extra'): os.makedirs(s.scenario_path+'/extra')
		if not os.path.exists(s.scenario_path+'/results'): os.makedirs(s.scenario_path+'/results')
		
		s.config.set('Paths', 'results_path', s.scenario_path.replace('../', '')+'/results/');
		s.config.set('Paths', 'extra_path', s.scenario_path.replace('../', '')+'/extra/');
		s.config.set('Extra', 'emissions', s.emissions);
		s.config.set('Extra', 'scenario', scenario);


	def start_server(s):
		s.database = s.config.get('DB', 'database');
		s.username = s.config.get('DB', 'username');
		s.host = s.config.get('DB', 'host');

		s.cur  = create_engine('postgresql://%s@%s:5432/%s' % (s.username, s.host, s.database))

	def biomass_availability(s, SQLcommand=None):
		if not SQLcommand: SQLcommand = 'SELECT fips AS origin, cropres, forestres, urbanwood + primmill + secmill AS scrapwood FROM solid_biomass_carb_study';

		# Set paths 
		cpath = '%s/input/%s_biomass_availability.csv' % (s.scenario_path, s.scenario)
		aidpath_o = '%s/extra/%s_biomass_availability_origin.csv' % (s.scenario_path, s.scenario)

		# Get Data from server
		df = pd.read_sql_query(SQLcommand, s.cur)
		df.columns = ['origin', 'cropres', 'forestres', 'scrapwood']
		df.sort(['origin'], inplace=True)
		
		# Set origin as the index
		df = df.set_index(['origin']);
		df = df.fillna(0)
		
		# Export the matrix to file
		df.to_csv(cpath, index=False, header=False)
		
		#Save the row and column names
		pd.DataFrame(df.index).to_csv(aidpath_o, index=False)

		# Set config path
		s.config.set('Paths', 'availability_data', cpath.replace('../', ''))
		s.config.set('Extra', 'biomass_availability_origin_path', aidpath_o.replace('../', ''));

	def facility_construction(s, SQLcommand=None, emissions='GHG'):
		if not SQLcommand: SQLcommand = "SELECT id AS facility, CASE WHEN type='drop-in' THEN CAST(1 AS double precision) ELSE CAST(0 AS double precision) END AS facility_construction FROM facility_locations_about_cities";
		# Set paths 
		cpath = '%s/input/%s_facility_construction_%s.csv' % (s.scenario_path, s.scenario, emissions)
		aidpath_d = '%s/extra/%s_facility_construction_emissions_destination.csv' % (s.scenario_path, s.scenario)

		# Get Data from server
		df = pd.read_sql_query(SQLcommand, s.cur)
		df.columns = ['facility', 'facility_construction']
		df.sort(['facility'], inplace=True)
		
		# Set origin as the index
		df = df.set_index(['facility']);
		df = df.fillna(1)
		
		# Export the matrix to file
		df.to_csv(cpath, index=False, header=False)
		
		#Save the row and column names
		pd.DataFrame(df.index).to_csv(aidpath_d, index=False)

		# Set config path
		s.config.set('Paths', 'capital', cpath.replace('../', ''))
		s.config.set('Extra', 'facility_construction_destination_path', aidpath_d.replace('../', ''));

	def upstream_transport(s, SQLcommand=None, emissions='GHG'):
		if not SQLcommand: 
			SQLcommand = """ SELECT a.origin, a.destination, a.km_road AS herb_road, a.km_rail as herb_rail, b.km_road as wood_road, b.km_rail as wood_rail
			FROM cij_CA_feedstocks_intermodal_crop a
			LEFT JOIN cij_CA_feedstocks_intermodal_forest b
			ON a.origin = b.origin AND a.destination = b.destination;""" 

		# Set paths 
		cpath = '%s/input/%s_cij_%s.csv' % (s.scenario_path, s.scenario, emissions)
		aidpath_km = '%s/extra/%s_cij_km.csv' % (s.scenario_path, s.scenario)
		aidpath_o = '%s/extra/%s_cij_origin.csv' % (s.scenario_path, s.scenario)
		aidpath_d = '%s/extra/%s_cij_destination.csv' % (s.scenario_path, s.scenario)

		# Get Data from server
		df = pd.read_sql_query(SQLcommand, s.cur);
		ef = json.load(open('base/transport_emission_factors.json'));

		# Save kilometers
		df.to_csv(aidpath_km, index=False)

		# Estimate Emissions
		for e in ef['road'].keys():
			temp = df
			e_path = '%s/%s/%s_cij_%s.csv' % (s.scenario_path, 'extra', s.scenario, e)
			temp['cropres'] = temp['herb_road'] * ef['road'][e] +  temp['herb_rail'] * ef['rail'][e];
			temp['forestres'] = temp['wood_road'] * ef['road'][e] +  temp['wood_rail'] * ef['rail'][e];
			temp['scrapwood'] = temp['wood_road'] * ef['road'][e] +  temp['wood_rail'] * ef['rail'][e];


			# Reshape
			temp = temp[['origin', 'destination', 'cropres', 'forestres', "scrapwood"]]
			
			# Transform Data 
			"""
				up_l_data = | {c111, c121,...,c1npathways1}, {c211, c221,...,c2npathways1}, ... |
							| {c122, c122,...,c1npathways2}, {c212, c222,...,c2npathways2}, ... |
							|             ...,             ,             ...              , ... |

			"""
			temp.set_index(['origin', 'destination'], inplace=True)
			temp =  temp.stack().reset_index()

			temp.columns = ['origin', 'destination', 'feedstock', 'kg_ghg_per_ton']
			temp.sort(['origin', 'destination'], inplace=True)
			
			# Create a matrix where biomass location-feedtock are columns and refineries are rows
			temp = pd.pivot_table(temp,values='kg_ghg_per_ton',index='destination',columns=['origin', 'feedstock']);
			temp = temp.fillna(1e6)
			# Export the matrix to file
			temp.to_csv(e_path, index=False, header=False)
			if e == emissions:
				temp.to_csv('%s/input/%s_cij_%s.csv' % (s.scenario_path, s.scenario, emissions), index=False, header=False)
		
		#Save the row and column names
		pd.DataFrame(temp.columns).to_csv(aidpath_o, index=False)
		pd.DataFrame(temp.index).to_csv(aidpath_d, index=False)

		# Set config path
		s.config.set('Paths', 'upstream_logistics', cpath.replace('../', ''))
		s.config.set('Extra', 'upstream_transport_origin_path', aidpath_o.replace('../', ''))
		s.config.set('Extra', 'upstream_transport_destination_path', aidpath_d.replace('../', ''));
		s.config.set('Extra', 'upstream_transport_kilometers_path', aidpath_km.replace('../', ''));

	def handling(s, emissions='GHG'):
		# Set paths 
		cpath = '%s/input/%s_handling_%s.csv' % (s.scenario_path, s.scenario, emissions)

		# Get Data from local files
		df = pd.read_csv('base/handling_%s_emissions.csv' % emissions, header=None)

		# Export the matrix to file
		df.to_csv(cpath, index=False, header=False)
		
		# Set config path
		s.config.set('Paths', 'handling', cpath.replace('../', ''))

	def fuel_production(s, emissions='GHG'):
		# Set paths 
		cpath = '%s/input/%s_fuel_production_%s.csv' % (s.scenario_path, s.scenario, emissions)

		# Get Data from local files
		df = pd.read_csv('base/fuel_production_%s_emissions.csv' % emissions, header=None)

		# Export the matrix to file
		df.to_csv(cpath, index=False, header=False)
		
		# Set config path
		s.config.set('Paths', 'fuel_production', cpath.replace('../', ''))

	def biomass_conversion_to_fuel(s):
		# Set paths 
		cpath = '%s/input/%s_conversion_efficieny.csv' % (s.scenario_path, s.scenario)

		# Get Data from local files
		df = pd.read_csv('base/conversion_efficieny.csv', header=None)

		# Export the matrix to file
		df.to_csv(cpath, index=False, header=False)
		
		# Set config path
		s.config.set('Paths', 'conversion_efficieny', cpath.replace('../', ''))

	def conventional_emission_factor(s, emissions="GHG"):
		# Set paths 
		cpath = '%s/input/%s_conventional_%s_emission_factor.csv' % (s.scenario_path, s.scenario, emissions)

		# Get Data from local files
		df = pd.read_csv('base/conventional_%s_emission_factor.csv' % emissions, header=None)

		# Export the matrix to file
		df.to_csv(cpath, index=False, header=False)
		
		# Set config path
		s.config.set('Paths', 'conventional_emission_factor', cpath.replace('../', ''))

	def energy_demand(s, SQLcommand=None):
		## Note: Diesel demand is based on onroad vehicles, not total demand. 
		if not SQLcommand: SQLcommand='SELECT id AS destination, CAST(million_gals_gasoline_2012*1000000*(6.0/2209.0) AS integer) AS mt_gas_demand, CAST(million_gals_diesel_2012*1000000*(7.5/2209.0) AS integer) AS mt_diesel_demand FROM downstream_locations_california'

		# Set paths 
		cpath = '%s/input/%s_energy_demand.csv' % (s.scenario_path, s.scenario)
		aidpath_d = '%s/extra/%s_energy_demand_destination.csv' % (s.scenario_path, s.scenario)

		# Get Data from server
		df = pd.read_sql_query(SQLcommand, s.cur)
		df.sort(['destination'], inplace=True)
		
		# Set origin as the index
		df = df.set_index(['destination']);
		df = df.fillna(0)
		
		# Export the matrix to file
		df.to_csv(cpath, index=False, header=False)
		
		#Save the row and column names
		pd.DataFrame(df.index).to_csv(aidpath_d, index=False)

		# Set config path
		s.config.set('Paths', 'demand_data', cpath.replace('../', ''))
		s.config.set('Extra', 'energy_demand_destination_path', aidpath_d.replace('../', ''))

	def downstream_transport(s, SQLcommand=None, emissions='GHG'):

		if not SQLcommand: 
			SQLcommand ='SELECT origin, destination, km, km_road, km_rail, km_pipe FROM sjk_CA_feedstocks_intermodal_pipeline'

		# Set paths 
		cpath = '%s/input/%s_sjk_%s.csv' % (s.scenario_path, s.scenario, emissions)
		aidpath_km = '%s/extra/%s_sjk_km.csv' % (s.scenario_path, s.scenario)
		aidpath_o = '%s/extra/%s_sjk_origin.csv' % (s.scenario_path, s.scenario)
		aidpath_d = '%s/extra/%s_sjk_destination.csv' % (s.scenario_path, s.scenario)

		# Get Data from server
		df = pd.read_sql_query(SQLcommand, s.cur)
		ef = json.load(open('base/transport_emission_factors.json'));

		# Save kilometers
		df.to_csv(aidpath_km, index=False)

		# Estimate Emissions
		for e in ef['road'].keys():

			temp = df
			e_path = '%s/%s/%s_sjk_%s.csv' % (s.scenario_path, 'extra', s.scenario, e)


			temp['emissions'] = temp['km_road'] * ef['road'][e]  +  temp['km_rail'] * ef['rail'][e]  + (temp['km'] - temp['km_rail'] - temp['km_road'] ) * ef['pipe'][e];

			# Reshape and sort
			temp = temp[['origin', 'destination', 'emissions']]
			temp.sort(['origin', 'destination'], inplace=True)
			
			# Create a matrix where biomass locations are columns and refineries are rows
			temp = pd.pivot_table(temp,values='emissions',index='origin',columns='destination');
			temp = temp.fillna(1e6)
			
			# Export the matrix to file
			temp.to_csv(e_path, index=False, header=False)

			if e == emissions:
				temp.to_csv('%s/input/%s_sjk_%s.csv' % (s.scenario_path, s.scenario, emissions), index=False, header=False)
		
		#Save the row and column names
		pd.DataFrame(temp.columns).to_csv(aidpath_d, index=False)
		pd.DataFrame(temp.index).to_csv(aidpath_o, index=False)

		# Set config path
		s.config.set('Paths', 'downstream_logistics', cpath.replace('../', ''))
		s.config.set('Extra', 'downstream_transport_origin_path', aidpath_o.replace('../', ''))
		s.config.set('Extra', 'downstream_transport_destination_path', aidpath_d.replace('../', ''))
		s.config.set('Extra', 'downstream_transport_kilometers_path', aidpath_km.replace('../', ''));


	def build_baseline(s):
		s.biomass_availability()
		s.facility_construction()
		s.upstream_transport()
		s.handling()
		s.fuel_production()
		s.biomass_conversion_to_fuel()
		s.conventional_emission_factor()
		s.energy_demand()
		s.downstream_transport()

	def build_new_facility_only(s):
		s.biomass_availability();

		SQLcommand = "SELECT id AS facility, CASE WHEN type='drop-in' THEN CAST(1 AS double precision) ELSE CAST(0 AS double precision) END AS facility_construction FROM facility_locations_about_cities WHERE type='drop-in'";
		s.facility_construction(SQLcommand=SQLcommand)
		
		SQLcommand = """ SELECT a.origin, a.destination, a.km_road AS herb_road, a.km_rail as herb_rail, b.km_road as wood_road, b.km_rail as wood_rail
		FROM cij_CA_feedstocks_intermodal_crop a
		LEFT JOIN cij_CA_feedstocks_intermodal_forest b
		ON a.origin = b.origin AND a.destination = b.destination
		LEFT JOIN facility_locations_about_cities c
		ON a.destination = c.id and b.destination = c.id
		WHERE c.type = 'drop-in';""" 
		s.upstream_transport(SQLcommand=SQLcommand)

		s.handling()
		s.fuel_production()
		s.biomass_conversion_to_fuel()
		s.conventional_emission_factor()
		s.energy_demand()

		SQLcommand ="SELECT a.origin, a.destination,a.km,  a.km_road, a.km_rail, a.km_pipe FROM sjk_CA_feedstocks_intermodal_pipeline a LEFT JOIN facility_locations_about_cities b ON a.origin = b.id WHERE b.type='drop-in'"
		s.downstream_transport(SQLcommand=SQLcommand);


	def build_co_locate_refinery(s):
		s.biomass_availability();

		SQLcommand = "SELECT id AS facility, CASE WHEN type='drop-in' THEN CAST(0 AS double precision) ELSE CAST(0 AS double precision) END AS facility_construction FROM facility_locations_about_cities WHERE type<>'drop-in'";
		s.facility_construction(SQLcommand=SQLcommand)
		
		SQLcommand = """ SELECT a.origin, a.destination, a.km_road AS herb_road, a.km_rail as herb_rail, b.km_road as wood_road, b.km_rail as wood_rail
		FROM cij_CA_feedstocks_intermodal_crop a
		LEFT JOIN cij_CA_feedstocks_intermodal_forest b
		ON a.origin = b.origin AND a.destination = b.destination
		LEFT JOIN facility_locations_about_cities c
		ON a.destination = c.id and b.destination = c.id
		WHERE c.type <> 'drop-in';""" 
		s.upstream_transport(SQLcommand=SQLcommand)

		s.handling()
		s.fuel_production()
		s.biomass_conversion_to_fuel()
		s.conventional_emission_factor()
		s.energy_demand()

		SQLcommand ="SELECT a.origin, a.destination, a.km, a.km_road, a.km_rail, a.km_pipe FROM sjk_CA_feedstocks_intermodal_pipeline a LEFT JOIN facility_locations_about_cities b ON a.origin = b.id WHERE b.type<>'drop-in'"
		s.downstream_transport(SQLcommand=SQLcommand);


	def save(s):
		with open(s.config_path, 'w') as configfile:
			s.config.write(configfile)



if __name__ == "__main__":
	
	c = CreateConfigScenario('S1_A_max_gasoline', quick_build=True, config_path='../config/', config_template='config_template.ini');
	c.save()

	c = CreateConfigScenario('S1_B_max_diesel', quick_build=True, config_path='../config/', config_template='config_template.ini');
	c.save()

	c = CreateConfigScenario('S2_max_fuel', quick_build=True, config_path='../config/', config_template='config_template.ini');
	c.save()

	c = CreateConfigScenario('S3_centralized_new_construction', quick_build=False, config_path='../config/', config_template='config_template.ini');
	c.build_new_facility_only()
	c.save()

	c = CreateConfigScenario('S4_centralized_co_locate', quick_build=False, config_path='../config/', config_template='config_template.ini');
	c.build_co_locate_refinery()
	c.save()

	c = CreateConfigScenario('S5_distributed_ca', quick_build=True, config_path='../config/', config_template='config_template.ini');
	c.save()
	

	c = CreateConfigScenario('S6_even_distribution', quick_build=True, config_path='../config/', config_template='config_template.ini')
	SQLcommand='SELECT id AS destination, CAST(million_gals_gasoline_2012*1000000*(6.0/2209.0)*0.086 AS integer) AS mt_gas_demand, CAST(million_gals_diesel_2012*1000000*(7.5/2209.0) AS integer)*20.4 AS mt_diesel_demand FROM downstream_locations_california';
	c.energy_demand(SQLcommand=SQLcommand)
	c.save()



