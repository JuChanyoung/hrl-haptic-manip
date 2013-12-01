#!/usr/bin/env python

import math
import numpy as np
import threading
import copy
import sys

import roslib
roslib.load_manifest("hrl_tactile_controller")
import rospy

import hrl_haptic_manipulation_in_clutter_msgs.msg as haptic_msgs
import hrl_haptic_manipulation_in_clutter_srvs.srv as haptic_srvs
import geometry_msgs.msg
import std_msgs.msg

import haptic_mpc_util
import multiarray_to_matrix


class HapticMPCMonitor():
  
  def __init__(self, node_name="haptic_mpc_monitor"):
    rospy.loginfo("HapticMPCMonitor: Initialised Haptic MPC monitoring node")
    # Set up all ros comms to start with
    self.node_name = node_name 
    
    self.mpc_state_pub = None
    self.rate = 100.0 # 100 Hz.
    self.msg_seq = 0 # Sequence counter
    
    self.state_lock = threading.RLock()
    self.traj_lock = threading.RLock()
    self.goal_lock = threading.RLock()
    
    # Jacobian MultiArray to Matrix converter
    self.ma_to_m = multiarray_to_matrix.MultiArrayConverter()
    
    self.last_goal_pos = None
    self.goal_pos = None # Current goal pose
    self.goal_orient_quat = None
    self.goal_orient_cart = None
    self.traj_pos = None # Current trajectory waypoint pose
    self.traj_orient_quat = None
    self.traj_orient_cart = None
    self.traj_pose_list = [] # List of trajectory waypoints
    
    self.end_effector_pos = None
    self.end_effector_orient_quat = None
    
    self.skin_data = None
    
    self.time_started = None # Time 
    self.attempt_timeout = 120.0 # Seconds given before a reach attempt times out.
    self.attempt_timed_out = False # state variable to ensure that it only stops logging once, etc.
    self.already_exceeded_force_limits = False
    self.reached_goal = False
    
    # Thresholds:
    self.dist_to_goal_threshold = 0.015
    self.max_force_threshold = 15.0 # default
    
    self.initComms()
    self.initParamsFromServer()
  
  # Store the current trajectory goal sent to the trajectory generator.
  # Expects a PoseStamped message
  def goalPoseCallback(self, msg):
    with self.goal_lock:
      self.time_started = rospy.Time.now()
      self.goal_pos = np.matrix([[msg.pose.position.x], [msg.pose.position.y], [msg.pose.position.z]])
      self.goal_orient_quat = [msg.pose.orientation.x, msg.pose.orientation.y, msg.pose.orientation.z, msg.pose.orientation.w]    
  
  # Store the current trajectory waypoint, generated by the trajectory generator.
  # Expects a PoseStamped message
  def trajPoseCallback(self, msg):
    with self.traj_lock:
      self.traj_pos = np.matrix([[msg.pose.position.x], [msg.pose.position.y], [msg.pose.position.z]])
      self.traj_orient_quat = [msg.pose.orientation.x, msg.pose.orientation.y, msg.pose.orientation.z, msg.pose.orientation.w]  
  
  # Store the robot state  
  def robotStateCallback(self, msg):
    with self.state_lock:
      self.msg = msg
      self.joint_names = msg.joint_names
      self.joint_angles = list(msg.joint_angles) 
      self.desired_joint_angles = list(msg.desired_joint_angles)
      self.joint_velocities= list(msg.joint_velocities)
      self.joint_stiffness = list(msg.joint_stiffness)
      self.joint_damping = list(msg.joint_damping)
      
      self.end_effector_pos = np.matrix([[msg.hand_pose.position.x], [msg.hand_pose.position.y], [msg.hand_pose.position.z]])
      self.end_effector_orient_quat = [msg.hand_pose.orientation.x, msg.hand_pose.orientation.y, msg.hand_pose.orientation.z, msg.hand_pose.orientation.w]
      
      self.skin_data = msg.skins
 
      self.Je = self.ma_to_m.multiArrayToMatrixList(msg.end_effector_jacobian)
      self.Jc = self.ma_to_m.multiArrayToMatrixList(msg.contact_jacobians)

  # Returns a header type with the current timestamp.
  # TODO: Add a frameid
  def getMessageHeader(self):
    header = std_msgs.msg.Header()
    header.stamp = rospy.get_rostime()
    
    return header
  
  def initParamsFromServer(self):
    base_path = '/haptic_mpc'
    control_path = '/control_params'
    
    rospy.loginfo("HapticMPC: Initialising controller parameters from server. Path: %s" % (base_path+control_path))
    # Force limits for the controller.
    max_force = rospy.get_param(base_path + control_path + '/stopping_force') # Max force allowed by the controller
    self.max_force_threshold = max_force 
    self.attempt_timeout = rospy.get_param(base_path + control_path + '/timeout')
    
  def initComms(self, node_name="haptic_mpc_monitor"):
    rospy.init_node(node_name)
    self.mpc_state_pub = rospy.Publisher("/haptic_mpc/mpc_state", haptic_msgs.HapticMpcState)
    self.robot_state_sub = rospy.Subscriber("/haptic_mpc/robot_state", haptic_msgs.RobotHapticState, self.robotStateCallback)
    self.traj_sub = rospy.Subscriber("/haptic_mpc/traj_pose", geometry_msgs.msg.PoseStamped, self.trajPoseCallback)
    self.goal_sub = rospy.Subscriber("/haptic_mpc/goal_pose", geometry_msgs.msg.PoseStamped, self.goalPoseCallback)
    self.mpc_logging_srv = rospy.ServiceProxy('haptic_mpc_logger_state', haptic_srvs.HapticMPCLogging)
  
  def publishMPCState(self):
    # Set up lists of strings to be published
    state_list = []
    error_list = []
    
    start_logging = False
    stop_logging = False
    
    # Get copies of the current goal, trajectory waypoint, and relevant state information
    with self.goal_lock:
      goal_pos = copy.copy(self.goal_pos)
    
    with self.traj_lock:
      traj_pos = copy.copy(self.traj_pos)
    
    with self.state_lock:
      current_pos = copy.copy(self.end_effector_pos)
      current_skin_state = copy.copy(self.skin_data) 
    
    # Now perform state monitoring checks.  
    # Check if successfully reached goal
    if goal_pos == None:
      state_list.append("waiting_for_goal")
    if traj_pos == None:
      state_list.append("waiting_for_waypoint")

    if goal_pos != None and traj_pos != None: # The monitor (and controller) won't start until robot state info is heard. It may not have a goal however.
                     
      if self.checkIfGoalChanged(self.last_goal_pos, goal_pos):
        start_logging = True # If we have an updated goal position from the last iteration, request logging start.
        
      dist_to_goal_3d = np.linalg.norm(goal_pos - current_pos)
      dist_to_goal_2d = np.linalg.norm(goal_pos[0:2] - current_pos[0:2])
      time_since_start = rospy.Time.now() - self.time_started
