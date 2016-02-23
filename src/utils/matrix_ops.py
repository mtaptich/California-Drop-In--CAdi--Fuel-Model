import numpy as np
from cvxopt import matrix, spmatrix
from scipy import sparse


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

def scipy_sparse_to_spmatrix(A):
    coo = A.tocoo()
    SP = spmatrix(coo.data.tolist(), coo.row.tolist(), coo.col.tolist(), size=A.shape)
    return SP

def shstack(_tuple):
	return sparse.hstack(_tuple)

def szero(M,N):
	return sparse.coo_matrix(np.zeros((M,N)))

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
		try:
			G = np.vstack((G, zero_offset(array, n, row)))
		except:
			G = zero_offset(array, n, 1) 
	return G

def bd_sparse(array, n):
	"""
	Block Diagonal:
	Similar to np.diagonal but instead creates a diagonal of arrays in a zero matrix. 
	"""
	for row in range(1, n+1):
		try:
			G = sparse.vstack((G, sparse.csr_matrix(zero_offset(array, n, row))))
		except:
			G = sparse.csr_matrix(zero_offset(array, n, 1) )
	return G

if __name__ == "__main__":
	pass

