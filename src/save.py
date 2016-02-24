from ConfigParser import ConfigParser
import pandas as pd, numpy as np, json, re
from wrangle import Z, up_freight, flare, is_gasoline, is_diesel, in_county_supplies
from upload import Methods
import utils.matrix_ops as mp

def supply_network(s):
	server = Methods(); #Launches server instance with appropriate configurations.

	# In some modeling cases, the dimensions of the G matrix would have changed (e.g., columns deleted).
	# If this is the case, remap the solution to the original dimensions.
	if s.trimmed_cols: 
		sset = np.zeros(s.var['x'] + s.var['y'] + s.var['w'] + s.var['v'] )
		np.put(sset, s.trimmed_cols, s.solution['set'])
		s.solution['set'] = sset


	# Break the solution based on the decision variable sets.
	[y, x, w, v] = np.split(s.solution['set'], s.blade)



	"""

	Section 1: Summarize the activities from feedstock collection to refinery gate.


	"""

	# Load relevant data and methods
	refineries = np.genfromtxt(s.config.get('Extra', 'downstream_transport_origin_path'), skip_header=1)
	counties  = pd.read_csv(s.config.get('Extra', 'upstream_transport_origin_path'));
	counties.columns = ['county']
	counties['county'] = counties['county'].map(lambda x: tuple(int(v) for v in re.findall("[0-9]+", x))[0]); #strip county FIPS from county-feedstocks labels
	counties = counties['county'].unique()


	# Reshape the upstream logistics cost (Cx) based on county, refinery, and pathway.
	df = pd.DataFrame(np.split(x, s.n_up * s.n_mid * s.n_pathways), columns=['cropres','forestres', 'scrapwood'])
	pathways = ['pg','m2g','pd','ft'];

	# Create appropriate labels based on index number.
	df['pathway'] = df.index.map(lambda x: pathways[x % s.n_pathways]);
	df['county'] = df.index.map(lambda x: counties[x // s.n_pathways % s.n_up]);
	df['refinery'] = df.index.map(lambda x: refineries[x // (s.n_up*s.n_pathways)]);


	# Import data to calculate the amount of fuel produced via each county-refinery pair. 
	# This next step was taken from model.py (see, FacilityLocationOptimizer.conversion_builder())
	gx = np.tile(s.cnv_block, (1, s.n_up));
	gx = mp.bd(gx, s.n_mid);
	gx = np.sum(gx, axis=0)
	#Reshape the conversion efficiency constraints to match Cx dimensions and provide appropriate labels. 
	eff = pd.DataFrame(np.split(gx, s.n_up * s.n_mid * s.n_pathways), columns=['cropres_eff','forestres_eff', 'scrapwood_eff'])
	eff['pathway'] = eff.index.map(lambda x: pathways[x % s.n_pathways])
	eff['county'] = eff.index.map(lambda x: counties[x // s.n_pathways % s.n_up])
	eff['refinery'] = eff.index.map(lambda x: refineries[x // (s.n_up*s.n_pathways)])
	

	# Merge the the Cx and conversion efficiency dataframes. 
	df = pd.merge(df, eff, on=['county','refinery', 'pathway'], how='left');


	# Given the pathways and feedstocks, calculate the amount of fuel produced for each county-refinery-pathway combination.
	df['mt_gas_at_refinery'] = df.apply(lambda row: is_gasoline(row), axis=1);
	df['mt_diesel_at_refinery'] = df.apply(lambda row: is_diesel(row), axis=1);

	# Drop the efficiency columns
	#df = df[['county', 'refinery', 'pathway', 'cropres','forestres', 'scrapwood', 'mt_gas_at_refinery', 'mt_diesel_at_refinery']]
	df.set_index(['county', 'refinery', 'pathway'], inplace=True)


	# Group the dataset by county-refinery pairs and sum feedstocks and fuels produced. 
	county_refinery_stats = df.groupby(level=['county', 'refinery'])[['cropres','forestres', 'scrapwood', 'mt_gas_at_refinery', 'mt_diesel_at_refinery']].sum() 
	# Drop empty pathways
	county_refinery_stats = county_refinery_stats.loc[~(county_refinery_stats==0).all(axis=1)]
	county_refinery_stats = county_refinery_stats.reset_index()


	# Create a new dataframe that shows the splits in feedstock usage based on pathway for each county-refinery pair
	pathway_feedstock_df = df[['cropres','forestres', 'scrapwood']].sum(axis=1).reset_index();
	pathway_feedstock_df.columns = ['county', 'refinery', 'pathway', 'feedstock_mt']
	# Reshape the dataframe using the pivot tab;e
	pathway_feedstock_df = pd.pivot_table(pathway_feedstock_df, index=['county', 'refinery'], columns='pathway', values='feedstock_mt')
	# Fill NaN with zero and drop empty pathways
	pathway_feedstock_df.fillna(0,inplace=True)
	pathway_feedstock_df = pathway_feedstock_df.loc[~(pathway_feedstock_df==0).all(axis=1)]
	pathway_feedstock_df = pathway_feedstock_df.reset_index()
	pathway_feedstock_df = pathway_feedstock_df[['county','refinery','ft','m2g','pd','pg']]



	# Join the two produced dataframes to create a master dataframe from county to the gate of the refinery.
	df_upstream = df[(df.cropres > 0) | (df.forestres > 0) | df.scrapwood > 0];
	df_upstream.columns = ['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)', 'Cropres Conv. Eff.', 'Forestres Conv. Eff.', 'Scrapwood Conv. Eff.','Gasoline (mt/yr)','Diesel (mt/year)']
	df_refine_gate = pd.merge(county_refinery_stats, pathway_feedstock_df, on=['county', 'refinery'], how='left')


	# Export master to csv
	df_refine_gate.to_csv(s.config.get('Paths', 'results_path')+'statistics_from_county_to_refinery_gate.csv', index=False);


	# Get the total amount of fuel produced at each refinery. 
	df_refinery_production = df_refine_gate.groupby('refinery')[['mt_gas_at_refinery','mt_diesel_at_refinery']].sum().reset_index();
	df_refinery_counties = df_refine_gate.groupby('refinery')[['county']].count().reset_index();
	df_refinery_stats = pd.merge(df_refinery_production, df_refinery_counties, on='refinery', how='left');


	assert (True == True) # A note that the df_refine_gate is correct.



	"""

	Section 2: Summarize the activities from refinery gate to terminal storage.


	"""

	# Reshape the optimal downstream decisions (W) from the solution set.
	df = pd.DataFrame(np.split(w, s.n_mid * s.n_down), columns=['gas','diesel'])
	refineries = np.genfromtxt(s.config.get('Extra', 'downstream_transport_origin_path'), skip_header=1)

	# Label appropriate indices
	df['terminal'] = df.index.map(lambda x: x % (s.n_down) + 1)
	df['refinery'] = df.index.map(lambda x: refineries[x // (s.n_down)])
	df = df[(df.gas > 0) | (df.diesel > 0)]

	# Terminal stats
	df_refinery_terminals = df.loc[~(df==0).all(axis=1)].groupby('refinery')[['terminal']].count().reset_index();
	
	# Get all of the active transport connections
	df_downstream = df.loc[(~(df==0).all(axis=1))].reset_index(drop=True)

	# Determine the allocation of fuels from refineries to terminals.  Split based on percentage shares.
	df_split = df_downstream.set_index(['refinery','terminal'])
	df_split = df_split.groupby(level=0).apply(lambda x: x['diesel']/x['diesel'].sum())
	df_split.index = df_split.index.droplevel(0)
	df_split = df_split.reset_index()
	df_split.columns = ['refinery', 'terminal','alfac_diesel']
	df_downstream = pd.merge(df_downstream, df_split, on=['refinery', 'terminal'], how='left')
	df_split = df_downstream.set_index(['refinery','terminal'])
	df_split = df_split.groupby(level=0).apply(lambda x: x['gas']/x['gas'].sum())
	df_split.index = df_split.index.droplevel(0)
	df_split = df_split.reset_index()
	df_split.columns = ['refinery', 'terminal','alfac_gas']
	df_downstream = pd.merge(df_downstream, df_split, on=['refinery', 'terminal'], how='left')
	df_split = None
	df_downstream.fillna(0,inplace=True)
	

	# Combine downstream dataframe to upstream dataframe and send this to the server for visualization
	df_supply = pd.merge(df_upstream.reset_index(), df_downstream[['refinery', 'terminal', 'alfac_gas', 'alfac_diesel']], on='refinery', how='left');

	for i, row in df_supply.iterrows():
		if row['pathway'] == 'm2g' or row['pathway'] == 'pg':
			alf = row['alfac_gas']
			if alf < 1:
				df_supply.set_value(i,'Cropres (mt/yr)', row['Cropres (mt/yr)'] * alf);
				df_supply.set_value(i,'Forestres (mt/yr)', row['Forestres (mt/yr)'] * alf);
				df_supply.set_value(i,'Scrapwood (mt/yr)', row['Scrapwood (mt/yr)'] * alf);
				df_supply.set_value(i,'Gasoline (mt/yr)', row['Gasoline (mt/yr)'] * alf);  

		else:
			alf = row['alfac_diesel']
			if alf < 1:
				df_supply.set_value(i,'Cropres (mt/yr)', row['Cropres (mt/yr)'] * alf);
				df_supply.set_value(i,'Forestres (mt/yr)', row['Forestres (mt/yr)'] * alf);
				df_supply.set_value(i,'Scrapwood (mt/yr)', row['Scrapwood (mt/yr)'] * alf);
				df_supply.set_value(i,'Diesel (mt/year)', row['Diesel (mt/year)'] * alf);  



	#df_supply = pd.merge(df_refine_gate, df_downstream[['refinery', 'terminal', 'alfac_gas', 'alfac_diesel']], on='refinery', how='left');
	#df_supply['mt_gas_to_terminal'] = df_supply['mt_gas_at_refinery']*df_supply['alfac_gas']
	#df_supply['mt_diesel_to_terminal'] = df_supply['mt_diesel_at_refinery']*df_supply['alfac_diesel']
	#server.supply_chain(df_supply)


	"""

	Section 3: Export summary data to excel for data exchange purposes. 


	"""


	# Grab relevant labels from server 
	county_names = server.pg_df("""SELECT geoid AS "County FIPS", name AS "County Name" FROM counties  WHERE statefp='06' """)
	county_names['County FIPS'] = county_names['County FIPS'].astype(int);
	refinery_types = server.pg_df("""SELECT id AS "Refinery ID", type AS "Refinery Type" FROM facility_locations_about_cities""");
	terminal_data = server.pg_df("""SELECT a.id AS "Terminal ID", b.name AS "Terminal Name", b.million_gals_gasoline_2012, b.million_gals_diesel_2012 FROM downstream_locations_california a, fuel_demand_service_areas b WHERE a.terminal_id=b.terminal_gid""")
	terminal_names = terminal_data[['Terminal ID', 'Terminal Name']];

	# Grab base data from model input folder
	feedstocks = pd.read_csv(s.config.get('Paths', 'availability_data'), header=None);
	feedstocks.index = pd.read_csv(s.config.get('Extra', 'biomass_availability_origin_path'))
	feedstocks = feedstocks.reset_index()
	feedstocks.columns = ['County FIPS', 'cropres_stock','forestres_stock', 'scrapwood_stock'];

	# Broad Overview
	a = df_supply[['county','refinery', 'terminal', 'pathway', 'Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)', 'Gasoline (mt/yr)','Diesel (mt/year)']];
	a.columns = [['County FIPS','Refinery ID', 'Terminal ID','Fuel Pathway', 'Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)', 'Gasoline (mt/yr)','Diesel (mt/year)']];
	a = pd.merge(county_names, a, on='County FIPS', how='left').sort('County FIPS')
	a = pd.merge(a, refinery_types, on='Refinery ID', how='left')
	supply_chain_overview = pd.merge(a, terminal_names, on='Terminal ID', how='left')
	

	# Feedstock Overview
	b = df_supply[['county','refinery', 'terminal', 'pathway', 'Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)', 'Gasoline (mt/yr)','Diesel (mt/year)']];
	b.columns = [['County FIPS','Refinery ID', 'Terminal ID','Fuel Pathway', 'Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)', 'Gasoline (mt/yr)','Diesel (mt/year)']]; 
	b = b.groupby('County FIPS')[['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)', 'Gasoline (mt/yr)','Diesel (mt/year)']].sum().reset_index();
	b = pd.merge(b, feedstocks,on='County FIPS', how='left');
	b['Cropres Util.'] = b['Cropres (mt/yr)'] / b['cropres_stock'];
	b['Forestres Util.'] = b['Forestres (mt/yr)'] / b['forestres_stock'];
	b['Scrapwood Util.'] = b['Scrapwood (mt/yr)'] / b['scrapwood_stock'];
	b.fillna(0, inplace=True);
	b.drop(['cropres_stock', 'forestres_stock', 'scrapwood_stock'],inplace=True,axis=1)
	feedstock_summary = pd.merge(county_names, b, on='County FIPS', how='left').sort('County FIPS')

	# Upstream Transport Overview
	temp_table = "temp_table232323232"
	server.df_pg(df_supply.drop_duplicates(['county', 'refinery'])[['county', 'refinery']], temp_table)
	SQLCommmand = """SELECT a.county, a.refinery, b.km_road AS crop_km_road, b.km_rail AS crop_km_rail, c.km_road AS wood_km_road, c.km_rail AS wood_km_rail \
			FROM %(table_random)s a \
			LEFT JOIN cij_ca_feedstocks_intermodal_crop b  \
			ON b.origin = a.county AND a.refinery = b.destination \
			LEFT JOIN cij_ca_feedstocks_intermodal_forest c \
			ON a.county=c.origin AND a.refinery=c.destination""" % {'table_random': temp_table}
	df_upL = server.pg_df(SQLCommmand);
	df_upL = pd.merge(df_upL, df_supply.groupby(['county', 'refinery'])[['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)']].sum().reset_index(), on=['county', 'refinery'], how='left');
	df_upL['Cropres Road (tkm/yr)'] = df_upL['Cropres (mt/yr)'] * df_upL['crop_km_road']
	df_upL['Cropres Rail (tkm/yr)'] = df_upL['Cropres (mt/yr)'] * df_upL['crop_km_rail']
	df_upL['Forestres Road (tkm/yr)'] = df_upL['Forestres (mt/yr)'] * df_upL['wood_km_road']
	df_upL['Forestres Rail (tkm/yr)'] = df_upL['Forestres (mt/yr)'] * df_upL['wood_km_rail']
	df_upL['Scrapwood Road (tkm/yr)'] = df_upL['Scrapwood (mt/yr)'] * df_upL['wood_km_road']
	df_upL['Scrapwood Rail (tkm/yr)'] = df_upL['Scrapwood (mt/yr)'] * df_upL['wood_km_rail']
	df_upL['Total Freight Turnover (tkm/yr)'] = df_upL['Cropres Road (tkm/yr)'] + df_upL['Cropres Rail (tkm/yr)'] + df_upL['Forestres Road (tkm/yr)'] + df_upL['Forestres Rail (tkm/yr)'] + df_upL['Scrapwood Road (tkm/yr)'] + df_upL['Scrapwood Rail (tkm/yr)']
	df_upL['Total Road Turnover (tkm/yr)'] = df_upL['Cropres Road (tkm/yr)'] + df_upL['Forestres Road (tkm/yr)']  + df_upL['Scrapwood Road (tkm/yr)']
	df_upL['Total Rail Turnover (tkm/yr)'] =  df_upL['Cropres Rail (tkm/yr)'] + df_upL['Forestres Rail (tkm/yr)'] +  df_upL['Scrapwood Rail (tkm/yr)']
	#df_upL.drop(['crop_km_road', 'crop_km_rail', 'wood_km_road','wood_km_rail'], inplace=True, axis=1)
	df_upL.rename(columns={'county': 'County FIPS', 'refinery': 'Refinery ID'}, inplace=True)
	df_upL = pd.merge(county_names, df_upL, on='County FIPS', how='left').sort('County FIPS')
	

	# Production Overview
	temp_table = "temp_table232323232"
	server.df_pg(df_supply.drop_duplicates(['refinery'])[['refinery']], temp_table)
	SQLCommmand ="""SELECT a.refinery, CAST(c.geoid AS integer) AS "Refinery FIPS", c.name AS "Refinery County", ST_X(b.the_geom) as Lon, ST_Y(b.the_geom) AS Lat, b.type, b.new_construction \
			FROM %(table_random)s a \
			LEFT JOIN facility_locations_about_cities b\
			ON a.refinery = b.id \
			LEFT JOIN counties c \
			ON ST_Intersects(b.the_geom, c.geom) \
			WHERE c.statefp = '06'""" % {'table_random': temp_table};
	df_refinery = server.pg_df(SQLCommmand);
	df_refinery = pd.merge(df_refinery, df_supply.groupby('refinery')[['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)', 'Gasoline (mt/yr)','Diesel (mt/year)']].sum().reset_index(), on='refinery', how='left')
	# Fuel by pathway
	df_ref_small = df_supply[['county','refinery', 'terminal', 'pathway', 'Gasoline (mt/yr)','Diesel (mt/year)']];
	a = df_ref_small.groupby(['refinery', 'pathway'])[['Gasoline (mt/yr)', 'Diesel (mt/year)']].sum().sum(axis=1).reset_index();
	a.columns = ['refinery', 'pathway', 'Fuel (mt/yr)']
	a = pd.pivot_table(a, index=['refinery'], columns='pathway', values='Fuel (mt/yr)').reset_index();
	a.fillna(0,inplace=True);
	df_refinery = pd.merge(df_refinery, a, on='refinery', how='left');
	#On-site Storage
	df_refinery["Onsite-Storage (mt/yr)"] = df_refinery['Cropres (mt/yr)'] + df_refinery['Forestres (mt/yr)'] + df_refinery['Scrapwood (mt/yr)']
	df_refinery = pd.merge(df_refinery,df_refinery_terminals, on='refinery', how='left')
	#In-county suppliers
	df_ref_small = df_refinery[['refinery', 'Refinery FIPS']];
	df_ref_small = pd.merge(df_supply.groupby(['county', 'refinery'])[['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)']].sum().reset_index() ,df_ref_small, on='refinery', how='left')
	df_ref_small['In-County Feedstocks (mt/yr)'] = df_ref_small.apply(lambda row: in_county_supplies(row), axis=1);
	df_refinery = pd.merge(df_refinery, df_ref_small.groupby('refinery')[['In-County Feedstocks (mt/yr)']].sum().reset_index(), on='refinery', how='left');
	df_refinery.rename(columns={'terminal': 'Connected Bulk Terminals', 'refinery': 'Refinery ID'}, inplace=True);
	df_refinery['In-County Feedstocks (%)'] = df_refinery['In-County Feedstocks (mt/yr)'] / (df_refinery['Cropres (mt/yr)'] + df_refinery['Forestres (mt/yr)'] + df_refinery['Scrapwood (mt/yr)'])
	

	# Downstream Transport Overview
	temp_table = "temp_table232323232"
	server.df_pg(df_supply.drop_duplicates(['refinery', 'terminal'])[['refinery', 'terminal']], temp_table)
	SQLCommmand = """SELECT a.refinery, a.terminal, b.km_road, b.km_rail, b.km_pipe\
			FROM %(table_random)s a \
			LEFT JOIN sjk_ca_feedstocks_intermodal_pipeline b \
			ON a.refinery=b.origin AND a.terminal=b.destination """ % {'table_random': temp_table};
	df_downL= server.pg_df(SQLCommmand);
	df_downL = pd.merge(df_downL, df_supply.groupby(['refinery', 'terminal'])[['Gasoline (mt/yr)','Diesel (mt/year)']].sum().reset_index(), on=['refinery', 'terminal'], how='left');
	df_downL['Gasoline Road (tkm/yr)'] = df_downL['Gasoline (mt/yr)'] * df_downL['km_road']
	df_downL['Gasoline Rail (tkm/yr)'] = df_downL['Gasoline (mt/yr)'] * df_downL['km_rail']
	df_downL['Gasoline Pipeline (tkm/yr)'] = df_downL['Gasoline (mt/yr)'] * df_downL['km_pipe']
	df_downL['Diesel Road (tkm/yr)'] = df_downL['Diesel (mt/year)'] * df_downL['km_road']
	df_downL['Diesel Rail (tkm/yr)'] = df_downL['Diesel (mt/year)'] * df_downL['km_rail']
	df_downL['Diesel Pipeline (tkm/yr)'] = df_downL['Diesel (mt/year)'] * df_downL['km_pipe']
	df_downL['Total Freight Turnover (tkm/yr)'] = df_downL['Gasoline Road (tkm/yr)'] + df_downL['Gasoline Rail (tkm/yr)'] + df_downL['Gasoline Pipeline (tkm/yr)'] + df_downL['Diesel Road (tkm/yr)'] + df_downL['Diesel Rail (tkm/yr)'] + df_downL['Diesel Pipeline (tkm/yr)']
	df_downL['Total Road Turnover (tkm/yr)'] = df_downL['Gasoline Road (tkm/yr)'] +  df_downL['Diesel Road (tkm/yr)'] 
	df_downL['Total Rail Turnover (tkm/yr)'] =  df_downL['Gasoline Rail (tkm/yr)'] + df_downL['Diesel Rail (tkm/yr)'] 
	df_downL['Total Pipeline Turnover (tkm/yr)'] =  df_downL['Gasoline Pipeline (tkm/yr)'] + df_downL['Diesel Pipeline (tkm/yr)']
	#df_downL.drop(['km_road', 'km_rail', 'km_pipe'],inplace=True,axis=1);
	df_downL.rename(columns={'terminal': 'Terminal ID', 'refinery': 'Refinery ID'}, inplace=True);
	df_downL = pd.merge(df_downL, refinery_types, on='Refinery ID', how='left');
	df_downL = pd.merge(df_refinery[['Refinery ID','Refinery FIPS', 'Refinery County']], df_downL, on='Refinery ID', how='right');
	

	# Terminal Summary
	df_terminal = df_supply.groupby('terminal')['Gasoline (mt/yr)','Diesel (mt/year)'].sum().reset_index()
	df_terminal.rename(columns={'terminal': 'Terminal ID'}, inplace=True);
	df_terminal = pd.merge(terminal_names, df_terminal, on='Terminal ID', how='right');
	df_terminal_small = server.pg_df("""SELECT a.id AS "Terminal ID",  ST_X(a.the_geom) AS "Lon", ST_Y(a.the_geom) AS "Lat", CAST(b.geoid AS integer) AS "Terminal FIPS", a.million_gals_gasoline_2012 *6/2204*1000000 AS "Gas Capacity (mt/yr)", a.million_gals_diesel_2012 * 7.5/2204*1000000 AS "Diesel Capacity (mt/yr)"  FROM downstream_locations_california a, counties b WHERE ST_Intersects(a.the_geom, b.geom) AND b.statefp='06'""")
	df_terminal =  pd.merge(df_terminal_small, df_terminal, on='Terminal ID', how='right');
	df_terminal['Gas Util. (%)'] = df_terminal['Gasoline (mt/yr)'] / df_terminal['Gas Capacity (mt/yr)']
	df_terminal['Diesel Util. (%)'] = df_terminal['Diesel (mt/year)'] / df_terminal['Diesel Capacity (mt/yr)']
	
	
	# Supply-chain Executive Summary
	totals = []
	totals.append({"Description": 'Annual Gasoline Production', 'Results': df_terminal['Gasoline (mt/yr)'].sum() * 2204/6, 'Units': 'gal/yr'});
	totals.append({"Description": 'Annual Diesel Production', 'Results': df_terminal['Diesel (mt/year)'].sum()* 2204/7.5, 'Units': 'gal/yr'});
	totals.append({"Description": 'Gasoline Market Share', 'Results': round(df_terminal['Gasoline (mt/yr)'].sum() / (terminal_data['million_gals_gasoline_2012'].sum() * 6/2204 *1000000) * 100,1), 'Units': '%'});
	totals.append({"Description": 'Diesel Market Share', 'Results': round(df_terminal['Diesel (mt/year)'].sum() / (terminal_data['million_gals_diesel_2012'].sum() * 7.5/2204 *1000000) * 100,1), 'Units': '%'});
	totals.append({"Description": 'Annual Feedstock Consumption', 'Results':  df_supply[['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)',]].sum(axis=1).sum(axis=0), 'Units': 'mt/yr'});
	totals.append({"Description": 'Crop Residue Consumption', 'Results': feedstock_summary['Cropres (mt/yr)'].sum(), 'Units': 'mt/yr'});
	totals.append({"Description": 'Forestres Residue Consumption', 'Results': feedstock_summary['Forestres (mt/yr)'].sum(), 'Units': 'mt/yr'});
	totals.append({"Description": 'Scrapwood Consumption', 'Results': feedstock_summary['Scrapwood (mt/yr)'].sum(), 'Units': 'mt/yr'});
	totals.append({"Description": 'Number of Refineries', 'Results': len(supply_chain_overview['Refinery ID'].unique()), 'Units': 'Units'});
	totals.append({"Description": 'Number of New Refineries', 'Results': df_refinery[df_refinery.new_construction == 1]['Refinery ID'].count(), 'Units': 'Units'});
	totals.append({"Description": 'Feedstock Storage at Refinery, mean', 'Results': df_refinery['Onsite-Storage (mt/yr)'].mean(), 'Units': 'mt/yr'});
	totals.append({"Description": 'M2G Feedstock', 'Results': df_supply[df_supply.pathway=='m2g'][['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)',]].sum(axis=1).sum(axis=0), 'Units': 'mt/year'})
	totals.append({"Description": 'FT Feedstock', 'Results': df_supply[df_supply.pathway=='ft'][['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)',]].sum(axis=1).sum(axis=0), 'Units': 'mt/year'})
	totals.append({"Description": 'PG Feedstock', 'Results': df_supply[df_supply.pathway=='pg'][['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)',]].sum(axis=1).sum(axis=0), 'Units': 'mt/year'})
	totals.append({"Description": 'PD Feedstock', 'Results': df_supply[df_supply.pathway=='pd'][['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)',]].sum(axis=1).sum(axis=0), 'Units': 'mt/year'})
	totals.append({"Description": 'Gas Production at Refinery , mean', 'Results': df_refinery[df_refinery['Gasoline (mt/yr)'] > 0]['Gasoline (mt/yr)'].mean() * 2204/6, 'Units': 'gal/yr'});
	totals.append({"Description": 'Diesel Production at Refinery, mean', 'Results': df_refinery[df_refinery['Diesel (mt/year)'] > 0]['Diesel (mt/year)'].mean() * 2204/7.5, 'Units': 'gal/yr'});
	totals.append({"Description": 'Number of Terminals', 'Results': df_terminal['Terminal ID'].count(), 'Units': 'Units'});
	totals.append({"Description": 'Gas Storage at Terminal, mean', 'Results': df_terminal['Gasoline (mt/yr)'].mean() * 2204/6, 'Units': 'gal/yr'});
	totals.append({"Description": 'Diesel Storage at Terminal, mean', 'Results': df_terminal['Diesel (mt/year)'].mean() * 2204/7.5, 'Units': 'gal/yr'});
	totals.append({"Description": 'Total Ton-Kilometers', 'Results': df_upL['Total Freight Turnover (tkm/yr)'].sum() + df_downL['Total Freight Turnover (tkm/yr)'].sum(), 'Units': 'tkm/yr'});
	totals.append({"Description": 'Total Ton-Kilometers, Upstream', 'Results': 100*df_upL['Total Freight Turnover (tkm/yr)'].sum()/(df_upL['Total Freight Turnover (tkm/yr)'].sum() + df_downL['Total Freight Turnover (tkm/yr)'].sum()), 'Units': '%'});
	totals.append({"Description": 'Total Ton-Kilometers, Downstream', 'Results': 100*df_downL['Total Freight Turnover (tkm/yr)'].sum()/(df_upL['Total Freight Turnover (tkm/yr)'].sum() + df_downL['Total Freight Turnover (tkm/yr)'].sum()), 'Units': '%'});
	totals.append({"Description": 'Total Road Ton-Kilometers', 'Results': df_upL['Total Road Turnover (tkm/yr)'].sum() + df_downL['Total Road Turnover (tkm/yr)'].sum(), 'Units': 'tkm/yr'});
	totals.append({"Description": 'Total Rail Ton-Kilometers', 'Results': df_upL['Total Rail Turnover (tkm/yr)'].sum() + df_downL['Total Rail Turnover (tkm/yr)'].sum(), 'Units': 'tkm/yr'});
	totals.append({"Description": 'Total Pipeline Ton-Kilometers', 'Results':  df_downL['Total Pipeline Turnover (tkm/yr)'].sum(), 'Units': 'tkm/yr'});
	


	# Emissions 
	# Load emission factors
	handling = json.load(open('src/base/handling_emission_factors.json'));
	production = json.load(open('src/base/fuel_production_emission_factors.json'));
	transport = json.load(open('src/base/transport_emission_factors.json'))
	conventional = json.load(open('src/base/conventional_emission_factors.json'))
	total_demand = server.pg_df('SELECT SUM(million_gals_gasoline_2012*1000000*(6.0/2209.0)) AS mt_gas_demand, SUM(million_gals_diesel_2012*1000000*(7.5/2209.0)) AS mt_diesel_demand FROM downstream_locations_california;')

	data = []
	change_in_baseline = []
	for e in ['GHG','NOx', "PM10", 'PM2.5', "SOx", "CO"]:
		h = handling['cropres'][e]*feedstock_summary['Cropres (mt/yr)'].sum() +  handling['forestres'][e]*feedstock_summary['Forestres (mt/yr)'].sum() + handling['scrapwood'][e]*feedstock_summary['Scrapwood (mt/yr)'].sum();
		t = transport['road'][e] * (df_upL['Total Road Turnover (tkm/yr)'].sum() + df_downL['Total Road Turnover (tkm/yr)'].sum()) + transport['rail'][e]*(df_upL['Total Rail Turnover (tkm/yr)'].sum() + df_downL['Total Rail Turnover (tkm/yr)'].sum()) + transport['pipe'][e]*df_downL['Total Pipeline Turnover (tkm/yr)'].sum() + (supply_chain_overview['Gasoline (mt/yr)'].sum() + supply_chain_overview['Diesel (mt/year)'].sum()) * transport['road'][e] * 45 # 45 km last mile
		p = production['m2g'][e] * df_supply[df_supply.pathway=='m2g'][['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)',]].sum(axis=1).sum(axis=0) + production['ft'][e] * df_supply[df_supply.pathway=='ft'][['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)',]].sum(axis=1).sum(axis=0) + production['pg'][e]* df_supply[df_supply.pathway=='pg'][['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)',]].sum(axis=1).sum(axis=0) + production['pd'][e] * df_supply[df_supply.pathway=='pd'][['Cropres (mt/yr)', 'Forestres (mt/yr)', 'Scrapwood (mt/yr)',]].sum(axis=1).sum(axis=0);
		c = supply_chain_overview['Gasoline (mt/yr)'].sum() * conventional['gas'][e] + supply_chain_overview['Diesel (mt/year)'].sum() * conventional['diesel'][e];
		B = float(total_demand['mt_gas_demand']* conventional['gas'][e] + total_demand['mt_diesel_demand'] * conventional['diesel'][e]);

		data.append({'Pollutant (kg y-1)': e, "Handling": h, "Transport": t, "Capital": 0, "Fuel Production": p, "Total":  h+t+p})
		change_in_baseline.append({'Pollutant (kg y-1)': e,'Scenario State Total':  (h+t+p-c) + B, "Baseline State Total": B, 'Change from Baseline': h+t+p-c, 'Percentage Change from Baseline': (h+t+p-c) / B})

	
	# Update 
	supply_chain_overview = pd.merge(supply_chain_overview, df_upL[['County FIPS', 'Refinery ID', 'crop_km_road','crop_km_rail','wood_km_road','wood_km_rail']], on=['County FIPS', 'Refinery ID'], how='left')
	supply_chain_overview['up_road_tkm'] = supply_chain_overview['crop_km_road']*supply_chain_overview['Cropres (mt/yr)'] + supply_chain_overview['wood_km_road']* ( supply_chain_overview['Forestres (mt/yr)'] + supply_chain_overview['Scrapwood (mt/yr)'] )
	supply_chain_overview['up_rail_tkm'] = supply_chain_overview['crop_km_rail']*supply_chain_overview['Cropres (mt/yr)'] + supply_chain_overview['wood_km_rail']* ( supply_chain_overview['Forestres (mt/yr)'] + supply_chain_overview['Scrapwood (mt/yr)'] )
	supply_chain_overview.drop(['crop_km_road', 'crop_km_rail', 'wood_km_road', 'wood_km_rail'],inplace=True,axis=1);
	supply_chain_overview = pd.merge(supply_chain_overview, df_downL[['Refinery ID', 'Terminal ID','km_road','km_rail','km_pipe']], on=['Refinery ID', 'Terminal ID'], how='left');
	supply_chain_overview['down_road_tkm'] = supply_chain_overview['km_road'] * (supply_chain_overview['Gasoline (mt/yr)'] + supply_chain_overview['Diesel (mt/year)'])
	supply_chain_overview['down_rail_tkm'] = supply_chain_overview['km_rail'] * (supply_chain_overview['Gasoline (mt/yr)'] + supply_chain_overview['Diesel (mt/year)'])
	supply_chain_overview['down_pipe_tkm'] = supply_chain_overview['km_pipe'] * (supply_chain_overview['Gasoline (mt/yr)'] + supply_chain_overview['Diesel (mt/year)'])
	supply_chain_overview.drop(['km_road', 'km_rail', 'km_pipe'],inplace=True,axis=1);
	mjs = {'m2g': 2204/6*122.481433931817, 'pg': 2204/6*122.481433931817, 'ft': 2204/7.5*134.47741897622, 'pd': 2204/7.5*134.47741897622}
	supply_chain_overview.dropna(inplace=True)
	supply_chain_overview['CO2,e g/MJ'] = (handling['cropres']['GHG']*supply_chain_overview['Cropres (mt/yr)'] +  handling['forestres']['GHG']*supply_chain_overview['Forestres (mt/yr)'] + handling['scrapwood']['GHG']*supply_chain_overview['Scrapwood (mt/yr)'] +  transport['road']['GHG'] * (supply_chain_overview['up_road_tkm'] + supply_chain_overview['down_road_tkm']) + transport['rail']['GHG'] * (supply_chain_overview['up_rail_tkm'] + supply_chain_overview['down_rail_tkm']) + transport['pipe']['GHG'] * supply_chain_overview['down_pipe_tkm'] + (supply_chain_overview['Cropres (mt/yr)'] + supply_chain_overview['Forestres (mt/yr)'] + supply_chain_overview['Scrapwood (mt/yr)']) * supply_chain_overview['Fuel Pathway'].map(lambda x: production[x]['GHG'])) *1000 / (supply_chain_overview['Fuel Pathway'].map(lambda x: mjs[x]) * (supply_chain_overview['Gasoline (mt/yr)'] + supply_chain_overview['Diesel (mt/year)']));
	supply_chain_overview['NOx g/MJ'] = (handling['cropres']['NOx']*supply_chain_overview['Cropres (mt/yr)'] +  handling['forestres']['NOx']*supply_chain_overview['Forestres (mt/yr)'] + handling['scrapwood']['NOx']*supply_chain_overview['Scrapwood (mt/yr)'] +  transport['road']['NOx'] * (supply_chain_overview['up_road_tkm'] + supply_chain_overview['down_road_tkm']) + transport['rail']['NOx'] * (supply_chain_overview['up_rail_tkm'] + supply_chain_overview['down_rail_tkm']) + transport['pipe']['NOx'] * supply_chain_overview['down_pipe_tkm'] + (supply_chain_overview['Cropres (mt/yr)'] + supply_chain_overview['Forestres (mt/yr)'] + supply_chain_overview['Scrapwood (mt/yr)']) * supply_chain_overview['Fuel Pathway'].map(lambda x: production[x]['NOx'])) *1000 / (supply_chain_overview['Fuel Pathway'].map(lambda x: mjs[x]) * (supply_chain_overview['Gasoline (mt/yr)'] + supply_chain_overview['Diesel (mt/year)']));
	supply_chain_overview['PM10 g/MJ'] = (handling['cropres']['PM10']*supply_chain_overview['Cropres (mt/yr)'] +  handling['forestres']['PM10']*supply_chain_overview['Forestres (mt/yr)'] + handling['scrapwood']['PM10']*supply_chain_overview['Scrapwood (mt/yr)'] +  transport['road']['PM10'] * (supply_chain_overview['up_road_tkm'] + supply_chain_overview['down_road_tkm']) + transport['rail']['PM10'] * (supply_chain_overview['up_rail_tkm'] + supply_chain_overview['down_rail_tkm']) + transport['pipe']['PM10'] * supply_chain_overview['down_pipe_tkm'] + (supply_chain_overview['Cropres (mt/yr)'] + supply_chain_overview['Forestres (mt/yr)'] + supply_chain_overview['Scrapwood (mt/yr)']) * supply_chain_overview['Fuel Pathway'].map(lambda x: production[x]['PM10'])) *1000 / (supply_chain_overview['Fuel Pathway'].map(lambda x: mjs[x]) * (supply_chain_overview['Gasoline (mt/yr)'] + supply_chain_overview['Diesel (mt/year)']));
	supply_chain_overview['PM2.5 g/MJ'] = (handling['cropres']['PM2.5']*supply_chain_overview['Cropres (mt/yr)'] +  handling['forestres']['PM2.5']*supply_chain_overview['Forestres (mt/yr)'] + handling['scrapwood']['PM2.5']*supply_chain_overview['Scrapwood (mt/yr)'] +  transport['road']['PM2.5'] * (supply_chain_overview['up_road_tkm'] + supply_chain_overview['down_road_tkm']) + transport['rail']['PM2.5'] * (supply_chain_overview['up_rail_tkm'] + supply_chain_overview['down_rail_tkm']) + transport['pipe']['PM2.5'] * supply_chain_overview['down_pipe_tkm'] + (supply_chain_overview['Cropres (mt/yr)'] + supply_chain_overview['Forestres (mt/yr)'] + supply_chain_overview['Scrapwood (mt/yr)']) * supply_chain_overview['Fuel Pathway'].map(lambda x: production[x]['PM2.5'])) *1000 / (supply_chain_overview['Fuel Pathway'].map(lambda x: mjs[x]) * (supply_chain_overview['Gasoline (mt/yr)'] + supply_chain_overview['Diesel (mt/year)']));
	supply_chain_overview['SOx g/MJ'] = (handling['cropres']['SOx']*supply_chain_overview['Cropres (mt/yr)'] +  handling['forestres']['SOx']*supply_chain_overview['Forestres (mt/yr)'] + handling['scrapwood']['SOx']*supply_chain_overview['Scrapwood (mt/yr)'] +  transport['road']['SOx'] * (supply_chain_overview['up_road_tkm'] + supply_chain_overview['down_road_tkm']) + transport['rail']['SOx'] * (supply_chain_overview['up_rail_tkm'] + supply_chain_overview['down_rail_tkm']) + transport['pipe']['SOx'] * supply_chain_overview['down_pipe_tkm'] + (supply_chain_overview['Cropres (mt/yr)'] + supply_chain_overview['Forestres (mt/yr)'] + supply_chain_overview['Scrapwood (mt/yr)']) * supply_chain_overview['Fuel Pathway'].map(lambda x: production[x]['SOx'])) *1000 / (supply_chain_overview['Fuel Pathway'].map(lambda x: mjs[x]) * (supply_chain_overview['Gasoline (mt/yr)'] + supply_chain_overview['Diesel (mt/year)']));
	supply_chain_overview['CO g/MJ'] = (handling['cropres']['CO']*supply_chain_overview['Cropres (mt/yr)'] +  handling['forestres']['CO']*supply_chain_overview['Forestres (mt/yr)'] + handling['scrapwood']['CO']*supply_chain_overview['Scrapwood (mt/yr)'] +  transport['road']['CO'] * (supply_chain_overview['up_road_tkm'] + supply_chain_overview['down_road_tkm']) + transport['rail']['CO'] * (supply_chain_overview['up_rail_tkm'] + supply_chain_overview['down_rail_tkm']) + transport['pipe']['CO'] * supply_chain_overview['down_pipe_tkm'] + (supply_chain_overview['Cropres (mt/yr)'] + supply_chain_overview['Forestres (mt/yr)'] + supply_chain_overview['Scrapwood (mt/yr)']) * supply_chain_overview['Fuel Pathway'].map(lambda x: production[x]['CO'])) *1000 / (supply_chain_overview['Fuel Pathway'].map(lambda x: mjs[x]) * (supply_chain_overview['Gasoline (mt/yr)'] + supply_chain_overview['Diesel (mt/year)']));


	# Set excel writer  
	writer = pd.ExcelWriter(s.config.get('Paths', 'results_path') + s.config.get('Extra', 'scenario') +'_supply_chain_results.xls')
	
	# Save
	pd.DataFrame(totals).to_excel(writer, 'Executive Summary', index=False);
	pd.DataFrame(change_in_baseline).to_excel(writer,'Emissions Change Baseline', columns=['Pollutant (kg y-1)', 'Scenario State Total', 'Baseline State Total', 'Change from Baseline', 'Percentage Change from Baseline'], index=False);
	pd.DataFrame(data).to_excel(writer,'Emissions by Component', columns=['Pollutant (kg y-1)', "Handling", "Transport", "Capital", "Fuel Production",  "Total"], index=False);
	supply_chain_overview.to_excel(writer,'Supply-Chain Overview', index=False);
	feedstock_summary.to_excel(writer, 'Feedstock Summary', index=False);
	df_upL.to_excel(writer,'Upstream Transport Summary', index=False);
	df_refinery.to_excel(writer,'Refinery Summary', index=False);
	df_downL.to_excel(writer,'Downstream Transport Summary', index=False);
	df_terminal.sort('Terminal ID').to_excel(writer,'Terminal Summary', index=False);
	writer.save()

	# Refineries
	tb= s.config.get('Extra', 'scenario')[:3].lower()+'_refinery_overview';
	d = df_refinery[['Refinery ID', 'Refinery FIPS', 'Gasoline (mt/yr)',	'Diesel (mt/year)']]
	d.columns = ['refinery', 'refinery_fips', 'gas', 'diesel']
	d['total'] = d.gas + d.diesel
	server.df_pg(d, tb);
	connection = server.cur.connect()
	SQLcommand = """ALTER TABLE %(tb)s ADD COLUMN the_geom geometry; UPDATE %(tb)s z SET the_geom = a.the_geom FROM facility_locations_about_cities a WHERE CAST(z.refinery as integer)=a.id; """ % { 'tb': tb}
	connection.execute(SQLcommand)

	# Regional 
	supply_chain_overview.columns = ['county', 'county_name', 'refinery', 'terminal', 'pathway', 'cropres', 'forestres', 'scrapwood', 'gas', 'diesel', 'refinery_type', 'terminal_name', 'up_road_tkm', 'up_rail_tkm', 'down_road_tkm','down_rail_tkm', 'down_pipe_tkm', 'CO2,e g/MJ', 'NOx g/MJ', 'PM10 g/MJ', 'PM2.5 g/MJ', 'SOx g/MJ', 'CO g/MJ']
	df_refinery = df_refinery[['Refinery ID', 'Refinery FIPS']]
	df_refinery.columns = ['refinery', 'refinery_fips']
	supply_chain_overview = pd.merge(supply_chain_overview, df_refinery, on='refinery', how='left');
	df_terminal = df_terminal[['Terminal ID','Terminal FIPS']]
	df_terminal.columns = ['terminal', 'terminal_fips']
	supply_chain_overview = pd.merge(supply_chain_overview, df_terminal, on='terminal', how='left');

	tb= s.config.get('Extra', 'scenario')[:3].lower()+'_supply_chain_overview';
	server.df_pg(supply_chain_overview, tb);

	connection = server.cur.connect()
	SQLcommand = """ALTER TABLE %(tb)s ADD COLUMN up_region text; UPDATE %(tb)s z SET up_region = a.label FROM ca_agg_divisions a WHERE CAST(z.county as integer)=a.county; """ % { 'tb': tb}
	connection.execute(SQLcommand)
	SQLcommand = """ALTER TABLE %(tb)s ADD COLUMN mid_region text; UPDATE %(tb)s z SET mid_region = a.label FROM ca_agg_divisions a WHERE CAST(z.refinery_fips as integer)=a.county; """ % { 'tb': tb}
	connection.execute(SQLcommand)
	SQLcommand = """ALTER TABLE %(tb)s ADD COLUMN down_region text; UPDATE %(tb)s z SET down_region = a.label FROM ca_agg_divisions a WHERE CAST(z.terminal_fips as integer)=a.county; """ % { 'tb': tb}
	connection.execute(SQLcommand)
	SQLcommand = """ALTER TABLE %(tb)s ADD COLUMN the_geom geometry; UPDATE %(tb)s z SET the_geom = a.the_geom FROM facility_locations_about_cities a WHERE CAST(z.refinery as integer)=a.id; """ % { 'tb': tb}
	connection.execute(SQLcommand)

	connection.close();

	supply_chain_overview = server.pg_df(tb)
	supply_chain_overview.sort('up_region', inplace=True)
	upmass = supply_chain_overview.groupby(['up_region', 'mid_region'])[['gas', 'diesel']].sum().reset_index()
	downmass = supply_chain_overview.groupby(['mid_region', 'down_region'])[['gas', 'diesel']].sum().reset_index()

	sankey = dict()
	sankey = {"nodes": [], "links": []};
	sankey['nodes'].append({"node": 0,'name': 'NCM'})
	sankey['nodes'].append({'node': 1,'name': 'CV'})
	sankey['nodes'].append({'node': 2,'name': 'CCS'})
	sankey['nodes'].append({'node': 3,'name': 'NCM'})
	sankey['nodes'].append({'node': 4,'name': 'CV'})
	sankey['nodes'].append({'node': 5,'name': 'CCS'})
	sankey['nodes'].append({'node': 6,'name': 'NCM'})
	sankey['nodes'].append({'node': 7,'name': 'CV'})
	sankey['nodes'].append({'node': 8,'name': 'CCS'})

	for i, row in upmass.iterrows():
		u = {'ncmr': 0, 'cvr':1, 'ccsr': 2}
		m = {'ncmr': 3, 'cvr':4, 'ccsr': 5}
		sankey['links'].append({'source': u[row['up_region']], 'target': m[row['mid_region']],'value': row['gas'], 'fuel': 'gas'})
		sankey['links'].append({'source': u[row['up_region']], 'target': m[row['mid_region']],'value': row['diesel'], 'fuel': 'diesel'})

	for i, row in downmass.iterrows():
		d = {'ncmr': 6, 'cvr':7, 'ccsr': 8}
		sankey['links'].append({'source': m[row['mid_region']], 'target': d[row['down_region']],'value': row['gas'], 'fuel': 'gas'})
		sankey['links'].append({'source': m[row['mid_region']], 'target': d[row['down_region']],'value': row['diesel'], 'fuel': 'diesel'})

	json.dump(sankey, open(s.config.get('Paths', 'results_path')+tb+'.json', 'w'))
	
