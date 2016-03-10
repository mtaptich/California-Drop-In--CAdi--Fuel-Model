import logging
from ConfigParser import ConfigParser
import utils.matrix_ops as mp
from numpy import genfromtxt, ndarray, repeat, tile, zeros, hstack, vstack, ones, identity, newaxis, array, savetxt, sum, nan_to_num, dot, split, nonzero
from cvxopt import matrix, spmatrix, sparse
import cvxopt.glpk


class FacilityLocationOptimizer:
	def __init__(s, scenario='EMISSIONS', r_cap=6800, m_units=180, config_path=None):
		# Configurate the model
		s.config_path = config_path
		s.configurate(config_path);
		s.scenario = scenario;
		s.r_cap = r_cap;
		s.m_units = m_units;

		#Load data and set global variables
		s.load();

	def configurate(s, config_path):
		config = ConfigParser()
		config.read(config_path);
		s.config = config

		# Set up logging
		log_path = config.get('Paths', 'log_file_path');
		logging.basicConfig(filename=log_path, level=logging.DEBUG);
		s.logging = logging.getLogger(__name__)

	def load(s):
		# Matrix building blocks
		s.cnv_block = genfromtxt(s.config.get('Paths', 'conversion_efficieny'), delimiter=',');

		# Objective Data
		s.f_data = genfromtxt(s.config.get('Paths', 'capital'), delimiter=',');
		s.up_l_data = genfromtxt(s.config.get('Paths', 'upstream_logistics'), delimiter=','); # rows: refineries, cols: feedstock locations
		s.h_data = genfromtxt(s.config.get('Paths', 'handling'), delimiter=',');
		s.p_data = genfromtxt(s.config.get('Paths', 'fuel_production'), delimiter=',');
		s.down_l_data = genfromtxt(s.config.get('Paths', 'downstream_logistics'), delimiter=','); # rows: refineries, cols: demand nodes
		s.ec_data = genfromtxt(s.config.get('Paths', 'conventional_emission_factor'), delimiter=','); 
		
		# Constraint Data
		s.b_data = genfromtxt(s.config.get('Paths', 'availability_data'), delimiter=',');
		s.d_data = genfromtxt(s.config.get('Paths', 'demand_data'), delimiter=',');

		# Update global variables
		s.n_up = s.b_data.shape[0];
		s.n_mid = s.up_l_data.shape[0];
		s.n_down = s.down_l_data.shape[1];
		s.n_feedstocks = s.b_data.shape[1]; 
		s.n_pathways = s.p_data.shape[0]; 
		s.n_fuels = s.d_data.shape[1]; 
		s.var = {'y': s.n_mid, 'x': s.cnv_block.shape[1]*s.n_up*s.n_mid, 'w': s.n_down * s.n_fuels*s.n_mid, 'v': s.n_mid} # Decision Variables
		s.blade = [s.var['y'], s.var['y']+s.var['x'], s.var['y']+s.var['x']+s.var['w']];

		# checks
		assert (s.up_l_data.shape[0] == s.down_l_data.shape[0]);

	def obective_builder(s, last_km_e = 45*0.130): #40km x ef_truck
		if s.scenario == 'EMISSIONS':
			# Capital emissions
			cF = ndarray.flatten(s.f_data);

			# Upstream transport
			"""
			up_l_data = | {c111, c121,...,c1npathways1}, {c211, c221,...,c2npathways1}, ... |
						| {c122, c122,...,c1npathways2}, {c212, c222,...,c2npathways2}, ... |
						|             ...,             ,             ...              , ... |


			Split the rows of matrix into individual arrays. Then, split each array by
			the number of upstream locations. These subarrays represent the set of 
			transportation costs for each feedstock sourcing location to the respective
			refinery. Since the transport costs for each feedstock-pathway combination
			are the sample, replicate this subarray by the number fuel pathways. Once
			this step is performed on each subarray for each row, flatten the arrays
			to get the final upsteam cost matrix. 

			"""
			temp = [split(x[0], s.n_up) for x in split(s.up_l_data, s.n_mid, axis=0)];
			cUL = ndarray.flatten(tile(temp,s.n_pathways));
			
			# Handling and productition emissions
			ch = ndarray.flatten(tile(s.h_data, s.n_pathways * s.n_up * s.n_mid));
			cp = ndarray.flatten(tile(repeat(s.p_data, s.n_feedstocks), s.n_up * s.n_mid));


			# To maintain a flexible model structure, some infeasible feedstock-pathway combinations are included. 
			# These pathways are determined to be infeasible if the fuel conversion efficiency is zero. Here, the
			# model forces the costs of these instances to an arbitrarily large cost (c_). Thus, these pathways 
			# will never be a part of the set of feasible optimal solutions.  
			c_ = tile((nan_to_num(sum(s.cnv_block, axis=0) / sum(s.cnv_block, axis=0)) - 1) * -10000, s.n_up * s.n_mid)
			
			# Summation of costs
			cX = cUL + ch + cp + c_;

			cDL = repeat(s.down_l_data + last_km_e, s.n_fuels)
			cec = tile(s.ec_data, s.n_mid * s.n_down)
			cW = cDL - cec;

			cV = zeros(s.var['y'], dtype='int8')

			Z = hstack((cF, cX, cW, cV))

			return matrix(Z)

		elif s.scenario == 'GASOLINE':
			# Produce the most amount of gasoline based on feedstock availability
			# while still considering the costs of moving goods (thus preserving 
			# likely markets). To do so, keep the transport costs the same but 
			# provide a substantial insentive to sell one type of fuel. 
			
			cF = ndarray.flatten(s.f_data);
			temp = [split(x[0], s.n_up) for x in split(s.up_l_data, s.n_mid, axis=0)];
			cUL = ndarray.flatten(tile(temp,s.n_pathways));

			# Negative fuel costs will drive optimial decision
			cDL = repeat(s.down_l_data + last_km_e, s.n_fuels)
			cec = tile([ 10000000.,0.], s.n_mid * s.n_down)
			cW = cDL - cec;

			cV = zeros(s.var['y'], dtype='int8')

			Z = hstack((cF, cUL, cW, cV))

			return matrix(Z)

		elif s.scenario == 'DIESEL':
			# Produce the most amount of diesel based on feedstock availability
			# while still considering the costs of moving goods (thus preserving 
			# likely markets). To do so, keep the transport costs the same but 
			# provide a substantial insentive to sell one type of fuel. 
			
			cF = ndarray.flatten(s.f_data);
			temp = [split(x[0], s.n_up) for x in split(s.up_l_data, s.n_mid, axis=0)];
			cUL = ndarray.flatten(tile(temp,s.n_pathways));

			# Negative fuel costs will drive optimial decision
			cDL = repeat(s.down_l_data + last_km_e, s.n_fuels)
			cec = tile([ 0.,10000000.], s.n_mid * s.n_down)
			cW = cDL - cec;

			cV = zeros(s.var['y'], dtype='int8')

			Z = hstack((cF, cUL, cW, cV))

			return matrix(Z)

		elif s.scenario == 'FUEL':
			# Produce the most amount of fuel based on feedstock availability
			# while still considering the costs of moving goods (thus preserving 
			# likely markets). 
			
			cF = ndarray.flatten(s.f_data);
			temp = [split(x[0], s.n_up) for x in split(s.up_l_data, s.n_mid, axis=0)];
			cUL = ndarray.flatten(tile(temp,s.n_pathways));

			# Negative fuel costs will drive optimial decision
			cDL = repeat(s.down_l_data, s.n_fuels)
			cec = tile([ 10000000., 10000000], s.n_mid * s.n_down)
			cW = cDL - cec;

			cV = zeros(s.var['y'], dtype='int8')

			Z = hstack((cF, cUL, cW, cV))

			return matrix(Z)

		else:
			print "You have not supplied an available scenario."

	def availability_builder(s):
		n_rows = s.n_feedstocks*s.n_up;
		#Y
		gy = zeros((n_rows, s.var['y']), dtype='int8');
		#X
		gx = mp.bd(tile(identity(s.n_feedstocks, dtype='int8'), s.n_pathways), s.n_up);
		gx = tile(gx, (1, s.n_mid));
		#W
		gw = zeros((n_rows, s.var['w']), dtype='int8')
		#V
		gv = zeros((n_rows, s.var['y']), dtype='int8')
		#G
		g = hstack((gy, gx, gw, gv))

		return sparse(g.tolist()).trans();

	def availability_data(s):
		
		return ndarray.flatten(s.b_data)[newaxis].T

	def capacity_builder(s):
		n_rows = s.n_mid;
		#Y
		gy = identity(n_rows, dtype='int8')*-s.r_cap;
		#X
		gx = mp.bd(array([ones(s.cnv_block.shape[1]*s.n_up)]), s.n_mid);
		#W
		gw = zeros((n_rows, s.var['w']), dtype='int8')
		#V
		gv = zeros((n_rows, s.var['y']), dtype='int8')
		#G
		g = hstack((gy, gx, gw, gv))

		return sparse(g.tolist()).trans();

	def capacity_data(s):

		return zeros(s.n_mid)[newaxis].T

	def demand_builder(s):
		n_rows = s.n_fuels*s.n_down;
		# Y,X
		shape = (n_rows, s.var['y'] + s.var['x'] ); 
		gyx = zeros(shape, dtype='int8');
		# W, All shipments to nodes must be less than demand
		gw = identity(n_rows, dtype='int8');
		gw = tile(gw, (1, s.n_mid));
		#V
		gv = zeros((n_rows, s.var['y']), dtype='int8')
		#G
		g = hstack((gyx, gw, gv));
		assert g.shape[1] 

		return sparse(g.tolist()).trans();

	def demand_data(s):
		
		return ndarray.flatten(s.d_data)[newaxis].T

	def conversion_builder(s):
		n_rows = s.cnv_block.shape[0] * s.n_mid;
		# Y
		gy = zeros((n_rows, s.var['y']), dtype='int8') 
		# X 
		gx = tile(s.cnv_block, (1, s.n_up));
		gx = mp.bd(gx, s.n_mid)*-1;
		# W
		gw = identity(s.n_fuels, dtype='int8')
		gw = tile(gw, (1, s.n_down));
		gw = mp.bd(gw, s.n_mid)
		#V
		gv = zeros((n_rows, s.var['y']),dtype='int8')
		#G
		g = hstack((gy, gx, gw, gv))

		return sparse(g.tolist()).trans();

	def conversion_data(s):

		return zeros(s.cnv_block.shape[0] * s.n_mid)[newaxis].T

	def positives_builder(s):
		n_rows = s.var['x'] + s.var['w'];
		#Y
		gy = matrix(0, (n_rows, s.var['y']))
		#XW
		gxw = spmatrix(-1, range(n_rows), range(n_rows))
		#V
		gv = matrix(0, (n_rows, s.var['y']))
		
		return sparse([[gy],[gxw],[gv]])

	def positives_data(s):

		return zeros(s.var['x'] + s.var['w'])[newaxis].T

	def max_units_builder(s):
		n_rows = s.var['y'];
		#Y
		gy = identity(s.n_mid, dtype='int8')
		#XW
		gxw = zeros((n_rows, s.var['x'] + s.var['w']))
		#V
		gv = identity(s.n_mid)*-s.m_units;
		#G
		g = hstack((gy, gxw, gv))

		return sparse(g.tolist()).trans();

	def max_units_data(s):

		return zeros(s.var['y'])[newaxis].T

	def threshold_builder(s):
		n_rows = s.var['y'];
		#Y
		gy = identity(s.n_mid, dtype='int8')*-1;
		#XW
		gxw = zeros((n_rows, s.var['x'] + s.var['w']))
		#V
		gv = identity(s.n_mid, dtype='int8');
		#G
		g = hstack((gy, gxw, gv))

		return sparse(g.tolist()).trans();

	def threshold_data(s):

		return zeros(s.var['y'])[newaxis].T

	def relaxed_threshold_builder(s):
		n_rows = s.var['y'];
		#Y
		gy = identity(s.n_mid, dtype='int8');
		#XW
		gxwv = zeros((n_rows, s.var['x'] + s.var['w'] + s.var['v']))

		#G
		g = hstack((gy, gxwv))

		return sparse(g.tolist()).trans();

	def combo_pathways_builder(s):
		n_rows = s.n_up*s.n_mid*s.n_feedstocks;
		#Y
		gy = mp.szero(n_rows, s.var['y']);
		#XW
		gx = mp.bd_sparse(array([[1,0,0,0,0,0,-1,0,0,0,0,0],[0,1,0,0,0,0,0,-1,0,0,0,0],[0,0,1,0,0,0,0,0,-1,0,0,0]]), s.n_up*s.n_mid);
		#V
		gwv = mp.szero(n_rows, s.var['w'] + s.var['v']);
		#G
		g = mp.shstack((gy, gx, gwv))
		
		return mp.scipy_sparse_to_spmatrix(g);


	def combo_pathways_data(s):
		n_rows = s.n_up*s.n_mid*s.n_feedstocks;

		return zeros(n_rows)[newaxis].T


	def predict(s, method='MILP'):

		# Integer-programming solution::True
		s.method = method;

		# OBJECTIVE #############################################################################################
		# Set Up Objective Function
		Z = s.obective_builder()

		# SUBJECT TO  ###########################################################################################
		# FIRST CONSTRAINT - Cannot ship more biomass than you can in a county ##################################
		g1 = s.availability_builder()
		h1 = s.availability_data()
		
		# SECOND CONSTRAINT - Cannot accept more biomass than a refinery can process ############################
		g2 = s.capacity_builder()
		h2 = s.capacity_data()

		# THIRD CONSTRAINT - Cannot ship more fuel(tons) than there is demand for fuel (tons) ###################
		g3 = s.demand_builder()
		h3 = s.demand_data()

		# FOURTH CONSTRAINT - The amount of fuel a county recieves is equal to what is produced at a refinery.#
		g4 = s.conversion_builder()
		h4 = s.conversion_data()

		# FIFTH CONSTRAINT - All xij and wjk must be greater than zero ###################################################
		g5 = s.positives_builder()
		h5 = s.positives_data()

		# SIXTH CONSTRAINT - The number of refineries must be less than the maximum allowable refineries ######
		# y_j <= M_j*V_j
		#y_j - M_j*V_j <= 0
		g6 = s.max_units_builder()
		h6 = s.max_units_data()
		
		# SEVENTH CONSTRAINT - The number of refineries is zero OR above some threshold value #####################
		# y_j >= k * V_j
		# k * V_j - y_j <= 0
		g7 = s.threshold_builder();
		h7 = s.threshold_data();

		# EIGTH CONSTRAINT - Pyrolysis produces two fuels at once. Force the pyrolysis feedstocks decision variables to be equal. 
		g8 = s.combo_pathways_builder()
		h8 = s.combo_pathways_data()


		# FORM G*x <= h  ########################################################################################
		# Use all columns so set trimmed columns to False
		s.trimmed_cols = False

		# Run optmization without constraint on objective.
		G = cvxopt.sparse([g1,g2,g3,g5,g6,g7])
		g1, g2, g3, g5, g6, g7 = None, None, None, None, None, None

		h = matrix(vstack((h1,h2,h3,h5,h6,h7)))
		h1, h2, h3, h5, h6, h7 = None, None, None, None, None, None

		A = cvxopt.sparse([g4, g8])
		b = matrix(vstack((h4, h8)))


		#Solve
		s.solution = s.solver(Z, G, h, A=A, b=b);
		s.model = {'Z': Z, 'G': G, 'h': h};

		# Log model results
		s.logging.info('%i kg CO2,e change from baseline.' % s.solution['total'])

	def solver(s, Z, G, h, A=None, b=None):
		"""
	    Uses the integer linear program solver ilp from glpk:

	    (status, x) = ilp(c, G, h, A, b, I, B)

	        minimize    c'*x
	        subject to  G*x <= h
	                    A*x = b
	                    x[k] is integer for k in I
	                    x[k] is binary for k in B

	    c            nx1 dense 'd' matrix with n>=1
	    G            mxn dense or sparse 'd' matrix with m>=1
	    h            mx1 dense 'd' matrix
	    A            pxn dense or sparse 'd' matrix with p>=0
	    b            px1 dense 'd' matrix
	    I            set of indices of integer variables
	    B            set of indices of binary variables
	    """

		(rows, cols) = G.size

		if A is None or b is None:
			# SET OPTIMIZATION PARAMETERS
			(A, b) = (matrix(1., (0,cols)), matrix(1., (0,1)))
		
		if s.method == 'IP':
			if (s.max_refineries == 1):
				# Binary
				(I,B)=(set(), set(range(s.n_mid)))
				print 'BINARY CONSTRAINTS'
			else:
				# Mixed Integer
				(B,I)=(set(range(cols - s.n_mid, cols)), set(range(s.n_mid)))
				print 'INTEGER CONSTRAINTS'

			#INTEGER SOLUTION
			(status, c)=cvxopt.glpk.ilp(Z,G,h,A,b,I,B)
		elif s.method == 'MILP':
			#RELAXATION with binary
			(I,B)=(set(), set(range(cols - s.n_mid, cols)))
			(status, c)=cvxopt.glpk.ilp(Z,G,h,A,b,I,B)
		else:
			#RELAXATION of binary
			(status, c)=cvxopt.glpk.ilp(Z,G,h,A,b)

		return {'set': array(c).T[0], 'total': int((c.T * Z)[0])}

	def save(s):
		savetxt('runs/solution.csv', s.solution['set'], delimiter=',')
		savetxt('runs/Z.csv', matrix(s.model['Z']), delimiter=',')
		#savetxt('runs/G.csv', matrix(s.model['G']), delimiter=',')
		#savetxt('runs/h.csv', matrix(s.model['h']), delimiter=',')


