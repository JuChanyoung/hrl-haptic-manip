import numpy as np
h_goal = np.matrix([-0.4, 1.0,0.2]).T
linkage_offset_from_ground = np.matrix([0., 0., 0.2]).T
ee_location = np.matrix([1.0, 0., 0.2]).T
mu = np.matrix([0, 8, 0, 0.08, 0, 0.08, 0, 0.08]).T

bod_shapes = ['cylinder', 'cylinder', 'cylinder']
bod_dimensions = [[0.05, 0.05, 0.4], [0.05, 0.05, 0.4], [0.05, 0.05, 0.2]]
bod_com_position = [[0.2, 0, 0.2],[0.6, 0, 0.2], [0.9, 0, 0.2]]
bod_color = [[1, 1, 0, 1], [0, 0, 1, 1], [1, 0.5, 0,1]]
bod_mass = [None, None, None]
bod_density =[10, 10, 10]
bod_rotation = [[0, 0, -1, 0, 1, 0, 1, 0, 0], [0, 0, -1, 0, 1, 0, 1, 0, 0], [0, 0, -1, 0, 1, 0, 1, 0, 0]]
bod_inertia = [None, None, None]
bod_names = ['link1', 'link2', 'link3']
bodies ={'shapes':bod_shapes, 'dim':bod_dimensions, 'com_pos':bod_com_position, 
       'color':bod_color, 'mass':bod_mass, 'density':bod_density, 
       'rotation':bod_rotation, 'inertia':bod_inertia, 'name':bod_names}


b_geom_bodies_ind = [0, 1, 2, None]
#b_geom_name = ['link1', 'link2', 'link3', 'ground']
b_geom_name = ['link', 'link', 'link', 'ground']
b_geom_dim = [None, None, None, [20, 20, 0.1]]
b_geom_shape = [None, None,None, 'cube']
b_geom_pos = [None, None, None, [0, 0, -0.05]]
b_geometries = {'body':b_geom_bodies_ind, 'name':b_geom_name, 'dim':b_geom_dim,
              'shape':b_geom_shape, 'pos':b_geom_pos}


b_jt_q_ind = [True, True, True]
b_jt_bodies = [[0,-1],[1,0], [2,1]]
b_jt_type = ['revolute', 'revolute', 'revolute']
b_jt_anchor = [[0, 0, 0.2], [0.4, 0, 0.2], [0.8, 0, 0.2]]
b_jt_axis = [[0,0,1],[0,0,1], [0,0,1]]
b_jt_vis_size = [[0.07, 0.07, 0.07], [0.07, 0.07, 0.07], [0.07, 0.07, 0.07]]
b_jt_vis_color = [[1, 0, 0, 1], [1, 0, 0, 1], [1, 0, 0, 1]]
b_jt_feedback = [0, 0, 0]

b_jts = {'bodies':b_jt_bodies, 'jt_type':b_jt_type, 'anchor':b_jt_anchor, 'axis':b_jt_axis,
          'vis_size':b_jt_vis_size, 'vis_color':b_jt_vis_color, 'feedback':b_jt_feedback}



obs_shapes = ['cube', 'cube', 'cylinder', 'cylinder', 'cylinder', 'cylinder', 'cylinder', 'cylinder']
obs_dimensions = [[0.1, 0.1, 0.01], [0.1, 0.1, 0.39], [0.1, 0.1, 0.01], [0.1, 0.1, 0.39], 
                  [0.1, 0.1, 0.01], [0.1, 0.1, 0.39], [0.1, 0.1, 0.01], [0.1, 0.1, 0.39]]
# obs_com_position = [[3.2, 3.2, 0.05], [3.2, 3.2, 1.05], [2, 3.4, 0.05], [2, 3.4, 0.8], 
#                     [0.5, 3.5, 0.05], [0.5, 3.5, 0.8], [0.5, 2.2, 0.05], [0.5, 2.2, 0.8]]
obs_com_position = [[0.5, 0.8, 0.005], [0.5, 0.8, 0.39/2+0.01], [0.0, 0.54, 0.005], [0.0, 0.54, 0.39/2+0.01], 
                    [0.1, 0.6, 0.005], [0.1, 0.6, 0.39/2+0.01], [-0.2, 0.7, 0.005], [-0.2, 0.7, 0.39/2+0.01]]

obs_color = [[1, 1, 1, 1], [1, 1,1,1], [1, 1, 1, 1], [1, 1,1,1], [1, 1, 1, 1], 
             [1, 1,1,1], [1, 1, 1, 1], [1, 1,1,1]]
obs_mass = [None, None, None, None, None, None,None, None]
obs_density =[10, 10, 10, 10, 10, 10, 10, 10]
obs_rotation = [None, None, None, None, None, None, None, None]
obs_inertia = [None, None, None, None, None, None, None, None]
obs_names = [None, 'obstacle1', None, 'obstacle2', None, 'obstacle3', None, 'obstacle4']
obstacles ={'shapes':obs_shapes, 'dim':obs_dimensions, 'com_pos':obs_com_position, 
       'color':obs_color, 'mass':obs_mass, 'density':obs_density, 
       'rotation':obs_rotation, 'inertia':obs_inertia, 'name':obs_names}


o_geom_bodies_ind = [0, 1, 2, 3, 4, 5, 6, 7]
o_geom_name = [None, 'obstacle', None, 'obstacle', None, 'obstacle', None, 'obstacle']
o_geom_dim = [None, None, None, None, None, None, None, None]
o_geom_shape = [None, None, None, None, None, None, None, None]
o_geom_pos = [None, None, None, None, None, None, None, None]
o_geometries = {'body':o_geom_bodies_ind, 'name':o_geom_name, 'dim':o_geom_dim,
              'shape':o_geom_shape, 'pos':o_geom_pos}

o_jt_q_ind = [False, False, False, False]
o_jt_bodies = [[0,1], [1, -1], [2,3], [3,-1], [4,5], [5,-1], [6,7], [7,-1]]#, [2, -1]]  # [2,-1] obstacle and ground 
o_jt_type = [ 'fixed', 'prismatic', 'fixed', 'prismatic', 'fixed', 'prismatic', 
              'fixed', 'prismatic']#, 'prismatic']  #'fixed'
o_jt_anchor = [None, None, None, None, None, None, None, None]#, com_position[2]]  #[
o_jt_axis = [None, [1,0,0], None, [1, 0, 0], None, [1,0,0], None, [1,0,0]]#, [0,1,0]]
o_jt_vis_size = [[0.25, 0.25, 0.25], [0.25, 0.25, 0.25],[0.25, 0.25, 0.25], 
                 [0.25, 0.25, 0.25], [0.25, 0.25, 0.25], [0.25, 0.25, 0.25],
                 [0.25, 0.25, 0.25], [0.25, 0.25, 0.25]]
o_jt_vis_color = [[1, 0, 0, 1], [1,0,0,1], [1, 0, 0, 1], [1,0,0,1], [1, 0, 0, 1], [1,0,0,1],
                  [1, 0, 0, 1], [1,0,0,1]]
o_jt_feedback = [1, 0, 1, 0, 1, 0, 1, 0]

o_jts = {'bodies':o_jt_bodies, 'jt_type':o_jt_type, 'anchor':o_jt_anchor, 'axis':o_jt_axis,
          'vis_size':o_jt_vis_size, 'vis_color':o_jt_vis_color, 'feedback':o_jt_feedback}
