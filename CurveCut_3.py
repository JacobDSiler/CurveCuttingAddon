import bpy
from mathutils import Vector, Quaternion

bl_info = {
    "name": "CurveSlice Pro",
    "author": "J.D. Siler",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > CurveSlice Pro",
    "description": "Description of your addon",
    "wiki_url": "",
    "category": "3D View",
}

class FlipNormalsOperator(bpy.types.Operator):
    bl_idname = "object.flip_normals_operator"
    bl_label = "Flip Normals"

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'
 
    def execute(self, context):
        props = context.scene.curve_slice_pro_properties
        if props.visualization_obj_name in context.scene.objects:
            vis_obj = context.scene.objects[props.visualization_obj_name]
            if vis_obj.type == 'MESH':
                # Store the original active object
                original_active_object_name = props.original_active_object_name

                # Set the visualization object as active and selected
                vis_obj.select_set(True)
                context.view_layer.objects.active = vis_obj

                # perform flip normals operations
                bpy.ops.object.mode_set(mode='EDIT')  
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.flip_normals()
                bpy.ops.object.mode_set(mode='OBJECT')
                
                # Deselect the visualization object
                vis_obj.select_set(False)

                # Call the set active operator to reset the original object as active and selected
                bpy.ops.object.set_active_operator(original_active_object_name=original_active_object_name)
        return {'FINISHED'}

class ToggleNormalsOperator(bpy.types.Operator):
    bl_idname = "object.toggle_normals_operator"
    bl_label = "Toggle Normals"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        props = context.scene.curve_slice_pro_properties
        new_state = not props.flip_normals

        if props.visualization_obj_name in bpy.data.objects:
            viz_obj = bpy.data.objects[props.visualization_obj_name]
            if viz_obj.type == 'MESH':
                bpy.ops.object.select_all(action='DESELECT')
                viz_obj.select_set(True)
                context.view_layer.objects.active = viz_obj
                if viz_obj.mode != 'EDIT':
                    bpy.ops.object.mode_set(mode='EDIT')

                    # Select all geometry
                    bpy.ops.mesh.select_all(action='SELECT')

                    # Check if flip_normals is True
                    #if new_state:
                    bpy.ops.mesh.flip_normals()
                    #else:
                        #bpy.ops.mesh.normals_make_consistent(inside=False)

                    bpy.ops.object.mode_set(mode='OBJECT')
                    viz_obj.select_set(False)

        props.flip_normals = new_state
        props.temp_override = not new_state
        self.report({'INFO'}, f"Flip Normals set to {props.flip_normals}")
        props.update_flip_normals(context)

        return {'FINISHED'}


class CurveSliceProProperties(bpy.types.PropertyGroup):
    depth: bpy.props.FloatProperty(name="Depth", default=1.0)
    depth_offset: bpy.props.FloatProperty(name="Depth Offset", default=0.0)
    cut_mode: bpy.props.BoolProperty(name="Cut Mode", default=True)
    cut_target: bpy.props.PointerProperty(
        name="Cut Target",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
    )
    cut_through: bpy.props.BoolProperty(name="Cut Through", default=False)
    # Properties for Setting Custom Resolution
    decimate_spline: bpy.props.BoolProperty(name="Decimate Spline Before Cut", default=False)
    decimate_spline_amount: bpy.props.FloatProperty(name="Amount", default=0.5, min=0.1, max=1)

    # Properties for Setting Custom Thickness
    set_thickness: bpy.props.BoolProperty(name="Set Thickness", default=False)
    thickness: bpy.props.FloatProperty(name="Thickness", default=0.0, min=0.0, max=10.0)
    flip_normals: bpy.props.BoolProperty(name="Flip Normals", default=False)
    keep_curve_post_cut: bpy.props.BoolProperty(name="Keep Curve Post Cut", default=False)
    view_rot: bpy.props.FloatVectorProperty(size=4)  # Quaternion rotation
    original_active_object_name: bpy.props.StringProperty()
    visualization_obj_name: bpy.props.StringProperty()

    # define the new attribute
    temp_override: bpy.props.BoolProperty(name="Temp Override", default=False)

    # The update function for the flip_normals property
    def update_flip_normals(self, context):
        if self.visualization_obj_name and self.visualization_obj_name in context.scene.objects:
            bpy.ops.object.flip_normals_operator()  # Call the new operator here

    flip_normals: bpy.props.BoolProperty(name="Flip Normals", default=False, update=update_flip_normals)


