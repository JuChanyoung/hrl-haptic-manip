
#######################################
# used with QP controller
# install python-openopt Ubuntu package 
# to use openopt module
import openopt as pp
import regular_polygons as rp
import subdivide_sphere as ss

import itertools as it

import numpy as np, math


# Add an additional quadratic term that attempts to
# minimize the magnitude of the delta_phi vector. This is
# comparable to minimizing the jerk, since delta_phi is
# proportional to the change in the joint torque at each
# time step.
#
# 0.5 * delta_phi.T * 2.0 * H * delta_phi = 
# delta_phi.T * H * delta_phi =
# delta_phi.T * (D2 + alpha * K_j.T * K_j) * delta_phi =
# delta_phi.T * (D2 * delta_phi + alpha * K_j.T K_j * delta_phi) =
# (delta_phi.T * D2 * delta_phi) + (alpha * delta_phi.T * K_j.T * K_j * delta_phi)
#
# The (alpha * delta_phi.T * K_j.T * K_j * delta_phi) term
# makes the optimization want to reduce the magnitude of
# additional torque applied to the joints prior to the
# joint angles changing and achieving static equilibrium
# (K_j * delta_phi)
#
# Alternatively, we could optimize with change in torque
# expected by our model after static equilibrium is
# achieved:
#
#           delta_tau = K_j * (delta_phi - delta_theta)
# and
#           delta_theta = P2 * K_j * delta_phi
# so 
#           delta_tau = K_j * (delta_phi - P2 * K_j * delta_phi)
#           delta_tau = K_j * (I - P2 * K_j) delta_phi
#           delta_tau = (K_j - K_j * P2 * K_j) delta_phi
# which would imply we'd use
#           (K_j - K_j * P2 * K_j).T * (K_j - K_j * P2 * K_j)
#D2 = D2 + (jerk_opt_weight * np.identity(m))
def min_jerk_quadratic_matrix(jerk_opt_weight, K_j):
    return (jerk_opt_weight * K_j.T * K_j)

# Calculate D2, D3, D4, D5, and D6
def D_matrices(delta_x_g, delta_f_min, K_j, Rc_l, P3, P4_l):
    m = K_j.shape[0]
    n = delta_f_min.shape[0]

    # D_2 = (P_3)^T P_3
    # (this is the matrix for the quadratic term of the cost function)
    # D_2 is size m x m
    D2 = P3.T * P3

    # D_3 = -2 (delta_x_g)^T P_3
    # D_3 is size 1 x m
    D3 = -2.0 * delta_x_g.T * P3

    # D_4 = R_c P_4 K_j
    # D_4 is size n x m = (n x 3n) (3n x m) (m x m)
    # R_ci * P_4i = (1 x 3) (3 x m) = (1 x m)
    # R_ci * P_4i * K_j = (1 x 3) (3 x m) (m x m) = (1 x m)
    D4 = np.matrix(np.zeros((n,m)))
    for row_num, R_ci, P4_i in it.izip(it.count(), Rc_l, P4_l):
        tmp = R_ci * P4_i * K_j
        D4[row_num,:] = tmp[:]

    # D_5 = -D_4
    # D_5 is size n x m
    D5 = -D4

    # D_6 = - delta_f_min
    # D_6 is size n x 1
    D6 = - delta_f_min

    return D2, D3, D4, D5, D6

# Calculate P_0, P_1, P_2, P_3, and P_4
def P_matrices(J_h, K_j, Kc_l, Jc_l):
    m = K_j.shape[0]

    # P_0 = K_c J_c
    # P_0i is size 3 x m
    # P_0 is size 3n x m
    P0_l = [K_ci * J_ci for K_ci, J_ci in it.izip(Kc_l, Jc_l)]

    # P_1 = (J_c)^T K_c J_c            
    # P_1 = (J_c)^T P_0            
    # P_1 is size m x m
    P1 = np.matrix(np.zeros((m,m)))
    for J_ci, P0_i in it.izip(Jc_l, P0_l):
        P1 = P1 + (J_ci.T * P0_i)

    # P_2 = ((J_c)^T K_c J_c + K_j)^-1
    # P_2 = (P_1 + K_j)^-1
    # P_2 is size m x m
    tmp = P1 + K_j
    #P2 = np.linalg.inv(tmp)
    # Advait changed the inv to a pseudo-inverse with the hope
    # that it will make things a bit stabler (although nothing
    # bad has happened yet -- July 6, 2011.)
    # Advait copied this from epc_skin_old_code.py on July 19
    P2 = np.linalg.pinv(tmp)

    # P_3 = J_h ((J_c)^T K_c J_c + K_j)^-1 K_j
    # P_3 = J_h P_2 K_j
    # P_3 is size 3 x m
    P3 = J_h * P2 * K_j

    # P_4 = K_c J_c ((J_c)^T K_c J_c + K_j)^-1
    # P_4 = P_0 P_2
    # P_4i is size 3 x m
    # P_4 is size 3n x m
    P4_l = [P0_i * P2 for P0_i in P0_l]

    return P0_l, P1, P2, P3, P4_l

