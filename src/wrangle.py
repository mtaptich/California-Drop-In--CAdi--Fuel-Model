import pandas as pd, numpy as np, json, re

def Z(s, emissions):

	scenario = s.config.get('Extra', 'scenario');

	# Load emission factors
	handling = json.load(open('src/base/handling_emission_factors.json'));
	production = json.load(open('src/base/fuel_production_emission_factors.json'));
	conventional = json.load(open('src/base/conventional_emission_factors.json'))

	# Load new data
	up_l_data = np.genfromtxt(s.config.get('Paths', 'extra_path')+'%s_cij_%s.csv' % (scenario, emissions) , delimiter=','); 
	h_data = [handling['cropres'][emissions], handling['forestres'][emissions], handling['scrapwood'][emissions]];
	p_data = [production['pg'][emissions], production['m2g'][emissions], production['pd'][emissions], production['ft'][emissions]];
	down_l_data = np.genfromtxt(s.config.get('Paths', 'extra_path')+'%s_sjk_%s.csv' % (scenario, emissions) , delimiter=','); 
	ec_data = [conventional['gas'][emissions], conventional['diesel'][emissions] ]

	# Capital emissions
	cF = np.zeros(s.n_mid);

	# Upstream transport
	temp = [np.split(x[0], s.n_up) for x in np.split(up_l_data, s.n_mid, axis=0)];
	cUL = np.ndarray.flatten(np.tile(temp,s.n_pathways));
	
	# Handling and productition emissions
	ch = np.ndarray.flatten(np.tile(h_data, s.n_pathways * s.n_up * s.n_mid));
	cp = np.ndarray.flatten(np.tile(np.repeat(p_data, s.n_feedstocks), s.n_up * s.n_mid));

	#c_ = np.tile((np.nan_to_num(np.sum(s.cnv_block, axis=0) / np.sum(s.cnv_block, axis=0)) - 1) * -10000, s.n_up * s.n_mid)

	# Summation of costs
	cX = cUL + ch + cp ;

	cDL = np.repeat(down_l_data, s.n_fuels)
	#cec = np.tile(ec_data, s.n_mid * s.n_down)
	cW = cDL #- cec;

	cV = np.zeros(s.var['y'], dtype='int8')

	return np.hstack((cF, cX, cW, cV)), ch, cp, cUL

def up_freight(s, prefix='cij'):
	if s.trimmed_cols: 
		sset = np.zeros(s.var['x'] + s.var['y'] + s.var['w'] + s.var['v'] )
		np.put(sset, s.trimmed_cols, s.solution['set'])
		s.solution['set'] = sset

	[y, x, w, v] = np.split(s.solution['set'], s.blade)

	df = pd.DataFrame(np.split(x, s.n_up * s.n_mid * s.n_pathways), columns=['cropres','forestres', 'scrapwood'])
	
	counties  = pd.read_csv(s.config.get('Extra', 'upstream_transport_origin_path'));
	counties.columns = ['county']
	counties['county'] = counties['county'].map(lambda x: tuple(int(v) for v in re.findall("[0-9]+", x))[0])
	counties = counties['county'].unique()

	refineries = np.genfromtxt(s.config.get('Extra', 'downstream_transport_origin_path'), skip_header=1)

	pathways = ['pg','m2g','pd','ft']

	df['pathway'] = df.index.map(lambda x: pathways[x % s.n_pathways])
	df['origin'] = df.index.map(lambda x: counties[x // s.n_pathways % s.n_up])
	df['destination'] = df.index.map(lambda x: refineries[x // (s.n_up*s.n_pathways)])

	df = df.groupby(['origin', 'destination']).sum().reset_index()
	df['herb'] = df['cropres'];
	df['wood'] = df['forestres'] + df['scrapwood'];

	t = pd.read_csv(s.config.get('Paths', 'extra_path')+'%s_%s_km.csv' % (s.config.get('Extra', 'scenario'), prefix)); 
	df = pd.merge(df, t, on=['origin', 'destination'], how='left')

	# partially complete dataframe
	return df

def flare(df, outfile, parent='county', child='refinery', subchild='terminal', csize='total_feedstock_mt'):
	# choose columns to keep, in the desired nested json hierarchical order
	#df = df[["the_parent", "the_child", "child_size"]]


	# order in the groupby here matters, it determines the json nesting
	# the groupby call makes a pandas series by grouping 'the_parent' and 'the_child', while summing the numerical column 'child_size'
	df1 = df.groupby([parent, child, subchild])[csize].sum()
	df1 = df1.reset_index()


	# start a new flare.json document
	f = dict()
	f = {"name":"Counties", "children": []}

	for line in df1.values:
	    the_parent = line[0]
	    the_child = int(line[1])
	    the_sub_child = line[2]
	    child_size = line[3]

	    # make a list of keys
	    keys_list = []
	    for item in f['children']:
	        keys_list.append(item['name'])

	    # if 'the_parent' is NOT a key in the flare.json yet, append it
	    if not the_parent in keys_list:
	        f['children'].append({"name":the_parent, "children":[{"name":the_child, "children": []}]})

	    keys_list = []
	    for item in f['children']:
	        keys_list.append(item['name'])

	    sub_keys_list = []
	    for item in f['children'][keys_list.index(the_parent)]['children']:
	        sub_keys_list.append(item['name'])
	    
	    if not the_child in sub_keys_list:
	        f['children'][keys_list.index(the_parent)]['children'].append({"name":the_child, "children":[{"name":the_sub_child, "size":child_size, }]})
	    else:
	    	f['children'][keys_list.index(the_parent)]['children'][sub_keys_list.index(the_child)]['children'].append({"name":the_sub_child, "size":child_size})


	    


	json.dump(f, open(outfile, 'w'))

def is_gasoline(x):
	if x['pathway'] == 'm2g' or x['pathway'] == 'pg':
		return x['cropres'] * x['cropres_eff'] + x['forestres']*x['forestres_eff'] + x['scrapwood']*x['scrapwood_eff']
	else:
		return 0

def is_diesel(x):
	if x['pathway'] == 'ft' or x['pathway'] == 'pd':
		return x['cropres'] * x['cropres_eff'] + x['forestres']*x['forestres_eff'] + x['scrapwood']*x['scrapwood_eff']
	else:
		return 0

def in_county_supplies(x):
	if x['county'] == x['Refinery FIPS']:
		return x['Cropres (mt/yr)'] + x['Forestres (mt/yr)'] + x['Scrapwood (mt/yr)']
	else:
		return 0