class VisualizationOperator(bpy.types.Operator):
    bl_idname = "object.visualization_operator"
    bl_label = "Visualize Normals"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR'}

    def invoke(self, context, event):
        props = context.scene.curve_slice_pro_properties
        view_layer = context.view_layer
        original_active_object_name = view_layer.objects.active.name if view_layer.objects.active else None
        
        # Check if there is an active object and it is selected
        if context.active_object is None or not context.active_object.select_get():
            self.report({'WARNING'}, "No object selected.")
            return {'CANCELLED'}
        
        # Check if there is an active object and it is selected
        if props.cut_mode and not props.cut_target:
            self.report({'WARNING'}, "No cut target selected. Please select a target to cut.")
            return {'CANCELLED'}
        
        # Remove the existing visualization object if it exists
        if props.visualization_obj_name in context.scene.objects:
            bpy.data.objects.remove(context.scene.objects[props.visualization_obj_name], do_unlink=True)
            props.visualization_obj_name = ""

        if not props.visualization_obj_name or props.visualization_obj_name not in context.scene.objects:
            # Only update view_rot to current view rotation if visualization_obj_name does not exist or does not refer to an existing object
            props.view_rot = list(context.space_data.region_3d.view_rotation)

        # Convert view_rot into Quaternion and calculate direction
        view_rot = Quaternion(props.view_rot)
        direction = view_rot @ Vector((0, 0, -1)).normalized()
        view_layer = context.view_layer

        # Store the original active object (the curve or grease pencil)
        original_active_object = context.active_object
        props.original_active_object_name = original_active_object.name  # Store the name.

        if props.visualization_obj_name:
            vis_obj = context.scene.objects.get(props.visualization_obj_name)
            if vis_obj is not None:  # Ensure the object exists before trying to manipulate it
                bpy.ops.object.select_all(action='DESELECT')  # Initially deselect all
                vis_obj.select_set(True)
                context.view_layer.objects.active = vis_obj
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.flip_normals()

        bpy.ops.object.mode_set(mode='OBJECT')

        if props.visualization_obj_name:
            vis_obj = context.scene.objects.get(props.visualization_obj_name)
            if vis_obj is not None:  # Ensure object exists before trying to unlink and delete
                bpy.data.objects.remove(vis_obj, do_unlink=True)
                props.visualization_obj = ""

        if context.active_object is None or (context.active_object.type != 'CURVE' and context.active_object.type != 'GPENCIL'):
            self.report({'WARNING'}, "No active curve object for visualization.")
            return {'CANCELLED'}
        
        #duplicate the source object
        bpy.ops.object.duplicate_move()
        duplicated_object = context.selected_objects[0]
        duplicated_object.name = "Visualizer"

        
        # Check if the active object is a grease pencil and convert if necessary
        if context.active_object.type == 'GPENCIL':
            self.report({'WARNING'}, "Grease pencil strokes are not supported with full accuracy. Converting to Bézier curve.")
            # Convert the duplicated grease pencil to a Bézier curve
            bpy.ops.gpencil.convert(type='CURVE', use_timing_data=False)
            # Deselect all objects first
            bpy.ops.object.select_all(action='DESELECT')
            # Find the newly created curve object and set it as the active and selected object
            for obj in context.view_layer.objects:
                if obj.type == 'CURVE':
                    obj.name = 'Visualizer'
                    context.view_layer.objects.active = obj
                    obj.select_set(True)
                    break
            bpy.data.objects.remove(duplicated_object, do_unlink=True)
            # Update the context
            context.view_layer.update()

        # Ensure we are in object mode, then apply a weld modifier if Decimate Cutter is set
        bpy.ops.object.mode_set(mode='OBJECT')
        if props.decimate_spline:
            reduce_spline_resolution(context, props)

        active_obj = context.active_object
        bpy.ops.object.select_all(action='DESELECT')  # Deselect everything to avoid duplicating more than the curve
        active_obj.select_set(True)  # Select only the curve
        visualization_obj = context.active_object
        bpy.ops.object.convert(target='MESH')
        props.visualization_obj_name = visualization_obj.name


        # Set the overlay mode to display the face orientation
        context.space_data.overlay.show_face_orientation = True

        extrusion_method(props, direction)

        # Reselect the original_active_object and set it as the active object again
        view_layer.objects.active = original_active_object
        original_active_object.select_set(True)

        # Update the context
        context.view_layer.update()

        # Trigger redraw
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

        if original_active_object_name in context.view_layer.objects:
            context.view_layer.objects.active = context.view_layer.objects[original_active_object_name]
            context.view_layer.objects.active.select_set(True)

        return {'FINISHED'}


    def execute(self, context):
        props = context.scene.curve_slice_pro_properties
        original_obj_name = props.original_active_object_name
        viz_obj_name = props.visualization_obj_name

        if props.flip_normals and viz_obj_name in context.scene.objects:
            viz_obj = context.scene.objects[viz_obj_name]

            # Select the visualization object, enter edit mode, flip normals
            context.view_layer.objects.active = viz_obj
            viz_obj.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.flip_normals()

            # Return to object mode, deselect visualization object
            bpy.ops.object.mode_set(mode='OBJECT')
            viz_obj.select_set(False)

        # Check if there is an active object and it is selected
        if context.active_object is None or not context.active_object.select_get():
            self.report({'WARNING'}, "No object selected.")
            return {'CANCELLED'}
        
        # Check if there is an active object and it is selected
        if props.cut_mode and not props.cut_target:
            self.report({'WARNING'}, "No cut target selected. Please select a target to cut.")
            return {'CANCELLED'}

        if original_obj_name in context.scene.objects:
            original_obj = context.scene.objects[original_obj_name]
            # Select and activate the original object
            context.view_layer.objects.active = original_obj
            original_obj.select_set(True)

        return {'FINISHED'}