# force_idx_l - index of the forces whose magintudes will be
# summed up to compute the cost.
# delta_fg: +ve Scalar (how much to decrease force in the normal direction)
def force_magnitude_cost_matrices(P4_l, K_j, force_idx_l, Rc_l, delta_fg):
    # first writing code to compute the term in the cost function.
    # I will then pull out the matrix which when pre and post
    # multiplied with delta_phi will give the cost that we are
    # interested in. This matrix can then be used by the QP
    # solver.
    #
    #delta_fc_l = [P4_i*K_j*delta_phi for P4_i in P4_l]
    #
    #delta_fc_large_mag = 0.
    #for idx in large_force_idx_l:
    #    d_fc_large = delta_fc_l[idx]
    #    delta_fc_large_mag += (d_fc_large.T * d_fc_large)[0,0]

    delta_fc_mat_l = [P4_i*K_j for P4_i in P4_l]
    # now multiplying each matrix in delta_fc_mat_l with delta_phi
    # will give us delta_fc_l

    quad_m = np.matrix(np.zeros(K_j.shape))
    lin_m = np.matrix(np.zeros(K_j.shape[0]))

    for idx in force_idx_l:
        d_fc_large_mat = delta_fc_mat_l[idx]
        quad_m += d_fc_large_mat.T * d_fc_large_mat
        lin_m += -delta_fg * Rc_l[idx] * d_fc_large_mat

    return quad_m, -2*lin_m


# v - vector of joint angles (or equilibrium angles for Cody)
def joint_limit_bounds(kinematics, v):
    m = v.shape[0]
    min_q, max_q = kinematics.get_joint_limits()
    min_q = (np.matrix(min_q).T)[0:m]
    max_q = (np.matrix(max_q).T)[0:m]

    delta_q_max = max_q - v
    delta_q_min = min_q - v

    return delta_q_min, delta_q_max


def convert_to_qp(J_h, Jc_l, K_j, Kc_l, Rc_l, delta_f_min,
                  delta_f_max, phi_curr, delta_x_g, f_n, q,
                  kinematics, jerk_opt_weight, max_force_mag):
    P0_l, P1, P2, P3, P4_l = P_matrices(J_h, K_j, Kc_l, Jc_l)
    D2, D3, D4, D5, D6 = D_matrices(delta_x_g, delta_f_min, K_j, Rc_l,
                                    P3, P4_l)
    m = K_j.shape[0]
    theta_curr = (np.matrix(q).T)[0:m]
    delta_theta_min, delta_theta_max = joint_limit_bounds(kinematics, theta_curr)
    D7 = P2 * K_j

    K_j_t = K_j
    min_jerk_mat = min_jerk_quadratic_matrix(jerk_opt_weight, K_j_t)

    cost_quadratic_matrices = [1. * D2, 1. * min_jerk_mat]
    cost_linear_matrices = [1. * D3]

    # if some contact forces are above the allowed pushing
    # force, add quadratic terms to the cost function to
    # decrease this force.
    over_max = f_n.A1 > max_force_mag
    if over_max.any():
        # at least one of the contact forces is over the maximum allowed
        idx_l = np.where(over_max)[0].tolist()
        weight = 1.
        qmat, lmat = force_magnitude_cost_matrices(P4_l, K_j, idx_l,
                                                   Rc_l, 0.2)
        cost_quadratic_matrices.append(qmat*weight)
        cost_linear_matrices.append(lmat*weight)

    constraint_matrices = [D4, D5]
    constraint_vectors = [delta_f_max, D6]

    # adding explicit contraint for joint limits.
    constraint_matrices.append(D7)
    constraint_vectors.append(delta_theta_max)
    constraint_matrices.append(-D7)
    constraint_vectors.append(-delta_theta_min)

    #delta_phi_min, delta_phi_max = self.delta_phi_bounds(phi_curr)
    delta_phi_min, delta_phi_max = joint_limit_bounds(kinematics, phi_curr)
    
    lb = delta_phi_min
    ub = delta_phi_max

    # HACK by Advait to allow JEP to go outside joint limits for
    # software simulation with 3 links.
    if kinematics.n_jts == 3:
        lb = lb * 10.
        ub = ub * 10.

    return cost_quadratic_matrices, cost_linear_matrices, \
           constraint_matrices, constraint_vectors, lb, ub



