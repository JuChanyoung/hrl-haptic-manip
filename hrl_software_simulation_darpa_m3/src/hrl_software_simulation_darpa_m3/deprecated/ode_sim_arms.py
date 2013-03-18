
import numpy as np, math
from threading import RLock
import sys, copy
import matplotlib.pyplot as pp

import roslib; roslib.load_manifest('hrl_software_simulation_darpa_m3')

import rospy
import PyKDL as kdl

from equilibrium_point_control.hrl_arm import HRLArm, HRLArmKinematics

import hrl_lib.geometry as hg
import hrl_lib.kdl_utils as ku
import hrl_lib.viz as hv

from hrl_msgs.msg import FloatArrayBare
from visualization_msgs.msg import Marker
from hrl_haptic_manipulation_in_clutter_msgs.msg import MechanicalImpedanceParams


class ODESimArm(HRLArm):
    def __init__(self):
        rospy.loginfo("Loading ODESimArm")
        kinematics = RobotSimulatorKDL() # KDL chain.
        HRLArm.__init__(self, kinematics)

        # at some point of time, Advait might move these to hrl_arm.py
        # and make things consistent with Cody. For now (Feb 7, 2012)
        # sticking to this file.
        self.kp = None
        self.kd = None

        self.jep_pub = rospy.Publisher('/sim_arm/command/jep', FloatArrayBare)
        self.cep_marker_pub = rospy.Publisher('/sim_arm/viz/cep', Marker)

        self.impedance_pub = rospy.Publisher('/sim_arm/command/joint_impedance',
                                             MechanicalImpedanceParams)

        rospy.Subscriber('/sim_arm/joint_angles', FloatArrayBare,
                         self.joint_states_cb)
        rospy.Subscriber('/sim_arm/joint_angle_rates', FloatArrayBare,
                         self.joint_rates_cb)
        rospy.Subscriber('/sim_arm/jep', FloatArrayBare, self.jep_cb)
        rospy.Subscriber('/sim_arm/joint_impedance', MechanicalImpedanceParams,
                         self.impedance_params_cb)

        rospy.sleep(1.)
        rospy.loginfo("Finished loading SimpleArmManger")

    def jep_cb(self, msg):
        with self.lock:
            self.ep = copy.copy(msg.data)

    def joint_states_cb(self, data):
        with self.lock:
            self.q = copy.copy(data.data)

    def joint_rates_cb(self, data):
        with self.lock:
            self.qdot = copy.copy(data.data)

    def impedance_params_cb(self, data):
        with self.lock:
            self.kp = copy.copy(data.k_p.data)
            self.kd = copy.copy(data.k_d.data)

    def get_joint_velocities(self):
        with self.lock:
            qdot = copy.copy(self.qdot)
        return qdot

    def set_ep(self, jep, duration=0.15):
        f = FloatArrayBare(jep)
        self.jep_pub.publish(f)
        self.publish_rviz_markers()

    def publish_rviz_markers(self):
        # publish the CEP marker.
        jep = self.get_ep()
        cep, r = self.kinematics.FK(jep)
        o = np.matrix([0.,0.,0.,1.]).T
        cep_marker = hv.single_marker(cep, o, 'sphere',
                        '/torso_lift_link', color=(0., 0., 1., 1.),
                        scale = (0.02, 0.02, 0.02), duration=0.)

        cep_marker.header.stamp = rospy.Time.now()
        self.cep_marker_pub.publish(cep_marker)

    # returns kp, kd
    # np arrays of stiffness and damping of the virtual springs.
    def get_joint_impedance(self):
        with self.lock:
            return np.array(self.kp), np.array(self.kd)

    # kp, kd - list or np array of stiffness and damping.
    def set_joint_impedance(self, kp, kd):
        im = MechanicalImpedanceParams()
        im.k_p.data = kp
        im.k_d.data = kd
        self.impedance_pub.publish(im)