#      print "*********************\ngoal_pos"
#      print goal_pos
#      print "curr_pos"
#      print current_pos
#      print "dist_to_goal"
#      print dist_to_goal_2d
      if dist_to_goal_2d < self.dist_to_goal_threshold:
        if self.reached_goal == False:
          rospy.logwarn("HapticMPCMonitor: Reached goal")
          self.reached_goal = True
          stop_logging = True
          
        state_list.append("reached_goal")
      # Check if unsuccessful - based on a reach duration timeout.
      elif time_since_start.to_sec() > self.attempt_timeout:
        if self.attempt_timed_out == False: # Only do this one time 
          rospy.logwarn("HapticMPCMonitor: Timed out in reaching goal. Elapsed: %s (%s)" % (str(time_since_start.to_sec()), str(self.attempt_timeout)))
          error_list.append('attempt_timeout')
          state_list.append('unsuccessful')
          self.attempt_timed_out = True
          stop_logging = True
      else:
        self.attempt_timed_out = False # reset state variable
      
      # Check if forces too high
      max_force = 0
      min_force = sys.maxint
      for taxel_array in current_skin_state:
        for i in range(len(taxel_array.values_x)):
          force_mag = np.sqrt(taxel_array.values_x[i]**2 + taxel_array.values_y[i]**2 + taxel_array.values_z[i]**2)
          if force_mag > max_force:
            max_force = force_mag
          elif force_mag < min_force:
            min_force = force_mag 

      if max_force > self.max_force_threshold:
        if self.already_exceeded_force_limits == False:
          rospy.logerr("HapticMPCMonitor: Max force exceeded: %s (%s)" % (str(max_force),str(self.max_force_threshold)))
          stop_logging = True
          self.already_exceeded_force_limits = True
        error_list.append('max_force_exceeded')      
      else:
        self.already_exceeded_force_limits = False
      
      # TODO: Add min distance exceded case - if min_force < min_threshold AND type == 'dist', etc.
      
      # TODO: Check if stuck
      
      # End of if statement. Update last_goal. This needs to be inside this loop as there is a delay between hearing a goal and hearing a trajectory waypoint.
      self.last_goal_pos = copy.copy(self.goal_pos) 
    
    # Publish state msg
    msg = haptic_msgs.HapticMpcState()
    msg.header = self.getMessageHeader()
    msg.state = state_list
    msg.error = error_list
    self.mpc_state_pub.publish(msg)

    # Do this after publishing the message with current state so it doesn't block.
    if start_logging == True:
      rospy.logwarn("HapticMPCMonitor: Starting logging")
      self.requestLoggingStart()
    elif stop_logging == True:
      rospy.logwarn("HapticMPCMonitor: Stopping logging")
      self.requestLoggingStop()
  
  def checkIfGoalChanged(self, old_goal, new_goal):
    if old_goal == None and new_goal == None: # No goal has been heard yet - still the starting values
      return False
    if old_goal == None and new_goal != None: # The new goal has just been set, but the last goal hasn't been updated yet
      return True
    if (old_goal == new_goal).all(): # The values of the goal pos are all the same
      return False
    return True # Values are different - must have a new goal.
    
  
  def requestLoggingStart(self):
    try:
      log_dir = ""
      log_file = "reach_from_start_to_goal_data_log"
      rospy.logwarn("HapticMPCMonitor: Requested logging start: %s/%s" % (log_dir, log_file))
      response = self.mpc_logging_srv("start", log_dir, log_file)
    except rospy.ServiceException, e:
      rospy.logwarn("HapticMPCMonitor: Service did not process request: %s" % str(e))
    
  def requestLoggingStop(self):
    try:
      log_dir = ""
      log_file = "reach_from_start_to_goal_data_log"
      rospy.logwarn("HapticMPCMonitor: Requested logging stop.")
      response = self.mpc_logging_srv("stop", log_dir, log_file)
      #print "TRIED TO WRITE LOGS TO FILE"
    except rospy.ServiceException, e:
      rospy.logwarn("HapticMPCMonitor:Service did not process request: %s" % str(e))
  
  def start(self):
    rospy.loginfo("HapticMPCMonitor: Starting Haptic MPC monitor")
    rate = rospy.Rate(self.rate) # 100Hz, nominally.
    
    rospy.loginfo("HapticMPCMonitor: Waiting for Robot Haptic State message")
    rospy.wait_for_message("/haptic_mpc/robot_state", haptic_msgs.RobotHapticState)
    rospy.loginfo("HapticMPCMonitor: Got Robot Haptic State message")
    
    rospy.loginfo("HapticMPCMonitor: Beginning publishing state")
    while not rospy.is_shutdown():
      self.publishMPCState()
#      rospy.spin() # Blocking spin for debug/dev purposes
      rate.sleep()


if __name__ == "__main__":
  monitor = HapticMPCMonitor()
  monitor.start()