## Set up and solve QP 
##
# In [3]: pp.QP?
# Docstring:
#     QP: constructor for Quadratic Problem assignment
#     1/2 x' H x  + f' x -> min
#     subjected to
#     A x <= b
#     Aeq x = beq
#     lb <= x <= ub
#
#     Examples of valid calls:
#     p = QP(H, f, <params as kwargs>)
#     p = QP(numpy.ones((3,3)), f=numpy.array([1,2,4]), <params as kwargs>)
#     p = QP(f=range(8)+15, H = numpy.diag(numpy.ones(8)), <params as kwargs>)
#     p = QP(H, f, A=A, Aeq=Aeq, b=b, beq=beq, lb=lb, ub=ub, <other params as kwargs>)
#     See also: /examples/qp_*.py
#
#     INPUT:
#     H: size n x n matrix, symmetric, positive-definite
#     f: vector of length n
#     lb, ub: vectors of length n, some coords may be +/- inf
#     A: size m1 x n matrix, subjected to A * x <= b
#     Aeq: size m2 x n matrix, subjected to Aeq * x = beq
#     b, beq: vectors of lengths m1, m2
#     Alternatively to A/Aeq you can use Awhole matrix as it's described 
#     in LP documentation (or both A, Aeq, Awhole)
def solve_qp(cost_quadratic_matrices, cost_linear_matrices, 
             constraint_matrices, constraint_vectors, lb, ub,
             debug_qp):
    total = np.zeros(cost_quadratic_matrices[0].shape)
    for cqm in cost_quadratic_matrices:
        total = total + cqm
    H = 2.0 * total
    # H is size m x m

    total = np.zeros(cost_linear_matrices[0].shape)
    for clm in cost_linear_matrices:
        total = total + clm
    f = total.T
    # f is size 1 x m

    A = np.concatenate(constraint_matrices)
    b = np.concatenate(constraint_vectors)

    # iprint: do text output each iprint-th iteration You can
    # use iprint = 0 for final output only or iprint < 0 to
    # omit whole output In future warnings are intended to be
    # shown if iprint >= -1.  
    if debug_qp: 
        iprint_val = 1
    else:
        iprint_val = -1

    # Result structure
    # http://openopt.org/OOFrameworkDoc
    # r = p.solve(nameOfSolver) 
    # >>> dir(r)
    # ['__doc__', '__module__', 'advanced', 'elapsed',
    # 'evals', 'ff', 'isFeasible', 'istop', 'iterValues',
    # 'msg', 'rf', 'solverInfo', 'stopcase', 'xf']
    #

    opt_error = False
    feasible = None
    delta_phi_zero = np.matrix(np.zeros(lb.shape))
    # this is Marc's fix for some cases in simulation when the arm
    # gets stuck and keeps setting delta_phi=0. Advait also saw
    # this problem in one case (Aug 23, 2011), and copied the next
    # line from the forked_simulation_files folder.
    #delta_phi_zero = np.matrix(np.random.normal(0.0, 0.003, lb.shape))
    #delta_phi_zero = np.matrix(np.random.normal(0.0, 0.01, lb.shape))

    try:
        qp = pp.QP(H, f, A=A, b=b, lb=lb, ub=ub)
        qp.solve('cvxopt_qp', iprint = iprint_val)
        delta_phi_opt = np.matrix(qp.xf).T
        val_opt = qp.ff
        feasible = qp.isFeasible

        if not feasible:
            print '====================================='
            print 'QP did not find a feasible solution.'
            print '====================================='
            opt_error = True
            delta_phi_opt = delta_phi_zero

        if np.isnan(delta_phi_opt.sum()):
            print '*****************************************************'
            print 'ERROR: QP FAILED TO FIND A SOLUTION AND RETURNED NaN(s)'
            print '*****************************************************'

        if qp.stopcase == 0:
            print 'maxIter, maxFuncEvals, maxTime or maxCPUTime have been exceeded, or the situation is unclear somehow else'
    except ValueError as inst:
        opt_error = True
        print type(inst)     # the exception instance
        print inst.args      # arguments stored in .args
        print inst           # __str__ allows args to printed directly
        print "ValueError raised by OpenOpt and/or CVXOPT"
        print "Setting new equilibrium angles to be same as old."
        print "delta_phi = 0"
        print "phi[t+1] = phi[t]"
        delta_phi_opt = delta_phi_zero
        val_opt = np.nan

    return delta_phi_opt, opt_error, feasible






#---------- OLD functions: probably WON'T work anymore ----------------

## Returns unit length vectors, each of which corresponds with
## a face of a polytope.
##
## For now, use a regular polygon to ensure that the
## expected change is not too high. This will likely result
## in a lack of a feasible solution in some situations,
## such as when a very high force is encountered.
#def polytope_faces(self, n_faces):
#    if n_faces <= 6:
#        polytope_faces = rp.cube_faces #6 sided polytope
#    elif n_faces <= 8:
#        polytope_faces = rp.octahedron_faces #6 sided polytope
#    elif n_faces <= 12:
#        polytope_faces = rp.dodecahedron_faces #12 sided polytope
#    elif n_faces <= 20:
#        polytope_faces = rp.icosahedron_faces #20 sided polytope 
#    else:
#        # should precompute this a single time...
#        polytope_faces = None
#        for num_faces, faces in self.spheres:
#            if (n_faces <= num_faces) and (polytope_faces is None):
#                polytope_faces = faces
#        if polytope_faces is None:
#            # requested number of sides is greater than our
#            # biggest tessellation, so use the biggest
#            num_faces, faces = self.spheres[-1]
#            polytope_faces = faces
#
#    num_faces, tmp = polytope_faces.shape
#
#    return polytope_faces, num_faces




