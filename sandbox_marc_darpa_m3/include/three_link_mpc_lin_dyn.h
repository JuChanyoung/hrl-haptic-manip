/* Produced by CVXGEN, 2013-08-02 15:52:24 -0400.  */
/* CVXGEN is Copyright (C) 2006-2012 Jacob Mattingley, jem@cvxgen.com. */
/* The code in this file is Copyright (C) 2006-2012 Jacob Mattingley. */
/* CVXGEN, or solvers produced by CVXGEN, cannot be used for commercial */
/* applications without prior written permission from Jacob Mattingley. */

/* Filename: solver.h. */
/* Description: Header file with relevant definitions. */
#ifndef SOLVER_H
#define SOLVER_H
/* Uncomment the next line to remove all library dependencies. */
/*#define ZERO_LIBRARY_MODE */
#ifdef MATLAB_MEX_FILE
/* Matlab functions. MATLAB_MEX_FILE will be defined by the mex compiler. */
/* If you are not using the mex compiler, this functionality will not intrude, */
/* as it will be completely disabled at compile-time. */
#include "mex.h"
#else
#ifndef ZERO_LIBRARY_MODE
#include <stdio.h>
#endif
#endif
/* Space must be allocated somewhere (testsolver.c, csolve.c or your own */
/* program) for the global variables vars, params, work and settings. */
/* At the bottom of this file, they are externed. */
#ifndef ZERO_LIBRARY_MODE
#include <math.h>
#define pm(A, m, n) printmatrix(#A, A, m, n, 1)
#endif
typedef struct Params_t {
  double alpha[1];
  double delta_x_d[2];
  double J[6];
  double q_0[3];
  double mu[1];
  double beta[1];
  double n_K_J_all[36];
  double n_Kd_J_all[36];
  double delta_f_max[12];
  double zeta[1];
  double delta_rate_f_max[12];
  double A_tl[9];
  double qd_0[3];
  double A_tr[9];
  double B_t1[9];
  double q_des_cur_0[3];
  double B_t2[9];
  double tau_cont_sum_0[3];
  double B_t3[9];
  double A_bl[9];
  double A_br[9];
  double B_b1[9];
  double B_b2[9];
  double B_b3[9];
  double q_min[3];
  double q_max[3];
  double u_max[3];
  double mass[9];
  double tau_max_delta_t[3];
  double *q[1];
  double *qd[1];
  double *q_des_cur[1];
  double *tau_cont_sum[1];
} Params;
typedef struct Vars_t {
  double *t_01; /* 2 rows. */
  double *u_0; /* 3 rows. */
  double *u_1; /* 3 rows. */
  double *u_2; /* 3 rows. */
  double *u_3; /* 3 rows. */
  double *u_4; /* 3 rows. */
  double *t_02; /* 12 rows. */
  double *t_03; /* 12 rows. */
  double *t_04; /* 12 rows. */
  double *t_05; /* 12 rows. */
  double *t_06; /* 12 rows. */
  double *t_07; /* 12 rows. */
  double *t_08; /* 12 rows. */
  double *t_09; /* 12 rows. */
  double *t_10; /* 12 rows. */
  double *t_11; /* 12 rows. */
  double *t_12; /* 12 rows. */
  double *t_13; /* 12 rows. */
  double *t_14; /* 12 rows. */
  double *t_15; /* 12 rows. */
  double *t_16; /* 12 rows. */
  double *q_1; /* 3 rows. */
  double *qd_1; /* 3 rows. */
  double *q_2; /* 3 rows. */
  double *qd_2; /* 3 rows. */
  double *q_3; /* 3 rows. */
  double *qd_3; /* 3 rows. */
  double *q_4; /* 3 rows. */
  double *qd_4; /* 3 rows. */
  double *q_5; /* 3 rows. */
  double *qd_5; /* 3 rows. */
  double *t_17; /* 3 rows. */
  double *t_18; /* 3 rows. */
  double *t_19; /* 3 rows. */
  double *t_20; /* 3 rows. */
  double *t_21; /* 3 rows. */
  double *t_22; /* 3 rows. */
  double *t_23; /* 3 rows. */
  double *t_24; /* 3 rows. */
  double *t_25; /* 3 rows. */
  double *t_26; /* 3 rows. */
  double *q_des_cur_1; /* 3 rows. */
  double *q_des_cur_2; /* 3 rows. */
  double *q_des_cur_3; /* 3 rows. */
  double *q_des_cur_4; /* 3 rows. */
  double *q_des_cur_5; /* 3 rows. */
  double *q[6];
  double *u[5];
  double *qd[6];
  double *q_des_cur[6];
} Vars;
typedef struct Workspace_t {
  double h[480];
  double s_inv[480];
  double s_inv_z[480];
  double b[47];
  double q[272];
  double rhs[1279];
  double x[1279];
  double *s;
  double *z;
  double *y;
  double lhs_aff[1279];
  double lhs_cc[1279];
  double buffer[1279];
  double buffer2[1279];
  double KKT[3811];
  double L[3581];
  double d[1279];
  double v[1279];
  double d_inv[1279];
  double gap;
  double optval;
  double ineq_resid_squared;
  double eq_resid_squared;
  double block_33[1];
  /* Pre-op symbols. */
  int converged;
} Workspace;
typedef struct Settings_t {
  double resid_tol;
  double eps;
  int max_iters;
  int refine_steps;
  int better_start;
  /* Better start obviates the need for s_init and z_init. */
  double s_init;
  double z_init;
  int verbose;
  /* Show extra details of the iterative refinement steps. */
  int verbose_refinement;
  int debug;
  /* For regularization. Minimum value of abs(D_ii) in the kkt D factor. */
  double kkt_reg;
} Settings;
extern Vars vars;
extern Params params;
extern Workspace work;
extern Settings settings;
/* Function definitions in ldl.c: */
void ldl_solve(double *target, double *var);
void ldl_factor(void);
double check_factorization(void);
void matrix_multiply(double *result, double *source);
double check_residual(double *target, double *multiplicand);
void fill_KKT(void);

/* Function definitions in matrix_support.c: */
void multbymA(double *lhs, double *rhs);
void multbymAT(double *lhs, double *rhs);
void multbymG(double *lhs, double *rhs);
void multbymGT(double *lhs, double *rhs);
void multbyP(double *lhs, double *rhs);
void fillq(void);
void fillh(void);
void fillb(void);
void pre_ops(void);

/* Function definitions in solver.c: */
double eval_gap(void);
void set_defaults(void);
void setup_pointers(void);
void setup_indexed_params(void);
void setup_indexed_optvars(void);
void setup_indexing(void);
void set_start(void);
double eval_objv(void);
void fillrhs_aff(void);
void fillrhs_cc(void);
void refine(double *target, double *var);
double calc_ineq_resid_squared(void);
double calc_eq_resid_squared(void);
void better_start(void);
void fillrhs_start(void);
long solve(void);

/* Function definitions in testsolver.c: */
int main(int argc, char **argv);
void load_default_data(void);

/* Function definitions in util.c: */
void tic(void);
float toc(void);
float tocq(void);
void printmatrix(char *name, double *A, int m, int n, int sparse);
double unif(double lower, double upper);
float ran1(long*idum, int reset);
float randn_internal(long *idum, int reset);
double randn(void);
void reset_rand(void);

#endif