#Define the set active operator class
class OBJECT_OT_set_active_operator(bpy.types.Operator):
    bl_idname = "object.set_active_operator"
    bl_label = "Set Active Object"
    bl_options = {'INTERNAL'} 
    
    original_active_object_name: bpy.props.StringProperty() 

    def execute(self, context):
        original_active_object_name = self.original_active_object_name
        if original_active_object_name in bpy.data.objects:
            original_obj = bpy.data.objects[original_active_object_name]
            original_obj.select_set(True)
            context.view_layer.objects.active = original_obj
        return {'FINISHED'}

#The method to reduce a spline's resolution.
def reduce_spline_resolution(context,props):
    selected_objects = bpy.context.selected_objects
    for obj in selected_objects:
        if obj.type == 'CURVE' or obj.type == 'PATH':
                # Convert curve to mesh
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.convert(target='MESH')
                # Add weld modifier
            bpy.ops.object.modifier_add(type='WELD')
            obj.modifiers['Weld'].merge_threshold = props.decimate_spline_amount
            bpy.ops.object.modifier_apply(modifier="Weld")



# Define the operator for the button
class CurveSlicePro(bpy.types.Operator):
    bl_idname = "object.simple_operator"
    bl_label = "CurveSlice"
    bl_options = {'REGISTER', 'UNDO'}

    # Store the view rotation at the time the operator is invoked
    def invoke(self, context, event):
        props = context.scene.curve_slice_pro_properties

        # Check if there is an active object and it is selected
        if context.active_object is None or not context.active_object.select_get():
            self.report({'WARNING'}, "No object selected.")
            return {'CANCELLED'}
        
        # Check if there is an active object and it is selected
        if props.cut_mode and not props.cut_target:
            self.report({'WARNING'}, "No cut target selected. Please select a target to cut.")
            return {'CANCELLED'}

        # From the discussion above, we only update this if the visualization_obj_name is not set, or the visualization object doesn't exist
        if not props.visualization_obj_name or props.visualization_obj_name not in context.scene.objects:
            props.view_rot = list(context.space_data.region_3d.view_rotation)

        # Remove the visualization object if it exists
        if props.visualization_obj_name:
            bpy.data.objects.remove(context.scene.objects[props.visualization_obj_name], do_unlink=True)
            props.visualization_obj_name = ""


        return self.execute(context)

    def execute(self, context):
        props = context.scene.curve_slice_pro_properties


        # Check if there is an active object and it is selected.
        if context.active_object is None or not context.active_object.select_get():
            self.report({'WARNING'}, "No object selected.")
            return {'CANCELLED'}
        
        # Check if cut mode is enabled, yest a cut_target is not set.
        if props.cut_mode and not props.cut_target:
            self.report({'WARNING'}, "No cut target selected. Please select a target to cut.")
            return {'CANCELLED'}
        
        
        # Check if there is an active object and it is selected
        if context.active_object is None or not context.active_object.select_get():
            self.report({'WARNING'}, "No object selected.")
            return {'CANCELLED'}
        
        # Normal operation follows...
        if context.active_object is None or (context.active_object.type != 'CURVE' and context.active_object.type != 'GPENCIL'):
            self.report({'WARNING'}, "No active curve object for visualization.")
            return {'CANCELLED'}

        # Remove the visualization object if it exists
        if props.visualization_obj_name:
            bpy.data.objects.remove(context.scene.objects[props.visualization_obj_name], do_unlink=True)
            props.visualization_obj_name = ""

        # Disable the Face Orientation visualization option.
        context.space_data.overlay.show_face_orientation = False

        # Convert the stored view rotation from a tuple to a Quaternion
        view_rot = Quaternion(props.view_rot)

        # Use this stored view rotation for the extrusion
        direction = view_rot @ Vector((0, 0, -1)).normalized()
        
        # Check if the active object is a grease pencil and convert if necessary
        if context.active_object.type == 'GPENCIL':
            self.report({'WARNING'}, "Grease pencil strokes are not supported with full accuracy. Converting to Bézier curve.")
            # Convert the duplicated grease pencil to a Bézier curve
            bpy.ops.gpencil.convert(type='CURVE', use_timing_data=False)
            # The active object should now be the new curve object
            # Deselect all objects first
            bpy.ops.object.select_all(action='DESELECT')
            # Find the newly created curve object and set it as the active and selected object
            for obj in context.view_layer.objects:
                if obj.type == 'CURVE':
                    context.view_layer.objects.active = obj
                    obj.select_set(True)
                    break
            # Update the context
            context.view_layer.update()

                    # Ensure we are in object mode, then apply a weld modifier if Decimate Cutter is set
            bpy.ops.object.mode_set(mode='OBJECT')
            if props.decimate_spline:
                reduce_spline_resolution(context, props)

        #If selection is usable, duplicate it and carry on.
        bpy.ops.object.duplicate_move()

        # Get the duplicated object
        duplicated_object = context.active_object

        # Extrude the curve.
        extrusion_method(props, direction)

        # Store the active extruded object
        extruded_object = context.active_object

        # Check if the Original material exists
        if "Original" not in bpy.data.materials:
            # Create the Original material
            original_mat = bpy.data.materials.new(name="Original")
            original_mat.diffuse_color = (0.1, 0.1, 0.8, 1)  # Define this material color as silvery blue
        else:
            # Use the existing Original material
            original_mat = bpy.data.materials["Original"]

        # Assign the Original material to the boolean object if it has no materials
        if props.cut_mode and props.cut_target is not None:
            if len(props.cut_target.data.materials) == 0:
                # Add a new material slot
                props.cut_target.data.materials.append(None)
                
                # Add the original material to the new material slot
                props.cut_target.material_slots[0].material = original_mat

        # Check if the CutSurface material exists
        if "CutSurface" not in bpy.data.materials:
            # Create the CutSurface material
            cutsurface_mat = bpy.data.materials.new(name="CutSurface")
            cutsurface_mat.diffuse_color = (1, 0.1, 0.1, 1)  # Define this material color as red
        else:
            # Use the existing CutSurface material
            cutsurface_mat = bpy.data.materials["CutSurface"]

        # Assign the CutSurface material to the extruded object
        # Check if the object has any material slots
        if props.cut_mode and props.cut_target is not None:
            if not extruded_object.material_slots:
                # If no material slots are found, add one
                extruded_object.data.materials.append(None)
                if len(props.cut_target.data.materials) == 0:
                    # No materials, just add CutSurface
                    extruded_object.data.materials.append(cutsurface_mat)
                else:
                    # Replace first material with CutSurface
                    extruded_object.material_slots[0].material = cutsurface_mat
            
            
        # Check if the Original material exists
        if "Original" not in bpy.data.materials:
            # Create the Original material
            original_mat = bpy.data.materials.new(name="Original")
        else:
            # Use the existing Original material
            original_mat = bpy.data.materials["Original"]

        # Apply boolean modifier if "Cut Mode" is checked
        if props.cut_mode and props.cut_target:
            # Add a difference boolean modifier to the target
            target_object = props.cut_target
            boolean_modifier = target_object.modifiers.new(name="Cut Modifier", type='BOOLEAN')
            boolean_modifier.operation = 'DIFFERENCE'
            boolean_modifier.object = extruded_object
            boolean_modifier.material_mode = 'TRANSFER'

            # Apply the boolean modifier
            bpy.context.view_layer.objects.active = target_object
            bpy.ops.object.modifier_apply(modifier=boolean_modifier.name)

            # Optionally, delete the extruded curve after the boolean operation if "Keep Curve Post Cut" isn't checked
            if not props.keep_curve_post_cut:
                bpy.data.objects.remove(duplicated_object, do_unlink=True)

        return {'FINISHED'}

