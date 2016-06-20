/*********************************************************************
 *
 * Software License Agreement (BSD License)
 *
 *  Copyright (c) 2013, Daehyung Park (Dr. Charles C. Kemp's HRL, GIT).
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions
 *  are met:
 *
 *   * Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *   * Redistributions in binary form must reproduce the above
 *     copyright notice, this list of conditions and the following
 *     disclaimer in the documentation and/or other materials provided
 *     with the distribution.
 *   * Neither the name of the Daehyung Park nor the names of its
 *     contributors may be used to endorse or promote products derived
 *     from this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 *  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 *  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 *  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 *  COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 *  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 *  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 *  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 *  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 *  LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 *  ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 *  POSSIBILITY OF SUCH DAMAGE.
 *
 * <02/01/2013>
 * This code includes a part of 'simulator_gazebo' package (BSD License)
 * of Willow Garage, Inc.
 * 
 * Daehyung Park is with Dr. Charles C. Kemp's the Healthcare Robotics Lab, 
 * Center for Robotics and Intelligent Machines, Georgia Institute of 
 * Technology. (Contact: deric.park@gatech.edu)
 *
 * We gratefully acknowledge support from DARPA Maximum Mobility
 * and Manipulation (M3) Contract W911NF-11-1-603.
 *********************************************************************/

#include <boost/bind.hpp>
#include <gazebo.hh>
#include <physics/physics.hh>
#include <common/Events.hh>
#include <common/common.hh>
#include <stdio.h>
#include <boost/thread/mutex.hpp>

#include "ros/ros.h"
#include "hrl_msgs/FloatArray.h"
#include "rosgraph_msgs/Clock.h"
#include "sttr_msgs/WrenchArray.h"
#include "geometry_msgs/Pose.h"


namespace gazebo
{   
  class ROSWorldPlugin : public WorldPlugin
  {

    public: ROSWorldPlugin()
    {
      this->world_created_ = false;
    }
    public: ~ROSWorldPlugin()
    {
      // disconnect slots
      event::Events::DisconnectWorldUpdateBegin(this->time_update_event_);
      event::Events::DisconnectWorldUpdateBegin(this->object_update_event_);

      // shutdown ros
      this->rosnode_->shutdown();
      delete this->rosnode_;

    }

    public: void Load(physics::WorldPtr _parent, sdf::ElementPtr /*_sdf*/)
    {
      // setup ros related
      if (!ros::isInitialized()){
        std::string name = "ros_world_plugin_node";
        int argc = 0;
        ros::init(argc,NULL,name,ros::init_options::NoSigintHandler);
      }
      else{
        ROS_WARN("ROS World Plugin>> Something other than this ros_world plugin started ros::init(...), clock may not be published properly.");
      }

      this->rosnode_ = new ros::NodeHandle("ROSWorldNode");

      this->lock_.lock();
      if (this->world_created_)
      {
        this->lock_.unlock();
        return;
      }

      // set flag to true and load this plugin
      this->world_created_ = true;
      this->lock_.unlock();

      this->world = physics::get_world(_parent->GetName());
      if (!this->world)
      {
        ROS_FATAL("cannot load gazebo ros world server plugin, physics::get_world() fails to return world");
        return;
      }

      gzdbg << "********************************" << "\n";

      /// \brief advertise all services
      this->AdvertiseServices();

      // hooks for applying forces, publishing simtime on /clock
      this->time_update_event_   = event::Events::ConnectWorldUpdateBegin(boost::bind(&ROSWorldPlugin::publishSimTime,this));
      this->object_update_event_ = event::Events::ConnectWorldUpdateBegin(boost::bind(&ROSWorldPlugin::publishObjectInfo,this));

      darci_wrench_msg_available = 0;
      lift_box_wrench_msg_available = 0;

      gzdbg << "********************************" << "\n";
    }

