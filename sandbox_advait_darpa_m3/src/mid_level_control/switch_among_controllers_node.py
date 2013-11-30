#!/usr/bin/python
#
# Node that is common to software simulation and Cody. Interfaces with
# the dashboard.
#
#

import sys, os
import numpy as np, math
import copy

import roslib; roslib.load_manifest('sandbox_advait_darpa_m3')
import rospy
import hrl_lib.util as ut

import hrl_haptic_controllers_darpa_m3.epc_skin as es

from std_msgs.msg import String, Bool
from geometry_msgs.msg import TransformStamped
from hrl_srvs.srv import Bool_None

class SwitchAmongControllers():
    def __init__(self, epc_skin):
        self.goal_location_world = None # location to reach to in the world frame.
        self.initial_q = None # joint angles in the initial configuration.
        self.initial_jep = None # starting JEP.
        self.optitrak_marker = None
        self.epc_skin = epc_skin
        self.epc_stop_pub = rospy.Publisher('/epc/stop', Bool)
        self.tm_pause = rospy.ServiceProxy('/task_monitor/pause', Bool_None)
        rospy.Subscriber('/fixed_obstacle_trackable/pose',
                         TransformStamped, self.marker_cb)

    #------------------------------------------------------------
    # ROS stuff
    #------------------------------------------------------------

    def publish_epc_start(self):
        self.epc_stop_pub.publish(Bool(False))
        rospy.sleep(0.1)

    def set_goal_software_sim(self):
        self.goal_location_world = np.matrix(rospy.get_param('m3/software_testbed/goal')).T
        self.epc_skin.publish_goal(self.goal_location_world, '/world')

    def set_goal_optitrak(self):
        self.goal_location_world = copy.copy(self.optitrak_marker)
        self.epc_skin.publish_goal(self.goal_location_world, '/world')

    def marker_cb(self, msg):
        t = msg.transform.translation
        self.optitrak_marker = np.matrix([t.x, t.y, t.z+0.075]).T
        #self.optitrak_marker = np.matrix([t.x, t.y, t.z+0.12]).T

    #-----------------------------------------------------------
    # common non-switching functions and functionality
    #-----------------------------------------------------------

    def reduce_force(self, logging_name):
        self.tm_pause(True)
        res = self.epc_skin.reduce_force(self.reduce_force_control_param_dict,
                                   logging_name,
                                   self.reduce_force_monitor_param_dict)
        self.tm_pause(False)
        return res

    # for now this is not a stack. But it might be worth it so that I
    # can do a bit of depth first search kinds of things.
    # here push is stack terminology (not physical pushing)
    def push_start(self):
        self.initial_q = self.epc_skin.robot.get_joint_angles()
        self.initial_jep = self.epc_skin.robot.get_ep()

    def is_contact_head_on(self):
        it_is = False
        robot = self.epc_skin.robot

        f_l, n_l, loc_l , _ = self.epc_skin.scl.force_normal_loc_joint_list(False)
        q = robot.get_joint_angles()
        ee = robot.kinematics.FK(q)[0]
        n_jts = len(q)
        wrist = robot.kinematics.FK(q, n_jts-1)[0]
        ee_direc = ee-wrist
        ee_direc = ee_direc / np.linalg.norm(ee_direc)

        n_contacts = len(f_l)
        for i in range(n_contacts):
            f = f_l[i]
            loc = loc_l[i]
            dist_along_arm = robot.kinematics.distance_from_ee_along_arm(q, loc)
            f_direc = f / np.linalg.norm(f)
            ang =  math.acos((ee_direc.T * f_direc)[0,0])

            if dist_along_arm < 0.03 and ang < math.radians(50.):
                # contact close to end effector.
                it_is = True

        return it_is

    #------------------------------------------------------------
    # functions that switch among controllers.
    #------------------------------------------------------------

    # retry_if_head_on - try and determine if the collision that caused
    # the controller to stop was a head on collision. if it was, then pick
    # a side and retry
    # @param goal - goal for the local controller (in torso frame)
    # @param attempt_number - using for logging_name.
    # @param goal_orientation - 3x3 np rotation matrix that transforms
    #                           points from the goal coord frame to
    #                           the torso coord frame
    # @param ignore_orientation - force controller to ignore
    # orientation even if it supports it.
    def reach_greedy(self, goal, goal_orientation, retry_if_head_on,
                     eq_gen_type, stopping_dist, stopping_angle,
                     attempt_name, timeout = np.inf,
                     retry_direction='right', ignore_orientation=False):
        attempt_name += '='
        # resetting the start location. when I pull out, I pull out to
        # this location only
        self.push_start()
        #goal = self.epc_skin.world_to_torso(goal_world)
        keep_going = True
        did_i_retry = False

        gtg_control_dict = copy.copy(self.greedy_to_goal_control_param_dict)
        gtg_control_dict['stopping_dist_to_goal'] = stopping_dist
        gtg_control_dict['stopping_ang_to_goal'] = stopping_angle
        if ignore_orientation:
            gtg_control_dict['orientation_weight'] = 0.
        gtg_monitor_dict = copy.copy(self.greedy_to_goal_monitor_param_dict)
        
        sm_control_dict = copy.copy(self.small_motions_control_param_dict)
        sm_control_dict['stopping_dist_to_goal'] = stopping_dist
        sm_monitor_dict = copy.copy(self.small_motions_monitor_param_dict)

        #small_motion_eq_gen = 'no_optimize_jep'
        small_motion_eq_gen = 'mpc_qs_1'

        head_on_count = 0

        iteration = 0
        while keep_going:
            iteration += 1
            nm = attempt_name+'to_goal_%d'%(iteration)
            #logging_name = 'greedy_to_goal_%d_%d'%(attempt_number, iteration)

            res = self.epc_skin.greedy_to_goal(goal, goal_orientation,
                                               gtg_control_dict,
                                               timeout, eq_gen_type,
                                               nm, gtg_monitor_dict)
            if 'Reached' in res[0]:
                break

            # check for head-on collision. pick a side in case of
            # head on and go greedy again?
            if retry_if_head_on:
                keep_going = self.is_contact_head_on()

                if head_on_count == 1:
                    keep_going = False
            else:
                keep_going = False

            if keep_going:
                did_i_retry = True
                head_on_count += 1
                # If the log_and_monitor node stopped the controller,
                # then I need to publish a False to /epc/stop so that
                # arm is allowed to move again
                self.publish_epc_start()
                nm = attempt_name + 'reduce_force_%d'%(iteration)
                #logging_name = 'reduce_force_%d_%d'%(attempt_number, iteration)
                self.reduce_force(nm)

                q = self.epc_skin.robot.get_joint_angles()
                n_jts = self.epc_skin.robot.kinematics.n_jts
                ee = self.epc_skin.robot.kinematics.FK(q)[0]
                wrist = self.epc_skin.robot.kinematics.FK(q, n_jts-1)[0]
                ee_direc = ee-wrist
                ee_direc[2,0] = 0. # forcing XY plane.
                ee_direc = ee_direc / np.linalg.norm(ee_direc)

                goal_back = ee  - ee_direc * 0.05
                #ut.get_keystroke('Hit a key to move back a bit.')
                nm = attempt_name + 'small_motion_back_%d'%(iteration)
                res = self.epc_skin.greedy_to_goal(goal_back, sm_control_dict, 5.,
                                         small_motion_eq_gen, nm,
                                         sm_monitor_dict)
                self.publish_epc_start()

                # pick a side.
                if retry_direction == 'right':
                    z = np.array([0.,0.,1.])
                else:
                    z = np.array([0.,0.,-1.])

                side_vec = np.matrix(np.cross(ee_direc.A1, z)).T
                if opt.cody:
                    side_dist = 0.1
                    side_timeout = 5.
                else:
                    side_dist = 0.1
                    side_timeout = 5.
                goal_side = goal_back + side_vec * side_dist
                nm = attempt_name + 'small_motion_side_%d'%(iteration)
                res = self.epc_skin.greedy_to_goal(goal_side, sm_control_dict, side_timeout,
                                                   small_motion_eq_gen, nm,
                                                   sm_monitor_dict)
                self.publish_epc_start()
                rospy.loginfo('Going to move to the goal.')

        res = list(res)
        res.append(did_i_retry)
        print 'Result:', res
        return res

    def pull_out(self, logging_name, elbow_start=None):
        logging_name += '='
        # pull out using the delta QP controller (always)
        pull_out_eq_gen_type = 'mpc_qs_1'

        po_control_dict = copy.copy(self.pull_out_control_param_dict)
        po_control_dict['stopping_dist_to_goal'] = 0.02
        po_monitor_dict = copy.copy(self.pull_out_monitor_param_dict)

        n_jts = self.epc_skin.robot.kinematics.n_jts
        if  n_jts == 3:
            if elbow_start == None:
                elbow_start = self.epc_skin.robot.kinematics.FK(self.initial_q, 3)[0]
            timeout = 40.
        elif n_jts == 7:
            elbow_start = self.epc_skin.robot.kinematics.FK(self.initial_q, 3)[0]
            timeout = 60.
        else:
            raise RuntimeError('Unknown number of joints: %d'%n_jts)

        # June 6, 2012. Advait commented out pull out elbow and is
        # going to use the tip to pull out on all robots.
        # Shprtly after this, he found that on Cody pull out failed.
        # So, he has restored the pull_out_elbow.
        #res = ('Reached', None)
        res = self.epc_skin.pull_out_elbow(elbow_start,
                                    po_control_dict, timeout,
                                    pull_out_eq_gen_type,
                                    logging_name+'elbow', po_monitor_dict)

        if res[0] == 'Reached':
            goal = self.epc_skin.robot.kinematics.FK(self.initial_q)[0]
            po_control_dict['stopping_dist_to_goal'] = 0.02
            res = self.epc_skin.greedy_to_goal(goal, po_control_dict, timeout,
                                               pull_out_eq_gen_type,
                                               logging_name+'tip',
                                               po_monitor_dict)
            print 'RES:', res[0]
            if res[0] == 'Reached':
                self.epc_skin.go_jep(self.initial_jep, speed=math.radians(15))
                rospy.sleep(0.1)

                #pop_start()
                self.push_start()

        return res

    # first naive implementation of reaching in from multiple
    # configurations, without moving the mobile base.
    # @param goal - goal for the local controller (in torso frame)
    # @param stopping_distance - distance from goal when we will declare success
    def fixed_base_multiple_reach(self, goal, delta_y_reach_in_l,
                                  eq_gen_type, stopping_distance, logging_nm = ''):
        if logging_nm != '':
            logging_nm += '='
        initial_reach_in = self.epc_skin.robot.kinematics.FK(self.initial_q)[0]
        retry_direction = 'right'
        keep_going = True
        reached_goal = False
        i = 0
        while keep_going:
            dy = delta_y_reach_in_l[i]
            # compute next reach in location (with base fixed)
            # hack: 1cm is the stopping distance for greedy to goal
            dy  = dy + 0.02 * np.sign(dy)
            reach_in_loc = initial_reach_in + np.matrix([0., dy, 0.]).T

            # move arm to reach in location
            rospy.loginfo('Going to reach_in_location')
            attempt_name = logging_nm + 'move_to_reach_in_pos_%d_retry_'%(i)+retry_direction
            res = self.reach_greedy(reach_in_loc, retry_if_head_on=False, 
                                    eq_gen_type = 'mpc_qs_1',
                                    timeout = 30., stopping_dist=0.02,
                                    attempt_name = attempt_name)

            #ut.get_keystroke('Hit a key to start reaching in')
            self.publish_epc_start()

            # now reach in.
            rospy.loginfo('now reaching in')
            attempt_name = logging_nm + 'reach_from_reach_in_dy_%.2f_retry_'%(dy)+retry_direction
            res = self.reach_greedy(goal, retry_if_head_on=False,
            #res = self.reach_greedy(goal, retry_if_head_on=True,
                                    eq_gen_type = eq_gen_type,
                                    retry_direction = retry_direction,
                                    timeout = 100.,
                                    stopping_dist = stopping_distance,
                                    attempt_name = attempt_name)
            did_reach_opt_retry = res[-1]

            if did_reach_opt_retry == True and retry_direction == 'right':
                # flip reaching direction from the same location.
                new_retry_direction = 'left'
            else:
                # did not make head on collision, so try next reach in
                # location.
                new_retry_direction = 'right'
                i += 1

            if i == len(delta_y_reach_in_l):
                keep_going = False

            # do not retry if reached the goal.
            if res[0] == 'Reached':
                keep_going = False
                reached_goal = True
                #HACK - in software simulation, do not pull out if
                #       reached the goal.
                if opt.cody:
                    ut.get_keystroke('Reached the goal. Hit a key to continue')

            if keep_going == False and (not opt.cody):
                #do not pull out if end of software simulation trial
                rospy.loginfo('res: %s'%res[0])
                break

            #ut.get_keystroke('Hit a key to continue')
            rospy.loginfo('Done with reach. Now going to pull out')

            self.publish_epc_start()
            if not opt.cody:
                #HACK - only doing reduce_force in software simulation.
                rospy.loginfo('reducing force')
                self.reduce_force('reduce_force_blah') # in case force too high, reduce_force is mostly harmless.

            rospy.loginfo('pulling out')
            attempt_name = logging_nm + 'pull_out_%d_1_retry_'%(i)+retry_direction
            res = self.pull_out(attempt_name)
            if res[0] != 'Reached':
                self.publish_epc_start()
                rospy.sleep(0.5)
                attempt_name = logging_nm + 'pull_out_%d_2_retry_'%(i)+retry_direction
                res = self.pull_out(attempt_name)
            
            if res[0] != 'Reached':
                if not opt.cody:
                    raise UserWarning('Pull out failed. Exiting fixed_base_multiple_reach.')
                else:
                    rospy.loginfo('Pull out failed.')
                    rospy.loginfo('Please pull out manually.')
                    ut.get_keystroke('hit a key to continue')
                    self.publish_epc_start()
                    rospy.sleep(0.5)

            retry_direction = new_retry_direction

        return reached_goal

    ##
    # @ delta_y_mobile_base - is in the coord frame of the torso, at
    #                         when this function is called.
    # @param move_at_start - should the mobile base move fwd until
    #              contact the first time (it will move back before
    #              going to the next delta_y_reach_in location)
    # @param stopping_distance - distance from goal when we will declare success
    def reach_in_multiple(self, goal, delta_y_mobile_base,
                          delta_y_reach_in_l, move_at_start,
                          stopping_distance):
        goal_world = self.epc_skin.torso_to_world(goal)

        initial_loc, initial_rot = self.epc_skin.current_torso_pose()
        initial_reach_in_loc = self.epc_skin.robot.kinematics.FK(self.initial_q)[0]
        home_jep = copy.copy(self.initial_jep)

        nominal_base_motion_distance = 0.2
        dist_moved_before_hit = 0.

        try:
            for dy_base in delta_y_mobile_base:
                res = self.reach_greedy(initial_reach_in_loc, retry_if_head_on=False,
                                        eq_gen_type = 'mpc_qs_1',
                                        stopping_dist = 0.02,
                                        attempt_name = 'base_dy_%.2f'%dy_base+'_move_to_initial_reach_location')
                if res[0] != 'Reached':
                    raise UserWarning('Unable to go to home location')

                self.epc_skin.go_jep(home_jep)

                if move_at_start:
                    # now go to the new torso location.
                    torso_loc = initial_loc + initial_rot * np.matrix([0., dy_base, 0.]).T
                    self.epc_skin.move_torso_to(torso_loc, initial_rot)

                    # in preparation for moving base until contact.
                    safety_for_base_motion = 0.03
                    loc_while_moving_base = initial_reach_in_loc + \
                            initial_rot * np.matrix([safety_for_base_motion, 0., 0.]).T
                    res = self.reach_greedy(loc_while_moving_base, retry_if_head_on=False,
                                            eq_gen_type = 'mpc_qs_1',
                                            stopping_dist = 0.01,
                                            attempt_name = 'safety_for_base_motion')

                    self.publish_epc_start()
                    
                    #print '####################################'
                    #ut.get_keystroke('Hit a key to move_base_till_hit')
                    res = self.epc_skin.move_base_till_hit(nominal_base_motion_distance)
                    #print 'res:', res[0]
                    #ut.get_keystroke('Done with move_base_till_hit')

                    new_torso_pos = self.epc_skin.current_torso_pose()[0]
                    # how far fwd in the robot's frame did we move.
                    dist_moved_before_hit = abs((initial_rot.T * \
                                    (new_torso_pos - initial_loc))[0,0])

                    self.epc_skin.go_jep(home_jep)
                else:
                    self.publish_epc_start()
                    dist_moved_before_hit = nominal_base_motion_distance
                    initial_loc += initial_rot * np.matrix([-nominal_base_motion_distance, 0., 0.]).T
                    nominal_base_motion_distance = nominal_base_motion_distance + 0.1
                    move_at_start = True

                goal = self.epc_skin.world_to_torso(goal_world)
                
                # TODO - hard coded is bad!
                if True:
                    if self.fixed_base_multiple_reach(goal, delta_y_reach_in_l, 'mpc_qs_1',
                                                      stopping_distance, logging_nm = 'base_dy_%.2f'%dy_base):
                        # reached the goal location.
                        break
                else:
                    # comparing QP and simple.
                    self.fixed_base_multiple_reach(goal, delta_y_reach_in_l, 'mpc_qs_1',
                                                   stopping_distance, logging_nm = 'qp_base_dy_%.2f'%dy_base)

                    ut.get_keystroke('Hit a key to reach in with greedy.')
                    self.fixed_base_multiple_reach(goal, delta_y_reach_in_l, 'simple',
                                                   stopping_distance, logging_nm = 'simple_base_dy_%.2f'%dy_base)

                # first move the base back by the amount that
                # move_base_till_hit had moved it in. this is a bit dangerous
                self.epc_skin.base.back(dist_moved_before_hit, blocking=True)

                ut.get_keystroke('Hit a key to move to the next reach in position.')

        except UserWarning as e:
            rospy.logwarn(str(e.args))