def extrusion_method(props, direction):
    if props.cut_mode and props.cut_through:
        depth_offset = 10000
        depth = 20000
    else:
        depth_offset = props.depth_offset
        depth = props.depth

    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.transform.translate(value=direction * (-depth_offset))
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": direction * (depth + depth_offset)}
    )
    # Flip normals if the checkbox is checked
    if props.flip_normals:
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.flip_normals()

    if props.set_thickness:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        # Creating the translation and extrusion based on surface normal.
        bpy.ops.transform.translate(value=(0, 0, -props.thickness / 2), orient_type='NORMAL', constraint_axis=(False, False, True))
        bpy.ops.mesh.extrude_region_move(
            MESH_OT_extrude_region={"use_normal_flip": False, "mirror": False},
            TRANSFORM_OT_translate={"value": (0, 0, props.thickness), "orient_type": 'NORMAL', "constraint_axis": (False, False, True)}
        )

    bpy.ops.object.mode_set(mode='OBJECT')


# Modified custom panel
class OBJECT_PT_CustomPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_custom_panel"
    bl_label = "Curve Project Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CurveSlice Pro"
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout
        props = context.scene.curve_slice_pro_properties

        layout.operator(CurveSlicePro.bl_idname)
        layout.prop(props, "depth")
        layout.prop(props, "depth_offset")
        layout.operator(VisualizationOperator.bl_idname)
        # Only show button if visualization object exists
        if props.visualization_obj_name and props.visualization_obj_name in context.scene.objects:
            context.scene.objects[props.visualization_obj_name].select_set(False)

        layout.prop(props, "flip_normals")
        layout.prop(props, "cut_mode")

        if props.cut_mode:
            layout.prop(props, "cut_target", text="Cut Target")
            layout.prop(props, "keep_curve_post_cut")

            # Add properties for Setting Thickness
            row = layout.row()
            row.prop(props, "set_thickness")
            if props.set_thickness:
                row.prop(props, "thickness")   

            if props.cut_target:
                layout.prop(props, "cut_through")
    
        # Add properties for decimating a spline cutter object
        row = layout.row()
        row.prop(props, "decimate_spline")
        if props.decimate_spline:
            row.prop(props, "decimate_spline_amount")

