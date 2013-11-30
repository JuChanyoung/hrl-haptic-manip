## @package hrl_haptic_mpc
# 
# @author Jeff Hawke jhawke@gatech.edu
# @version 0.1
# @copyright Simplified BSD Licence

#
# Copyright (c) 2009, Georgia Tech Research Corporation
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Georgia Tech Research Corporation nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY GEORGIA TECH RESEARCH CORPORATION ''AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL GEORGIA TECH BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

# Author: Advait Jain

import numpy as np, math

import roslib; roslib.load_manifest('hrl_tactile_controller')
import rospy
from equilibrium_point_control.hrl_arm import HRLArmKinematics

import tf

import PyKDL as kdl

import hrl_lib.transforms as tr
import hrl_lib.kdl_utils as ku

#from urdf_parser_py.urdf import URDF
#from pykdl_utils.kdl_parser import kdl_tree_from_urdf_model 

## Provides interfaces to calculate FK/IK for the PR2 arm using KDL.
# @author Advait Jain 
class PR2ArmKinematics(HRLArmKinematics):
    def __init__(self, arm):
        if arm != 'r' and arm != 'l':
            raise RuntimeError('Unimplemented arm: must be "r" or "l"')

        HRLArmKinematics.__init__(self, n_jts = 7)

        # create joint limit dicts
        if arm == 'r':
            min_lim = np.radians(np.array([-109., -24., -220., -132., -180., -120, -180.]))
            max_lim = np.radians(np.array([26., 68., 41., 0.01, 180., 0.01, 180.]))

            #min_lim = np.radians(np.array([-109., -24, -220, -132, -np.inf, -120, -np.inf]))
            #max_lim = np.radians(np.array([26., 68, 41, 0, np.inf, 0, np.inf]))
        elif arm == 'l':
            #min_lim = np.radians(np.array([-26., -10., 80., -132, -10., -120., -180.]))
            #max_lim = np.radians(np.array([109., 10., 100., 0.01, 10., 0.01, 180.]))

            min_lim = np.radians(np.array([-26., -24., -41., -132, -270., -120., -180.]))
            max_lim = np.radians(np.array([109., 68., 220., 0.01, 270., 0.01, 180.]))

        self.joint_lim_dict = {}
        self.joint_lim_dict['max'] = max_lim
        self.joint_lim_dict['min'] = min_lim

        # define tooltips from the /r_gripper_palm_link origin
        nominal_gripper_length = 0.2
        self.use_shaver45 = False#True
        self.shaver45_x = 0.08438
        self.shaver45_y = -0.04738
        self.shaver45_z = 0.0
        self.shaver45_rx = 0.0#np.radians(45.0)
        self.shaver45_ry = 0.0#np.radians(45.0)
        self.shaver45_rz = np.radians(-45.0)

        self.setup_kdl_chains(arm, nominal_gripper_length)

        self.arm_type = 'real' # for epc_skin_math

        self.tooltip_x = 0.0
        self.tooltip_y = 0.0
        self.tooltip_z = 0.0

        self.set_tooltip(np.matrix([self.tooltip_x, self.tooltip_y, self.tooltip_z]).T)

    def create_chain_from_urdf(self, base_link='torso_lift_link',
                                     end_link='l_gripper_tool_frame',
                                     urdf_file=None):
        self.arm_base_offset_from_torso_lift_link = np.matrix([0., 0. , 0.]).T
        if urdf_file is None:
            robot = URDF.load_from_parameter_server(verbose=False)
        else:
            robot = URDF.load_xml_file(urdf_file, verbose=False)
        tree = kdl_tree_from_urdf_model(robot)
        ch = tree.getChain(base_link, end_link)
        print "Ch Joints: %s" %ch.getNrOfJoints()
        print "Ch Segments: %s" %ch.getNrOfSegments()

        #Prune chain of non-jointed segments
        chain  = kdl.Chain()
        for i in xrange(ch.getNrOfSegments()):
            if not ch.getSegment(i).getJoint().getTypeName() == 'None':
                chain.addSegment(ch.getSegment(i)) 
        print "Chain Joints: %s" %chain.getNrOfJoints()
        print "Chain Segments: %s" %chain.getNrOfSegments()
        return chain

    def create_right_chain(self, end_effector_length):
        ch = kdl.Chain()
        self.arm_base_offset_from_torso_lift_link = np.matrix([0., -0.188, 0.]).T
        # shoulder pan
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotZ),kdl.Frame(kdl.Vector(0.1,0.,0.))))
        # shoulder lift
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotY),kdl.Frame(kdl.Vector(0.,0.,0.))))
        # upper arm roll
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotX),kdl.Frame(kdl.Vector(0.4,0.,0.))))
        # elbox flex
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotY),kdl.Frame(kdl.Vector(0.0,0.,0.))))
        # forearm roll
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotX),kdl.Frame(kdl.Vector(0.321,0.,0.))))
        # wrist flex
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotY),kdl.Frame(kdl.Vector(0.,0.,0.))))
        # wrist roll
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotX),kdl.Frame(kdl.Vector(end_effector_length,0.,0.))))
        print "Chain Joints: %s" %ch.getNrOfJoints()
        print "Chain Segments: %s" %ch.getNrOfSegments()
        return ch

    def create_left_chain(self, end_effector_length):
        ch = kdl.Chain()
        #self.arm_base_offset_from_torso_lift_link = np.matrix([0., 0.188, 0.]).T
        self.arm_base_offset_from_torso_lift_link = np.matrix([0.01274, 0.199, 0.]).T
        # shoulder pan
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotZ),kdl.Frame(kdl.Vector(1.1,0.,0.))))
        # shoulder lift
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotY),kdl.Frame(kdl.Vector(0.,0.,0.))))
        # upper arm roll
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotX),kdl.Frame(kdl.Vector(0.4,0.,0.))))
        # elbox flex
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotY),kdl.Frame(kdl.Vector(0.0,0.,0.))))
        # forearm roll
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotX),kdl.Frame(kdl.Vector(0.321,0.,0.))))
        # wrist flex
        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotY),kdl.Frame(kdl.Vector(0.,0.,0.))))
        # wrist roll
        ee_x = end_effector_length
        ee_y = 0.0
        ee_z = 0.0
        ee_rx = 0.0
        ee_ry = 0.0
        ee_rz = 0.0

        if self.use_shaver45 == True:
          ee_x += self.shaver45_x
          ee_y += self.shaver45_y
          ee_z += self.shaver45_z
          ee_rx += self.shaver45_rx
          ee_ry += self.shaver45_ry
          ee_rz += self.shaver45_rz

        ch.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.RotX),kdl.Frame(kdl.Rotation.RPY(ee_rx, ee_ry, ee_rz), kdl.Vector(ee_x,ee_y,ee_z))))
        return ch

    def create_solvers(self, ch):
         fk = kdl.ChainFkSolverPos_recursive(ch)
         ik_v = kdl.ChainIkSolverVel_pinv(ch)
         ik_p = kdl.ChainIkSolverPos_NR(ch, fk, ik_v)
         jac = kdl.ChainJntToJacSolver(ch)
         return fk, ik_v, ik_p, jac

    def setup_kdl_chains(self, arm, end_effector_length):
        #ch = self.create_chain_from_urdf('torso_lift_link', arm+'_gripper_tool_frame')
        if arm == 'r':
            ch = self.create_right_chain(end_effector_length)
        else:
            ch = self.create_left_chain(end_effector_length)
        fk, ik_v, ik_p, jac = self.create_solvers(ch)

        kdl_chains = {}
        kdl_chains['chain'] = ch
        kdl_chains['nJnts'] = ch.getNrOfJoints()
        kdl_chains['fk_p'] = fk
        kdl_chains['ik_v'] = ik_v
        kdl_chains['ik_p'] = ik_p
        kdl_chains['jacobian_solver'] = jac

        #Add both chains to dictionary
        self.kdl_chains = kdl_chains

    def FK_kdl(self, q, link_number):
        fk_solver = self.kdl_chains['fk_p']
        endeffec_frame = kdl.Frame()
        kinematics_status = fk_solver.JntToCart(q, endeffec_frame,
                                                link_number)
        if kinematics_status >= 0:
            return endeffec_frame
        else:
            print 'Could not compute forward kinematics.'
            return None

    #-------------- implementation of HRLArmKinematics -----------

    def FK_vanilla(self, q, link_number = 7):
        q = self.pr2_angles_to_kdl(q)
        frame = self.FK_kdl(q, link_number)
        pos = frame.p
        pos = ku.kdl_vec_to_np(pos) + self.arm_base_offset_from_torso_lift_link
        m = frame.M
        rot = ku.kdl_rot_to_np(m)
        return pos, rot

    ## compute Jacobian at point pos. 
    # p is in the ground coord frame.
    def jacobian(self, q, pos=None):
        if pos == None:
            pos = self.FK(q)[0]

        ch = self.kdl_chains['chain']
        v_list = []
        w_list = []

        for i in xrange(self.n_jts):
            p, rot = self.FK_vanilla(q, i)
            r = pos - p
            z_idx = ch.getSegment(i).getJoint().getType() - 1
            # An assumption here is that the KDL z-axis and PR2 z-axis
            # are identical
            z = rot[:, z_idx]
            v_list.append(np.matrix(np.cross(z.A1, r.A1)).T)
            w_list.append(z)

        J = np.row_stack((np.column_stack(v_list), np.column_stack(w_list)))
        return J

    def kdl_angles_to_pr2(self, q):
        if q == None:
            return None

        q_pr2 = [0] * 7
        q_pr2[0] = q[0]
        q_pr2[1] = q[1]
        q_pr2[2] = q[2]
        q_pr2[3] = q[3]
        q_pr2[4] = q[4]
        q_pr2[5] = q[5]
        q_pr2[6] = q[6]
        return q_pr2

    def pr2_angles_to_kdl(self, q):
        if q == None:
            return None
        n = len(q)
        q_kdl = kdl.JntArray(n)
        for i in xrange(n):
            q_kdl[i] = q[i]
        return q_kdl


    #----------- extra functions -----------------

    ## clamp joint angles to their physical limits.
    # @param q - list of 7 joint angles.
    # The joint limits for IK are larger that the physical limits.
    def clamp_to_joint_limits(self, q, delta_list=[0.,0.,0.,0.,0.,0.,0.]):
        min_arr, max_arr = self.get_joint_limits()
        q_arr = np.array(q)
        d_arr = np.array(delta_list)
        return np.clip(q_arr, min_arr-d_arr, max_arr+d_arr)

    def within_joint_limits(self, q, delta_list=[0.,0.,0.,0.,0.,0.,0.]):
        min_arr, max_arr = self.get_joint_limits()
        q_arr = np.array(q)
        d_arr = np.array(delta_list)
        return np.all((q_arr <= max_arr+d_arr, q_arr >= min_arr-d_arr))

    def get_joint_limits(self):
        return self.joint_lim_dict['min'], self.joint_lim_dict['max']