# callback for the command that decides which behavior to execute.
# this will come from the dashboard 
def skin_behavior_cb(msg):
    if msg.data == 'set_goal':
        sac.set_goal()
    elif msg.data == 'set_start':
        sac.push_start()
    elif msg.data == 'next_reach_in_pose':
        rospy.logwarn('Unimplemented %s'%(msg.data))
    else:
        # below is temporary hack for automated trials for Oct 2011
        # Darpa M3 PI meeting.
        #
        #goal_num = 4
        #n_goals = 5
        #g = np.matrix([0.21, -0.2, 0.44]).T
        #dist_between_goals = 0.4 / (n_goals-1)
        #g[1,0] += (goal_num-1) * dist_between_goals
        #sac.goal_location_world = g

        if msg.data == 'pull_out':
            sac.pull_out('pull_out_1')
        elif msg.data == 'reduce_force':
            sac.reduce_force('reduce_force_standalone')
        elif msg.data == 'reach_to_goal':
            t0 = rospy.get_time()
            sac.epc_skin.publish_goal(sac.goal_location_world, '/world')
            goal = sac.epc_skin.world_to_torso(sac.goal_location_world)

            #reach_opt_greedy(goal, retry_if_head_on = False,
            sac.reach_greedy(goal, retry_if_head_on=True,
                             eq_gen_type = 'mpc_qs_1', stopping_dist = 0.040,
                             attempt_name = 'reach_from_single_reach_in_pos')
            t1 = rospy.get_time()
            print 'Time to reach:', t1-t0
        elif msg.data == 'try_multiple':
            if True:
                sac.epc_skin.publish_goal(sac.goal_location_world, '/world')
                goal = sac.epc_skin.world_to_torso(sac.goal_location_world)

                if opt.cody:
                    delta_y_reach_in_l = [0]
                    delta_y_mobile_base = [0, 0.15, 0.3, 0.45]
                else:
                    delta_y_reach_in_l = [0]
                    delta_y_mobile_base = [0, -0.2, 0.2]

                # move the segway
                sac.reach_in_multiple(goal, delta_y_mobile_base,
                                      delta_y_reach_in_l,
                                      #move_at_start = False)
                                      move_at_start = True)
            else:
                # fixed base reaching in
                if opt.cody:
                    delta_y_reach_in_l = [0, 0.1]
                else:
                    #delta_y_reach_in_l = [0, -0.03, -0.1, -0.15, -0.2]
                    delta_y_reach_in_l = [0, -0.2]

                sac.epc_skin.publish_goal(sac.goal_location_world, '/world')
                goal = sac.epc_skin.world_to_torso(sac.goal_location_world)
                
                sac.fixed_base_multiple_reach(goal, delta_y_reach_in_l)
                #if goal_world_2 != None:
                #    self.epc_skin.go_jep(home_jep) # this is dangerous.
                #    goal_world = copy.copy(goal_world_2)
                #    goal = self.epc_skin.world_to_torso(goal_world)
                #    self.epc_skin.publish_goal(goal, '/torso_lift_link')
                #    fixed_base_multiple_reach(delta_y_reach_in_l)