    /// \brief advertise services
    void AdvertiseServices()
    {
      // publish clock for simulated ros time
      this->pub_clock_         = this->rosnode_->advertise<rosgraph_msgs::Clock>("/clock",1/0.0005);

      // publish object state 
      this->pub_leg_angles_        = this->rosnode_->advertise<hrl_msgs::FloatArray>("/gazebo/leg_angles", 100);

      this->pub_sprjt_        = this->rosnode_->advertise<sttr_msgs::WrenchArray>("/gazebo/sprjt", 100);

      this->pub_spr2ft_        = this->rosnode_->advertise<sttr_msgs::WrenchArray>("/gazebo/spr2ft", 100);

      this->pub_ragdollft_rleg_        = this->rosnode_->advertise<sttr_msgs::WrenchArray>("/gazebo/ragdollft_rleg", 100);

      this->pub_darcift_larm_        = this->rosnode_->advertise<sttr_msgs::WrenchArray>("/gazebo/darcift_larm", 100);

      this->pub_darcift_rarm_        = this->rosnode_->advertise<sttr_msgs::WrenchArray>("/gazebo/darcift_rarm", 100);

      this->pub_darci_larm_ee_cart_        = this->rosnode_->advertise<geometry_msgs::Pose>("/gazebo/darci_larm_ee_cart", 100);

      this->pub_darci_rarm_ee_cart_        = this->rosnode_->advertise<geometry_msgs::Pose>("/gazebo/darci_rarm_ee_cart", 100);

      this->sub_darci_wrench_ = this->rosnode_->subscribe<sttr_msgs::WrenchArray>("/gazebo/darci_wrench", 1000, &ROSWorldPlugin::ApplydarciWrenchCallback, this );

      this->sub_lift_box_wrench_ = this->rosnode_->subscribe<sttr_msgs::WrenchArray>("/gazebo/lift_box_wrench", 1000, &ROSWorldPlugin::ApplyliftboxWrenchCallback, this );

      this->sub_ragdoll_wrench_ = this->rosnode_->subscribe<sttr_msgs::WrenchArray>("/gazebo/ragdoll_wrench", 1000, &ROSWorldPlugin::ApplyragdollWrenchCallback, this );

      this->pub_ragdoll_leg_0_cart_        = this->rosnode_->advertise<geometry_msgs::Pose>("/gazebo/ragdoll_leg_0_cart", 100);

      // set param for use_sim_time if not set by user alread
      this->rosnode_->setParam("/use_sim_time", true);
    }

    void publishSimTime()
    {
      common::Time currentTime = this->world->GetSimTime();
      rosgraph_msgs::Clock ros_time_;
      ros_time_.clock.fromSec(currentTime.Double());
      //  publish time to ros
      this->pub_clock_.publish(ros_time_);
    }

    void ApplydarciWrenchCallback(const sttr_msgs::WrenchArray::ConstPtr& msg)
    {
      if (msg->frame_names[0].find("none") == std::string::npos){
        darci_force_location = msg->frame_names[0];
        darci_rarm_force_vector = math::Vector3(msg->force_x[0],msg->force_y[0],msg->force_z[0]);
        //darci_rarm_force_vector = math::Vector3(msg->force_x[1],msg->force_y[1],msg->force_z[1]);
        darci_wrench_msg_available = 1;
      }
      else {
        darci_wrench_msg_available = 0;
      }
    }

    void ApplyliftboxWrenchCallback(const sttr_msgs::WrenchArray::ConstPtr& msg)
    {
      if (msg->frame_names[0].find("none") == std::string::npos){
        //lift_box_force_location = msg->frame_names[0];
        lift_box_force_vector = math::Vector3(msg->force_x[0],msg->force_y[0],msg->force_z[0]);
        lift_box_wrench_msg_available = 1;
      }
      else {
        lift_box_wrench_msg_available = 0;
      }
    }

    void ApplyragdollWrenchCallback(const sttr_msgs::WrenchArray::ConstPtr& msg)
    {
      if (msg->frame_names[0].find("none") == std::string::npos){
        //lift_box_force_location = msg->frame_names[0];
        ragdoll_force_vector = math::Vector3(msg->force_x[0],msg->force_y[0],msg->force_z[0]);
        ragdoll_wrench_msg_available = 1;
      }
      else {
        ragdoll_wrench_msg_available = 0;
      }
    }

