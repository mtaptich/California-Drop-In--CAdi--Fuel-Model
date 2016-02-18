import numpy as np

def build_j_in_J_for_all_I(i,j):
	for row in range(i):
		a = np.zeros((j,i))
		a[:,row]+=1
		a = a.flatten()
		try:
			out = np.vstack((out,a))
		except:
			out = a
	return out

def build_i_in_I_for_all_J(i,j):
	for row in range(j):
		a = np.zeros((j,i))
		a[row,:]+=1
		a = a.flatten()
		try:
			out = np.vstack((out,a))
		except:
			out = a
	return out

def zero_offset(array,repeats, position):
	"""
	Offsets an array in an zero matrix. 
	"""
	a = np.zeros(array.shape);
	return np.hstack((np.repeat(a, position - 1, axis=1), array, np.repeat(a, repeats - position , axis=1)))

def bd(array, n):
	"""
	Block Diagonal:
	Similar to np.diagonal but instead creates a diagonal of arrays in a zero matrix. 
	"""
	for row in range(1, n+1):
		a = np.zeros(array.shape)
		try:
			G = np.vstack((G, zero_offset(array, n, row)))
		except:
			G = zero_offset(array, n, 1) 
	return G