if __name__ == '__main__':
    import optparse
    p = optparse.OptionParser()
    p.add_option('--batch', action='store_true', dest='batch',
                 help='run in batch mode')
    p.add_option('--cody', action='store_true', dest='cody',
                 help='task monitoring for cody')
    p.add_option('--hil', action='store_true', dest='hil',
                 help='hardware-in-loop simulation with Cody')
    p.add_option('--sim3', action='store_true', dest='sim3',
                 help='three link software simulation')
    p.add_option('--sim3_with_hand', action='store_true',
                 dest='sim3_with_hand',
                 help='three link with hand software simulation')
    p.add_option('--use_wrist_joints', action='store_true',
                 dest='use_wrist_joints',
                 help='use wrist joints (Cody)')
    p.add_option('--ignore_mobile_base', action='store_true',
                 dest='ignore_mobile_base',
                 help='ignore mobile base (software simulation)')
    p.add_option('--arm_to_use', action='store', dest='arm',
                 type='string', help='which arm to use (l or r)',
                 default=None)
    p.add_option('--ignore_skin', '--is', action='store_true',
                 dest='ignore_skin', help='ignore feedback from skin')

    p.add_option('--single_reach', action='store_true',
                 dest='single_reach',
                 help='reach from one initial configuration')

    p.add_option('--allowable_contact_force', '--acf', action='store',
                 dest='acf', type='float', help='value for f_thresh',
                 default=5.0)

    opt, args = p.parse_args()
    
    if opt.cody and (not opt.hil):
        skin_topic_list = ['/skin/contacts_forearm', '/skin/contacts_ft']
    else:
        skin_topic_list = ['/skin/contacts']

    rospy.init_node('switch_among_controllers_node')

    rospy.Subscriber('/epc_skin/command/behavior', String,
                      skin_behavior_cb)

    if opt.cody:
        import hrl_cody_arms.cody_arm_client as cac
        import sandbox_advait_darpa_m3.cody.cody_guarded_move as cgm

        if opt.arm == None:
            rospy.logerr('Need to specify --arm_to_use.\nExiting...')
            sys.exit()

        if opt.use_wrist_joints:
            robot = cac.CodyArmClient_7DOF(opt.arm)
        else:
            robot = cac.CodyArmClient_4DOF(opt.arm)

        # the reason for explicitly specifying the joint limits is
        # that I have restricted the shoulder roll.
        if opt.arm == 'r':
            max_lim = np.radians([ 120.00, 122.15, 0., 144., 122.,  45.,  45.])
            min_lim = np.radians([ -47.61,  -20., -77.5,   0., -80., -45., -45.])
        elif opt.arm == 'l':
            max_lim = np.radians([ 120.00,   20.,  77.5, 144.,   80.,  45.,  45.])
            min_lim = np.radians([ -47.61, -122.15, 0.,   0., -122., -45., -45.])
        else:
            rospy.logerr('Unknown arm.\nExiting...')
            sys.exit()

        robot.kinematics.joint_lim_dict['max'] = max_lim
        robot.kinematics.joint_lim_dict['min'] = min_lim

        #robot.kinematics.set_tooltip(np.matrix([0.,0.,-0.16]).T) # tube
        #robot.kinematics.set_tooltip(np.matrix([0.,0.,-0.01]).T) # stub
        robot.kinematics.set_tooltip(np.matrix([0.,0.,-0.04]).T) # stub with mini45
        scl = cgm.Cody_SkinClient(skin_topic_list)
        epcon = cgm.MobileSkinEPC_Cody(robot, scl)

        while robot.get_ep() == None:
            rospy.sleep(0.1)
        jep_start = robot.get_ep()

    else:
        from hrl_software_simulation_darpa_m3.ode_sim_guarded_move import ode_SkinClient
        import hrl_software_simulation_darpa_m3.gen_sim_arms as gsa

        if opt.sim3:
            import hrl_common_code_darpa_m3.robot_config.three_link_planar_capsule as d_robot

            if opt.ignore_mobile_base:
                #jep_start = np.radians([-140.0, 100, 120])
                jep_start = np.radians([-50.0, 70, 145])
            else:
                jep_start = np.radians([-100.0, 110, 110])
                init_base_motion = -np.matrix([0.11439146, -0.15089079,  0.]).T

        elif opt.sim3_with_hand:
            import hrl_common_code_darpa_m3.robot_config.three_link_with_hand as d_robot
            jep_start = np.radians([-30.0, 150, 15])

        else:
            print 'Please specify a testbed.'
            print 'Exiting ...'
            sys.exit()

        ode_arm = gsa.ODESimArm(d_robot)
        scl = ode_SkinClient(skin_topic_list)

        if opt.ignore_mobile_base:
            epcon = es.Skin_EPC(ode_arm, scl)
            rospy.sleep(1.)
        else:
            epcon = sgm.MobileSkinEPC_ODE(ode_arm, scl)
            rospy.sleep(1.)
            epcon.base.go(init_base_motion, 0, blocking=True)

        kp, kd = ode_arm.get_joint_impedance()
        ode_arm.set_ep(jep_start)

    sac = SwitchAmongControllers(epcon)

    if opt.sim3:
        sac.set_goal = sac.set_goal_software_sim

        #static_contact_stiffness_estimate = 100000.
        static_contact_stiffness_estimate = 1000.
        estimate_contact_stiffness = True
        goal_velocity_for_hand = 0.05
        ee_motion_threshold = 0.001

        #---------------------------
        # greedy to goal
        #---------------------------
        greedy_to_goal_control_param_dict = {
            # for delta_qp
                'jep_start': jep_start,
                'time_step': 0.01,
                'planar': True,
                'goal_velocity_for_hand': goal_velocity_for_hand,
                'allowable_contact_force': opt.acf,
                'k': static_contact_stiffness_estimate,
                'estimate_contact_stiffness': estimate_contact_stiffness,
                'ignore_skin': opt.ignore_skin,
            }

        greedy_to_goal_monitor_param_dict = {
                'ee_motion_threshold': ee_motion_threshold,
                'stopping_force': 50.
            }

        #---------------------------
        # reduce force
        #---------------------------
        reduce_force_control_param_dict = {
                'planar': True,
            }
        reduce_force_monitor_param_dict = {}

        #---------------------------
        # pull out
        #---------------------------
        pull_out_control_param_dict = {
            # delta_qp.
                'time_step': 0.01,
                'goal_velocity_for_hand': goal_velocity_for_hand,
                'planar': True,
                'allowable_contact_force': opt.acf,
                'k': static_contact_stiffness_estimate,
                'estimate_contact_stiffness': estimate_contact_stiffness,
                'ignore_skin': opt.ignore_skin,
            }

        pull_out_monitor_param_dict = {
                'ee_motion_threshold': ee_motion_threshold,
                'stopping_force': 80.
            }

        #---------------------------
        # small motions
        #---------------------------
        small_motions_control_param_dict = {
            # for delta_qp
                'time_step': 0.01 ,
                'goal_velocity_for_hand': goal_velocity_for_hand,
                'planar': True,
                'allowable_contact_force': 10.,
                'k': static_contact_stiffness_estimate,
                'estimate_contact_stiffness': estimate_contact_stiffness,
                'ignore_skin': opt.ignore_skin,
            }

        small_motions_monitor_param_dict = {
                'ee_motion_threshold': ee_motion_threshold,
                'stopping_force': 50.,
            }

    if opt.sim3_with_hand:
        sac.set_goal = sac.set_goal_software_sim

        #static_contact_stiffness_estimate = 100000.
        static_contact_stiffness_estimate = 1000.
        estimate_contact_stiffness = True
        goal_velocity_for_hand = 0.05
        ee_motion_threshold = 0.001

        #---------------------------
        # greedy to goal
        #---------------------------
        greedy_to_goal_control_param_dict = {
            # for delta_qp
                'jep_start': jep_start,
                'time_step': 0.01,
                'planar': True,
                'goal_velocity_for_hand': goal_velocity_for_hand,
                'allowable_contact_force': 5.,
                'k': static_contact_stiffness_estimate,
                'estimate_contact_stiffness': estimate_contact_stiffness,
                'ignore_skin': opt.ignore_skin,
            }

        greedy_to_goal_monitor_param_dict = {
                'ee_motion_threshold': ee_motion_threshold,
                'stopping_force': 50.
            }

        #---------------------------
        # reduce force
        #---------------------------
        reduce_force_control_param_dict = {
                'planar': True,
            }
        reduce_force_monitor_param_dict = {}

        #---------------------------
        # pull out
        #---------------------------
        pull_out_control_param_dict = {
            # delta_qp.
                'time_step': 0.01,
                'goal_velocity_for_hand': goal_velocity_for_hand,
                'planar': True,
                'allowable_contact_force': 10.,
                'k': static_contact_stiffness_estimate,
                'estimate_contact_stiffness': estimate_contact_stiffness,
                'ignore_skin': opt.ignore_skin,
            }

        pull_out_monitor_param_dict = {
                'ee_motion_threshold': ee_motion_threshold,
                'stopping_force': 80.
            }

        #---------------------------
        # small motions
        #---------------------------
        small_motions_control_param_dict = {
            # for delta_qp
                'time_step': 0.01 ,
                'goal_velocity_for_hand': goal_velocity_for_hand,
                'planar': True,
                'allowable_contact_force': 10.,
                'k': static_contact_stiffness_estimate,
                'estimate_contact_stiffness': estimate_contact_stiffness,
                'ignore_skin': opt.ignore_skin,
            }

        small_motions_monitor_param_dict = {
                'ee_motion_threshold': ee_motion_threshold,
                'stopping_force': 50.,
            }

    elif opt.cody:
        sac.set_goal = sac.set_goal_optitrak

        static_contact_stiffness_estimate = 1000.
        estimate_contact_stiffness = False

        # start with low estimate of stiffness and turn on the
        # stiffness estimation.
        #static_contact_stiffness_estimate = 50.
        #estimate_contact_stiffness = True

        # for foliage trials.
        #goal_velocity_for_hand = 0.2
        #ee_motion_threshold = 0.005

        # very slow.
        goal_velocity_for_hand = 0.05
        ee_motion_threshold = 0.004

        # fast.
        #goal_velocity_for_hand = 0.3
        #ee_motion_threshold = 0.01
        
        time_step = 0.01
        #time_step = 1.

        #---------------------------
        # greedy to goal
        #---------------------------
        greedy_to_goal_control_param_dict = {
            # for delta_qp
                'jep_start': jep_start,
                'time_step': time_step,
                'planar': False,
                'allowable_contact_force': 5.,
                'goal_velocity_for_hand': goal_velocity_for_hand,
                'k': static_contact_stiffness_estimate,
                'estimate_contact_stiffness': estimate_contact_stiffness,
                'ignore_skin': opt.ignore_skin,
            }

        greedy_to_goal_monitor_param_dict = {
                'ee_motion_threshold': ee_motion_threshold,
                'stopping_force': 15.
            }

        #---------------------------
        # reduce force
        #---------------------------
        reduce_force_control_param_dict = {}
        reduce_force_monitor_param_dict = {}

        #---------------------------
        # pull out
        #---------------------------
        pull_out_control_param_dict = {
            # for delta_qp
                'time_step': time_step,
                'goal_velocity_for_hand': goal_velocity_for_hand,
                'planar': False,
                'allowable_contact_force': 5.,
                'k': static_contact_stiffness_estimate,
                'estimate_contact_stiffness': estimate_contact_stiffness,
                'ignore_skin': opt.ignore_skin,
            }

        pull_out_monitor_param_dict = {
                'ee_motion_threshold': ee_motion_threshold,
                'stopping_force': 25.
            }

        #---------------------------
        # small motions
        #---------------------------
        small_motions_control_param_dict = {
            # for delta_qp
                'time_step': time_step,
                'goal_velocity_for_hand': goal_velocity_for_hand,
                'planar': False,
                'allowable_contact_force': 5.,
                'k': static_contact_stiffness_estimate,
                'estimate_contact_stiffness': estimate_contact_stiffness,
                'ignore_skin': opt.ignore_skin,
            }

        small_motions_monitor_param_dict = {
                'ee_motion_threshold': ee_motion_threshold,
                'stopping_force': 15.,
            }

    sac.greedy_to_goal_control_param_dict = greedy_to_goal_control_param_dict
    sac.greedy_to_goal_monitor_param_dict = greedy_to_goal_monitor_param_dict

    sac.reduce_force_control_param_dict = reduce_force_control_param_dict
    sac.reduce_force_monitor_param_dict = reduce_force_monitor_param_dict

    sac.pull_out_control_param_dict = pull_out_control_param_dict
    sac.pull_out_monitor_param_dict = pull_out_monitor_param_dict

    sac.small_motions_control_param_dict = small_motions_control_param_dict
    sac.small_motions_monitor_param_dict = small_motions_monitor_param_dict

    if opt.batch and (not opt.cody):
        rospy.sleep(2.) # wait for arm to reach start JEP
        sac.push_start()
        sac.set_goal()
        #delta_y_reach_in_l = [0, -0.03, -0.1, -0.15, -0.2]
        #delta_y_reach_in_l = [-0.3]
        #delta_y_reach_in_l = [0., -0.1, -0.2]
        if opt.single_reach:
            delta_y_reach_in_l = [0.]
        else:
            delta_y_reach_in_l = [0, -0.1, -0.2, -0.3, -0.4]

        sac.epc_skin.publish_goal(sac.goal_location_world, '/world')
        goal = sac.epc_skin.world_to_torso(sac.goal_location_world)

        overall_dict = {}
        try:
            reached_goal = sac.fixed_base_multiple_reach(goal, delta_y_reach_in_l, 'mpc_qs_1', 0.015)
            overall_dict['pull_out_failed'] = False
        except UserWarning:
            overall_dict['pull_out_failed'] = True
            reached_goal = False

        overall_dict['goal'] = sac.goal_location_world
        overall_dict['reached_goal'] = reached_goal
        print 'FINAL RESULT:', reached_goal
        ut.save_pickle(overall_dict, 'overall_result.pkl')
    else:
        rospy.spin()