    void publishObjectInfo()
    {
      //this->lock_.lock();
      physics::Model_V models_;
      unsigned int nModel = 0;
      physics::Joint_V joints_;
      std::string jointName;
      physics::LinkPtr link_;
      //math::Angle hip_angle;
      //math::Angle knee_angle;
      double leg_angle;
      double hip_angle;
      double knee_angle;
      double shoulder_angle;
      double elbow_angle;
 
      physics::JointWrench spr_jt;
      math::Vector3 spr_forces;
      math::Vector3 spr_torques; 

      physics::JointWrench spr2_ft;
      math::Vector3 spr2_forces;
      math::Vector3 spr2_torques;

      physics::JointWrench ragdoll_ft_rleg;
      math::Vector3 ragdoll_forces_rleg;
      math::Vector3 ragdoll_torques_rleg;

      physics::JointWrench darci_ft_larm;
      math::Vector3 darci_forces_larm;
      math::Vector3 darci_torques_larm;

      physics::JointWrench darci_ft_rarm;
      math::Vector3 darci_forces_rarm;
      math::Vector3 darci_torques_rarm;
    
      math::Pose ragdoll_leg_0_cart;
      math::Pose darci_larm_ee_cart;
      math::Pose darci_rarm_ee_cart;
       
      models_ = this->world->GetModels();
      nModel = this->world->GetModelCount();

      for (unsigned int i = 0; i < nModel; i++){
        std::string modelName = models_[i]->GetName();
        if (modelName.find("ragdoll") != std::string::npos){

          //ragdoll_leg_0_cart = models_[i]->GetLink("r_leg")->GetWorldPose();
          ragdoll_leg_0_cart = models_[i]->GetLink("r_thigh")->GetWorldPose();
          
          joints_ = models_[i]->GetJoints();
          for (unsigned int j = 0; j < joints_.size(); j++){
            std::string jointName = joints_[j]->GetName();
            if (jointName.find("r_leg") != std::string::npos){
              ragdoll_ft_rleg = joints_[j]->GetForceTorque(0);
              ragdoll_forces_rleg = ragdoll_ft_rleg.body2Force;
              ragdoll_torques_rleg = ragdoll_ft_rleg.body2Torque;
              //gzdbg << "Darci Forces: " << darci_forces.z << "\n";
              this->pub_ragdollft_rleg_array_.frame_names.push_back(jointName);
              this->pub_ragdollft_rleg_array_.force_x.push_back(ragdoll_forces_rleg.x);
              this->pub_ragdollft_rleg_array_.force_y.push_back(ragdoll_forces_rleg.y);
              this->pub_ragdollft_rleg_array_.force_z.push_back(ragdoll_forces_rleg.z);
              this->pub_ragdollft_rleg_array_.torque_x.push_back(ragdoll_torques_rleg.x);
              this->pub_ragdollft_rleg_array_.torque_y.push_back(ragdoll_torques_rleg.y);
              this->pub_ragdollft_rleg_array_.torque_z.push_back(ragdoll_torques_rleg.z);
            }

            //if (jointName.find("r_leg_joint") != std::string::npos){
            //  leg_angle = joints_[j]->GetAngle(0).Degree()*(-1);
            //}
            if (jointName.find("r_thigh_joint") != std::string::npos){
              hip_angle = joints_[j]->GetAngle(0).Degree()*(-1);
            }
            if (jointName.find("r_shin_joint") != std::string::npos){
              knee_angle = joints_[j]->GetAngle(0).Degree()*(-1)+hip_angle;
              //gzdbg << "knee angle relative: " << joints_[j]->GetAngle(0).Degree()*(-1) << "\n";
            }
            //if (jointName.find("r_arm_joint") != std::string::npos){
            //  shoulder_angle = joints_[j]->GetAngle(0).Degree()*(-1);
            //}
            //if (jointName.find("r_wrist_joint") != std::string::npos){
            //  elbow_angle = joints_[j]->GetAngle(0).Degree()*(-1)+hip_angle;
              //gzdbg << "elbow angle relative: " << joints_[j]->GetAngle(0).Degree()*(-1) << "\n";
            //}
          }
          //if (ragdoll_wrench_msg_available == 1){
          //  link_ = models_[i]->GetLink("r_leg");
          //  math::Vector3 rel_pos = math::Vector3(-0.4,0.,0.);
          //  link_->AddForceAtRelativePosition(ragdoll_force_vector,rel_pos);
          //}
       
        }
        if (modelName.find("simple_prismatic_robot") != std::string::npos){
          joints_ = models_[i]->GetJoints();
          for (unsigned int j = 0; j < joints_.size(); j++){
            std::string jointName = joints_[j]->GetName();
            if (jointName.find("revolute_joint") != std::string::npos){
              spr_jt = joints_[j]->GetForceTorque(0);
              spr_forces = spr_jt.body2Force;
              spr_torques = spr_jt.body2Torque;
              this->pub_sprjt_array_.frame_names.push_back(jointName);
              this->pub_sprjt_array_.force_x.push_back(spr_forces.x);
              this->pub_sprjt_array_.force_y.push_back(spr_forces.y);
              this->pub_sprjt_array_.force_z.push_back(spr_forces.z);
              this->pub_sprjt_array_.torque_x.push_back(spr_torques.x);
              this->pub_sprjt_array_.torque_y.push_back(spr_torques.y);
              this->pub_sprjt_array_.torque_z.push_back(spr_torques.z);
            }
            else if (jointName.find("robot_joint") != std::string::npos){
              spr_jt = joints_[j]->GetForceTorque(0);
              spr_forces = spr_jt.body2Force;
              spr_torques = spr_jt.body2Torque;
              this->pub_sprjt_array_.frame_names.push_back(jointName);
              this->pub_sprjt_array_.force_x.push_back(spr_forces.x);
              this->pub_sprjt_array_.force_y.push_back(spr_forces.y);
              this->pub_sprjt_array_.force_z.push_back(spr_forces.z);
              this->pub_sprjt_array_.torque_x.push_back(spr_torques.x);
              this->pub_sprjt_array_.torque_y.push_back(spr_torques.y);
              this->pub_sprjt_array_.torque_z.push_back(spr_torques.z);
            }
          }
        }
        if (modelName.find("simple_prismatic_robot_2") != std::string::npos){
          joints_ = models_[i]->GetJoints();
          for (unsigned int j = 0; j < joints_.size(); j++){
            std::string jointName = joints_[j]->GetName();
            if (jointName.find("robot_joint_2") != std::string::npos){
              spr2_ft = joints_[j]->GetForceTorque(0);
              spr2_forces = spr2_ft.body2Force;
              spr2_torques = spr2_ft.body2Torque;
              this->pub_spr2ft_array_.frame_names.push_back(jointName);
              this->pub_spr2ft_array_.force_x.push_back(spr2_forces.x);
              this->pub_spr2ft_array_.force_y.push_back(spr2_forces.y);
              this->pub_spr2ft_array_.force_z.push_back(spr2_forces.z);
              this->pub_spr2ft_array_.torque_x.push_back(spr2_torques.x);
              this->pub_spr2ft_array_.torque_y.push_back(spr2_torques.y);
              this->pub_spr2ft_array_.torque_z.push_back(spr2_torques.z);
            }
            else if (jointName.find("robot_joint") != std::string::npos){
              spr2_ft = joints_[j]->GetForceTorque(0);
              spr2_forces = spr2_ft.body2Force;
              spr2_torques = spr2_ft.body2Torque;
              this->pub_spr2ft_array_.frame_names.push_back(jointName);
              this->pub_spr2ft_array_.force_x.push_back(spr2_forces.x);
              this->pub_spr2ft_array_.force_y.push_back(spr2_forces.y);
              this->pub_spr2ft_array_.force_z.push_back(spr2_forces.z);
              this->pub_spr2ft_array_.torque_x.push_back(spr2_torques.x);
              this->pub_spr2ft_array_.torque_y.push_back(spr2_torques.y);
              this->pub_spr2ft_array_.torque_z.push_back(spr2_torques.z);
            }
          }
        }
        if (modelName.find("lift_box") != std::string::npos){
          if (lift_box_wrench_msg_available == 1){
            link_ = models_[i]->GetLink("lift_box");
            math::Vector3 rel_pos = math::Vector3(0.,0.,0.);
            link_->AddForceAtRelativePosition(lift_box_force_vector,rel_pos);
          }
        }
        if (modelName.find("Darci") != std::string::npos){
          joints_ = models_[i]->GetJoints();
          for (unsigned int j = 0; j < joints_.size(); j++){
            std::string jointName = joints_[j]->GetName();
            if (jointName.find("left_arm_j6") != std::string::npos){
              darci_ft_larm = joints_[j]->GetForceTorque(0);
              darci_forces_larm = darci_ft_larm.body2Force;
              darci_torques_rarm = darci_ft_larm.body2Torque;
              //gzdbg << "Darci Forces: " << darci_forces.z << "\n";
              this->pub_darcift_larm_array_.frame_names.push_back(jointName);
              this->pub_darcift_larm_array_.force_x.push_back(darci_forces_larm.x);
              this->pub_darcift_larm_array_.force_y.push_back(darci_forces_larm.y);
              this->pub_darcift_larm_array_.force_z.push_back(darci_forces_larm.z);
              this->pub_darcift_larm_array_.torque_x.push_back(darci_torques_larm.x);
              this->pub_darcift_larm_array_.torque_y.push_back(darci_torques_larm.y);
              this->pub_darcift_larm_array_.torque_z.push_back(darci_torques_larm.z);
            }
            if (jointName.find("right_arm_j6") != std::string::npos){
              darci_ft_rarm = joints_[j]->GetForceTorque(0);
              darci_forces_rarm = darci_ft_rarm.body2Force;
              darci_torques_rarm = darci_ft_rarm.body2Torque;
              //gzdbg << "Darci Forces: " << darci_forces.z << "\n";
              this->pub_darcift_rarm_array_.frame_names.push_back(jointName);
              this->pub_darcift_rarm_array_.force_x.push_back(darci_forces_rarm.x);
              this->pub_darcift_rarm_array_.force_y.push_back(darci_forces_rarm.y);
              this->pub_darcift_rarm_array_.force_z.push_back(darci_forces_rarm.z);
              this->pub_darcift_rarm_array_.torque_x.push_back(darci_torques_rarm.x);
              this->pub_darcift_rarm_array_.torque_y.push_back(darci_torques_rarm.y);
              this->pub_darcift_rarm_array_.torque_z.push_back(darci_torques_rarm.z);
            }
          }
          if (darci_wrench_msg_available == 1){
            link_ = models_[i]->GetLink("handmount_RIGHT");
            //math::Vector3 rel_pos = math::Vector3(0.,0.,0.14);
            math::Vector3 rel_pos = math::Vector3(0.,0.,-0.1);
            //force_vector = math::Vector3(0,0,1);
            link_->AddForceAtRelativePosition(darci_rarm_force_vector,rel_pos);
            //link_ = models_[i]->GetLink("r_forearm_roll_link");
            //rel_pos = math::Vector3(0.,0.,0.209);
            //force_vector = math::Vector3(0,0,1);
            //link_->AddForceAtRelativePosition(crona_rarm_force_vector,rel_pos);
          }
          darci_rarm_ee_cart = models_[i]->GetLink("handmount_RIGHT")->GetWorldPose();
          darci_larm_ee_cart = models_[i]->GetLink("handmount_LEFT")->GetWorldPose();
        } 
      }
      //this->leg_angles_array.data.push_back(shoulder_angle);
      //this->leg_angles_array.data.push_back(elbow_angle);
      //this->leg_angles_array.data.push_back(leg_angle);
      this->leg_angles_array.data.push_back(hip_angle);
      this->leg_angles_array.data.push_back(knee_angle);

      this->pub_leg_angles_.publish(this->leg_angles_array);
      this->leg_angles_array.data.clear();

      this->pub_sprjt_.publish(this->pub_sprjt_array_);
      this->pub_sprjt_array_.frame_names.clear();
      this->pub_sprjt_array_.force_x.clear();
      this->pub_sprjt_array_.force_y.clear();
      this->pub_sprjt_array_.force_z.clear();
      this->pub_sprjt_array_.torque_x.clear();
      this->pub_sprjt_array_.torque_y.clear();
      this->pub_sprjt_array_.torque_z.clear();

      this->pub_spr2ft_.publish(this->pub_spr2ft_array_);
      this->pub_spr2ft_array_.frame_names.clear();
      this->pub_spr2ft_array_.force_x.clear();
      this->pub_spr2ft_array_.force_y.clear();
      this->pub_spr2ft_array_.force_z.clear();
      this->pub_spr2ft_array_.torque_x.clear();
      this->pub_spr2ft_array_.torque_y.clear();
      this->pub_spr2ft_array_.torque_z.clear();

      this->pub_ragdollft_rleg_.publish(this->pub_ragdollft_rleg_array_);
      this->pub_ragdollft_rleg_array_.frame_names.clear();
      this->pub_ragdollft_rleg_array_.force_x.clear();
      this->pub_ragdollft_rleg_array_.force_y.clear();
      this->pub_ragdollft_rleg_array_.force_z.clear();
      this->pub_ragdollft_rleg_array_.torque_x.clear();
      this->pub_ragdollft_rleg_array_.torque_y.clear();
      this->pub_ragdollft_rleg_array_.torque_z.clear();

      this->pub_darcift_larm_.publish(this->pub_darcift_larm_array_);
      this->pub_darcift_larm_array_.frame_names.clear();
      this->pub_darcift_larm_array_.force_x.clear();
      this->pub_darcift_larm_array_.force_y.clear();
      this->pub_darcift_larm_array_.force_z.clear();
      this->pub_darcift_larm_array_.torque_x.clear();
      this->pub_darcift_larm_array_.torque_y.clear();
      this->pub_darcift_larm_array_.torque_z.clear();

      this->pub_darcift_rarm_.publish(this->pub_darcift_rarm_array_);
      this->pub_darcift_rarm_array_.frame_names.clear();
      this->pub_darcift_rarm_array_.force_x.clear();
      this->pub_darcift_rarm_array_.force_y.clear();
      this->pub_darcift_rarm_array_.force_z.clear();
      this->pub_darcift_rarm_array_.torque_x.clear();
      this->pub_darcift_rarm_array_.torque_y.clear();
      this->pub_darcift_rarm_array_.torque_z.clear();

      this->pub_ragdoll_leg_0_cart_msg.position.x = ragdoll_leg_0_cart.pos.x;
      this->pub_ragdoll_leg_0_cart_msg.position.y = ragdoll_leg_0_cart.pos.y;
      this->pub_ragdoll_leg_0_cart_msg.position.z = ragdoll_leg_0_cart.pos.z;
      this->pub_ragdoll_leg_0_cart_.publish(this->pub_ragdoll_leg_0_cart_msg);

      this->pub_darci_larm_ee_cart_msg.position.x = darci_larm_ee_cart.pos.x;
      this->pub_darci_larm_ee_cart_msg.position.y = darci_larm_ee_cart.pos.y;
      this->pub_darci_larm_ee_cart_msg.position.z = darci_larm_ee_cart.pos.z;
      this->pub_darci_rarm_ee_cart_msg.position.x = darci_rarm_ee_cart.pos.x;
      this->pub_darci_rarm_ee_cart_msg.position.y = darci_rarm_ee_cart.pos.y;
      this->pub_darci_rarm_ee_cart_msg.position.z = darci_rarm_ee_cart.pos.z;
      this->pub_darci_larm_ee_cart_.publish(this->pub_darci_larm_ee_cart_msg);
      this->pub_darci_rarm_ee_cart_.publish(this->pub_darci_rarm_ee_cart_msg);
      //this->pub_darci_larm_ee_cart_msg.clear();
      //this->pub_darci_rarm_ee_cart_msg.clear();
  
    }

