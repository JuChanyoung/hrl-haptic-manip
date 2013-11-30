%MDL_DARCI Create model of Cody manipulator from Meka
%
%      mdl_darci_no_motors

clear L
%             th    d       a         alpha   sigma  offset
L(1) = Link([ 0     -0.18465 0         pi/2    0        -pi/2], 'modified');
L(2) = Link([ 0 	0.      0	      pi/2    0         pi/2], 'modified');
L(3) = Link([ 0     0.27857	-0.03175   pi/2    0         pi/2], 'modified');
L(4) = Link([ 0     0       -0.00502  pi/2    0         0   ], 'modified');
L(5) = Link([ 0     0.27747 0         -pi/2   0         0   ], 'modified');
L(6) = Link([ 0     0       0         pi/2    0         pi/2], 'modified');
L(7) = Link([ 0     0       0         pi/2    0         pi/2], 'modified');
%L(8) = Link([ 0    0.04414  0         pi/2    0         0], 'modified');
            
% L(1) = Link([ 0    0.18465 0         pi/2    0         pi/2], 'standard');
% L(2) = Link([ 0 	0.      0.03175   pi/2    0         pi/2], 'standard');
% L(3) = Link([ 0     0.27857	0.00502  -pi/2    0        -pi/2], 'standard');
% L(4) = Link([ 0     0       0         pi/2    0         0   ], 'standard');
% L(5) = Link([ 0     0.27747 0        -pi/2   0         0   ], 'standard');
% L(6) = Link([ 0     0       0        -pi/2    0         pi/2], 'standard');
% L(7) = Link([ 0     0       -0.04414         0       0         0   ], 'standard');

L(1).m = 1.9872*0.8;
L(2).m = 0.5575*1.2;
L(3).m = 2.220*1.2;
L(4).m = 0.22*0.8;
L(5).m = 1.7*0.7;
L(6).m = 0.212*1.3;
L(7).m = 0.084*1.2;
%L(8).m = 0.838;
% 
L(1).r = [0, -0.0094, 0.0240]
L(2).r = [-0.0264, -0.0431, -0.0008]
L(3).r = [0.0080, 0., -0.0877]
L(4).r = [0.0, 0.02573092, 0.00080947]
L(5).r = [0.00193729, 0.00046171, -0.13853286]
L(6).r = [8.7719999999999994e-05, -0.0018379500000000001, -0.0018201000000000001]
L(7).r = [3.0e-05, -0.01092, 0.00292]
% L(8).r = [0.00286004, 0.00206754, 0.06242752]

%L(1).r = [0.0, 0., 0.0];
%L(2).r = [0, 0, 0];
%L(3).r = [0, 0, 0.];
% L(4).r = [0, 0, 0.];
% L(5).r = [0, 0, 0.];
% L(6).r = [0, 0, 0.];
% L(7).r = [0, 0, 0.];


% L(1).I = [0, 0, 0.0, 0, 0, 0];
% L(2).I = [0, 0, 0.0, 0, 0, 0];
% L(3).I = [0, 0, 0.0, 0, 0, 0];
% L(4).I = [0, 0, 0.0, 0, 0, 0];
% L(5).I = [0, 0, 0.0, 0, 0, 0];
% L(6).I = [0, 0, 0.0, 0, 0, 0];
% L(7).I = [0, 0, 0.0, 0, 0, 0];

L(1).I = [0.00681123,  0.004616, 0.003267,  2.79e-06,   0.0001518,  -9.60e-07]
L(2).I = [0.00195358,  0.00121948, 0.0021736, -0.00077554, 4.74e-06, 4.39e-06]
L(3).I = [0.02949661, 0.02983326, 0.00244235, 8.636e-05, -0.00013024, -0.0024288]
L(4).I = [0.00062344, 0.00042457, 0.00038623, 2.0e-08, 1.768e-05, 0.0]
L(5).I = [0.03130809, 0.03135827, 0.00120798, -2.89e-06, -3.896e-05, -0.00089153]
L(6).I = [0.00011597, 0.00011378, 7.497e-05, -5.0e-08, -1.2e-07, 4.0e-08]
L(7).I = [9.428e-05, 6.133e-05, 5.054e-05, 2.0e-08, -7.4e-07, 0.0]
%L(8).I = [0.00484971, 0.00507558, 0.00080672, -3.507e-05, 9.2089e-05, 7.626e-05]


L(1).Jm =  0.;
L(2).Jm =  0.;
L(3).Jm =  0.;
L(4).Jm =  0.;
L(5).Jm =  0.;
L(6).Jm =  0.;
L(7).Jm =  0.;
%L(8).Jm =  0.;

L(1).G =  0.;
L(2).G =  0.;
L(3).G =  0.;
L(4).G =  0.;
L(5).G =  0.;
L(6).G =  0.;
L(7).G =  0.;
%L(8).G =  0.;

% viscous friction (motor referenced)
L(1).B =   0.;
L(2).B =   0.;
L(3).B =   0.;
L(4).B =   0.;
L(5).B =   0.;
L(6).B =   0.;
L(7).B =   0.;
%L(8).B =   0.;

darci_left_off = SerialLink(L, 'name', 'darci left arm', ...
    'manufacturer', 'Meka', 'comment', 'params from Meka');

darci_left_off.gravity = [0, 0, 0]';

darci_left_off.tool = [1, 0, 0, 0;
                    0, 0, -1, -0.153;
                    0, 1, 0, 0;
                    0, 0, 0, 1];

% darci.base = [1 0 0 0;
%               0 0 -1 0;
%               0 -1 0 0;
%               0 0 0 1];

%
% some useful poses
%
qz = [0 0 0 0 0 0 0]; % zero angles, L shaped pose
%qz = [0 0 0 0 0 0 0]; % zero angles, L shaped pose
qn = [0 pi/2 0 0 0 0 0]; % zero angles, L shaped pose
q1 = ones(1,7)*0.1
q2 = ones(1,7)*0.3
%qn = [0 pi/2 0 0 0 0 0]; % zero angles, L shaped pose
%qr = [0 pi/2 -pi/2 0 0 0]; % ready pose, arm up
%qs = [0 0 -pi/2 0 0 0];
%qn=[0 pi/4 pi 0 pi/4  0];


clear L