# Register the operator, panel, and properties
def register():
    bpy.utils.register_class(ToggleNormalsOperator)
    bpy.utils.register_class(VisualizationOperator)
    bpy.utils.register_class(CurveSlicePro)
    bpy.utils.register_class(OBJECT_PT_CustomPanel)
    bpy.utils.register_class(CurveSliceProProperties)
    bpy.utils.register_class(OBJECT_OT_set_active_operator)
    bpy.utils.register_class(FlipNormalsOperator)
    bpy.types.Scene.curve_slice_pro_properties = bpy.props.PointerProperty(type=CurveSliceProProperties)
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Object Mode')
    kmi = km.keymap_items.new(ToggleNormalsOperator.bl_idname, 'F', 'PRESS')


def unregister():
    bpy.utils.unregister_class(ToggleNormalsOperator)
    bpy.utils.unregister_class(VisualizationOperator)
    bpy.utils.unregister_class(CurveSlicePro)
    bpy.utils.unregister_class(OBJECT_PT_CustomPanel)
    bpy.utils.unregister_class(CurveSliceProProperties)
    bpy.utils.unregister_class(FlipNormalsOperator)
    wm = bpy.context.window_manager
    del bpy.types.Scene.curve_slice_pro_properties


if __name__ == "__main__":
    register()