    // 
    private: physics::WorldPtr world;
    private: event::ConnectionPtr time_update_event_;
    private: event::ConnectionPtr object_update_event_;

    /// \brief A mutex to lock access to fields that are used in ROS message callbacks
    private: boost::mutex lock_;

    /// \brief utilites for checking incoming string URDF/XML/Param
    bool world_created_;

    ros::NodeHandle* rosnode_;

    // ROS Publisher & Subscriber
    ros::Publisher pub_clock_;
    ros::Publisher pub_leg_angles_;
    ros::Publisher pub_sprjt_;
    ros::Publisher pub_spr2ft_;
    ros::Publisher pub_ragdollft_rleg_;
    ros::Publisher pub_darcift_larm_;
    ros::Publisher pub_darcift_rarm_;
    ros::Publisher pub_ragdoll_leg_0_cart_;
    ros::Publisher pub_darci_larm_ee_cart_;
    ros::Publisher pub_darci_rarm_ee_cart_;
    ros::Subscriber sub_darci_wrench_;
    ros::Subscriber sub_lift_box_wrench_;
    ros::Subscriber sub_ragdoll_wrench_;

    hrl_msgs::FloatArray leg_angles_array;
    sttr_msgs::WrenchArray pub_sprjt_array_;
    sttr_msgs::WrenchArray pub_spr2ft_array_;
    sttr_msgs::WrenchArray pub_ragdollft_rleg_array_;
    sttr_msgs::WrenchArray pub_darcift_larm_array_;
    sttr_msgs::WrenchArray pub_darcift_rarm_array_;
    geometry_msgs::Pose pub_ragdoll_leg_0_cart_msg;
    geometry_msgs::Pose pub_darci_larm_ee_cart_msg;
    geometry_msgs::Pose pub_darci_rarm_ee_cart_msg;

    bool darci_wrench_msg_available;
    std::string darci_force_location;
    math::Vector3 darci_larm_force_vector;
    math::Vector3 darci_rarm_force_vector;

    bool lift_box_wrench_msg_available;
    std::string lift_box_force_location;
    math::Vector3 lift_box_force_vector;

    bool ragdoll_wrench_msg_available;
    std::string ragdoll_force_location;
    math::Vector3 ragdoll_force_vector;

  };

  // Register this plugin with the simulator
  GZ_REGISTER_WORLD_PLUGIN(ROSWorldPlugin)
}