##
# KDL for kinematics etc.
class RobotSimulatorKDL(HRLArmKinematics):
    def __init__(self):
        HRLArmKinematics.__init__(self, n_jts = 3)
        self.right_chain = self.create_right_chain()
        fk, ik_v, ik_p, jac = self.create_solvers(self.right_chain)

        self.right_fk = fk
        self.right_ik_v = ik_v
        self.right_ik_p = ik_p
        self.right_jac = jac
        self.right_tooltip = np.matrix([0.,0.,0.]).T

        # marc joint limits.
        self.min_jtlim_arr = np.radians(np.array([-150., -63, 0.]))
        self.max_jtlim_arr = np.radians(np.array([150., 162, 159.]))

        # advait joint limits.
#        self.min_jtlim_arr = np.radians(np.array([-75., -63+65, 0+2.]))
#        self.max_jtlim_arr = np.radians(np.array([75., 162, 159-1.]))

    def create_right_chain(self):
        height = 0.0
        linkage_offset_from_ground = np.matrix([0., 0., height]).T
        self.linkage_offset_from_ground = linkage_offset_from_ground
        b_jt_q_ind = [True, True, True]
        self.n_jts = len(b_jt_q_ind)

        torso_half_width = 0.196
        upper_arm_length = 0.334
        forearm_length = 0.288 #+ 0.115

        ee_location = np.matrix([0., -torso_half_width-upper_arm_length-forearm_length, height]).T
        b_jt_anchor = [[0, 0, height], [0, -torso_half_width, height],
                       [0., -torso_half_width-upper_arm_length, height]]
        b_jt_axis = [[0,0,1],[0,0,1], [0,0,1]]

        ch = kdl.Chain()
        prev_vec = np.copy(linkage_offset_from_ground.A1)
        n = len(b_jt_q_ind)

        for i in xrange(n-1):
            if b_jt_axis[i][0] == 1 and b_jt_axis[i][1] == 0 and b_jt_axis[i][2] == 0:
                kdl_jt = kdl.Joint(kdl.Joint.RotX)
            elif b_jt_axis[i][0] == 0 and b_jt_axis[i][1] == 1 and b_jt_axis[i][2] == 0:
                kdl_jt = kdl.Joint(kdl.Joint.RotY)
            elif b_jt_axis[i][0] == 0 and b_jt_axis[i][1] == 0 and b_jt_axis[i][2] == 1:
                kdl_jt = kdl.Joint(kdl.Joint.RotZ)
            else:
                print "can't do off-axis joints yet!!!"

            np_vec = np.array(b_jt_anchor[i+1])
            diff_vec = np_vec-prev_vec
            prev_vec = np_vec
            kdl_vec = kdl.Vector(diff_vec[0], diff_vec[1], diff_vec[2])            
            ch.addSegment(kdl.Segment(kdl_jt, kdl.Frame(kdl_vec)))

        np_vec = np.copy(ee_location.A1)
        diff_vec = np_vec-prev_vec

        if b_jt_axis[n-1][0] == 1 and b_jt_axis[n-1][1] == 0 and b_jt_axis[n-1][2] == 0:
            kdl_jt = kdl.Joint(kdl.Joint.RotX)
        elif b_jt_axis[n-1][0] == 0 and b_jt_axis[n-1][1] == 1 and b_jt_axis[n-1][2] == 0:
            kdl_jt = kdl.Joint(kdl.Joint.RotY)
        elif b_jt_axis[n-1][0] == 0 and b_jt_axis[n-1][1] == 0 and b_jt_axis[n-1][2] == 1:
            kdl_jt = kdl.Joint(kdl.Joint.RotZ)
        else:
            print "can't do off-axis joints yet!!!"

        kdl_vec = kdl.Vector(diff_vec[0], diff_vec[1], diff_vec[2])            
        ch.addSegment(kdl.Segment(kdl_jt, kdl.Frame(kdl_vec)))
        
        return ch

    def create_solvers(self, ch):
         fk = kdl.ChainFkSolverPos_recursive(ch)
         ik_v = kdl.ChainIkSolverVel_pinv(ch)
         ik_p = kdl.ChainIkSolverPos_NR(ch, fk, ik_v)
         jac = kdl.ChainJntToJacSolver(ch)
         return fk, ik_v, ik_p, jac

    def FK_kdl(self, q, link_number):
        fk = self.right_fk
        endeffec_frame = kdl.Frame()
        kinematics_status = fk.JntToCart(q, endeffec_frame,
                                         link_number)
        if kinematics_status >= 0:
            return endeffec_frame
        else:
            rospy.loginfo('Could not compute forward kinematics.')
            return None

    ## returns point in torso lift link.
    def FK_vanilla(self, q, link_number=None):
        if link_number == None:
            link_number = self.n_jts
        link_number = min(link_number, self.n_jts)

        q = self.list_to_kdl(q)
        frame = self.FK_kdl(q, link_number)
        pos = frame.p
        pos = ku.kdl_vec_to_np(pos)
        pos = pos + self.linkage_offset_from_ground
        m = frame.M
        rot = ku.kdl_rot_to_np(m)

        return pos, rot

    def kdl_to_list(self, q):
        if q == None:
            return None
        n = self.n_jts
        q_list = [0] * n
        for i in xrange(n):
            q_list[i] = q[i]
        return q_list

    def list_to_kdl(self, q):
        if q == None:
            return None
        n = len(q)
        q_kdl = kdl.JntArray(n)
        for i in xrange(n):
            q_kdl[i] = q[i]
        return q_kdl

    ## compute Jacobian at point pos. 
    # p is in the ground coord frame.
    def Jacobian(self, q, pos=None):
        if pos == None:
            pos = self.FK(q)[0]

        v_list = []
        w_list = []

        #ee, r = self.FK(q)
        #pos = ee

        for i in xrange(self.n_jts):
            p, rot = self.FK_vanilla(q, i)
            r = pos - p
            z_idx = self.right_chain.getSegment(i).getJoint().getType() - 1
            z = rot[:, z_idx]
            v_list.append(np.matrix(np.cross(z.A1, r.A1)).T)
            w_list.append(z)

        J = np.row_stack((np.column_stack(v_list), np.column_stack(w_list)))
        return J

    def clamp_to_joint_limits(self, q):
        return np.clip(q, self.min_jtlim_arr, self.max_jtlim_arr)

    def within_joint_limits(self, q, active_joints = [0,1,2],
                            delta_list=[0.,0.,0.]):
        min_arr = self.min_jtlim_arr[active_joints]
        max_arr = self.max_jtlim_arr[active_joints]

        q_arr = np.array(q)[active_joints]
        d_arr = np.array(delta_list)[active_joints]
        return np.all((q_arr <= max_arr+d_arr, q_arr >= min_arr+d_arr))

    def get_joint_limits(self):
        return self.min_jtlim_arr, self.max_jtlim_arr

    # plot the arm using matplotlib.
    # flip_xy - x will point up and +ve y will be to the left. This is
    # to match how we look at the arm in rviz.
    def plot_arm(self, q, color, alpha, flip_xy):
        pts = [[0.,0.,0.]]
        for i in range(len(q)):
            p,_ = self.FK(q, i+1)
            pts.append(p.A1.tolist())

        pts_2d = np.array(pts)[:,0:2]
        direc_list = (pts_2d[1:] - pts_2d[:-1]).tolist()

        for i, d in enumerate(direc_list):
            d_vec = np.matrix(d).T
            d_vec = d_vec / np.linalg.norm(d_vec)
            w = np.cross(d_vec.A1, np.array([0., 0., 1.])) * 0.03/2
            x1 = pts_2d[i,0]
            y1 = pts_2d[i,1]
            x2 = pts_2d[i+1,0]
            y2 = pts_2d[i+1,1]

            x_data = np.array([x1+w[0], x1-w[0], x2-w[0], x2+w[0], x1+w[0]])
            y_data = np.array([y1+w[1], y1-w[1], y2-w[1], y2+w[1], y1+w[1]])

            if flip_xy:
                tmp = y_data
                y_data = x_data
                x_data = -tmp

            pp.plot(x_data, y_data, '-', alpha=alpha, color=color,
                    linewidth=2)


if __name__ == '__main__':
    rospy.init_node('ode_arms_test')
    ode_arm = ODESimArm()

    #test_jep = np.radians([30., 20., 45.])
    test_jep = np.radians([0., 0., 0.])
    p, _ = ode_arm.kinematics.FK(test_jep, 3)
    print 'p:', p.A1

#    while not rospy.is_shutdown():
#    ode_arm.set_jep(arm, test_jep)
#        rospy.sleep(0.1)



