# -*- coding: utf-8 -*-
# <pep8 compliant>

bl_info = {
    "name": "Haydee I/O Scripts",
    "author": "johnzero7",
    "version": (0, 4, 0),
    "blender": (2, 78, 0),
    "location": "File > Import-Export > HaydeeTools",
    "description": "Import-Export scripts for Haydee",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export",
}

if "bpy" in locals():
    import imp
    # Import if the library is new
    from . import HaydeeExporter
    from . import HaydeeImporter
    from . import HaydeeUtils
    from . import HaydeeNodeMat
    # Reload
    imp.reload(HaydeeExporter)
    imp.reload(HaydeeImporter)
    imp.reload(HaydeeUtils)
    imp.reload(HaydeeNodeMat)
    # print("Reloading Libraries")
else:
    import bpy
    from . import HaydeeExporter
    from . import HaydeeImporter
    from . import HaydeeUtils
    from . import HaydeeNodeMat
    # print("Loading Libraries")





class HaydeeToolsImportPanel(bpy.types.Panel):
    '''Haydee Import Toolshelf'''
    bl_idname = 'OBJECT_PT_haydee_import_tools_object'
    bl_label = 'Haydee Import Tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = 'Haydee'
    bl_context = 'objectmode'

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        col.label('Outfit:')
        # c = col.column()
        r = col.row(align=True)
        r1c1 = r.column(align=True)
        r1c1.operator("haydee_importer.outfit", text='Outfit', icon='NONE')

        # col.separator()
        col = layout.column()

        col.label('Mesh:')
        # c = col.column()
        r = col.row(align=True)
        r1c1 = r.column(align=True)
        r1c1.operator("haydee_importer.dmesh", text='DMesh', icon='NONE')
        r1c2 = r.column(align=True)
        r1c2.operator('haydee_importer.mesh', text='Mesh')

        # col.separator()
        col = layout.column()

        col.label('Skeleton:')
        # c = col.column()
        r = col.row(align=True)
        r1c1 = r.column(align=True)
        r1c1.operator("haydee_importer.dskel", text='DSkel', icon='NONE')
        r1c2 = r.column(align=True)
        r1c2.operator('haydee_importer.skel', text='Skel')

        # col.separator()
        col = layout.column()

        col.label('Motion:')
        # c = col.column()
        r = col.row(align=True)
        r1c1 = r.column(align=True)
        r1c1.operator("haydee_importer.dmotion", text='Dmotion', icon='NONE')
        r1c2 = r.column(align=True)
        r1c2.operator('haydee_importer.motion', text='Motion')

        # col.separator()
        col = layout.column()

        col.label('Pose:')
        # c = col.column()
        r = col.row(align=True)
        r1c1 = r.column(align=True)
        r1c1.operator("haydee_importer.dpose", text='DPose', icon='NONE')
        r1c2 = r.column(align=True)
        r1c2.operator('haydee_importer.pose', text='Pose')

        # col.separator()
        col = layout.column()

        col.label('Skin:')
        # c = col.column()
        r = col.row(align=True)
        r1c1 = r.column(align=True)
        r1c1.operator("haydee_importer.skin", text='Skin', icon='NONE')

        # col.separator()
        col = layout.column()

        col.label('Material:')
        # c = col.column()
        r = col.row(align=True)
        r1c1 = r.column(align=True)
        r1c1.operator("haydee_importer.material", text='Material', icon='NONE')


class HaydeeToolsExportPanel(bpy.types.Panel):
    '''Haydee Export Tools'''
    bl_idname = 'OBJECT_PT_haydee_export_tools_object'
    bl_label = 'Haydee Export Tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = 'Haydee'
    bl_context = 'objectmode'

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        col.label('Mesh:')
        # c = col.column()
        r = col.row(align=True)
        r.operator("haydee_exporter.dmesh", text='DMesh', icon='NONE')

        # col.separator()
        col = layout.column()

        col.label(text="Skeleton:")
        c = col.column()
        r = c.row(align=True)
        r2c1 = r.column(align=True)
        r2c1.operator('haydee_exporter.dskel', text='DSkel')
        r2c2 = r.column(align=True)
        r2c2.operator('haydee_exporter.skeleton', text='Skel')

        # col.separator()
        col = layout.column()

        col.label('Pose:')
        c = col.column(align=True)
        c.operator('haydee_exporter.dpose', text='DPose')

        # col.separator()
        col = layout.column()

        col.label('Motion:')
        c = col.column(align=True)
        c.operator('haydee_exporter.dmotion', text='DMot')



class HaydeeToolsImportPanel(bpy.types.Panel):
    '''Haydee Adjust Armature Toolshelf'''
    bl_idname = 'OBJECT_PT_haydee_skel_tools_object'
    bl_label = 'Haydee Skel Tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = 'Haydee'
    bl_context = 'objectmode'

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        col.label('Fit Armature/Mesh:')
        # c = col.column()
        r = col.row(align=True)
        r1c1 = r.column(align=True)
        r1c1.operator("haydee_tools.fit_to_armature", text='To Armature', icon='NONE')
        r1c2 = r.column(align=True)
        r1c2.operator('haydee_tools.fit_to_mesh', text='To Mesh')


#
# Registration
#


def register():
    print('Registering %s' % __name__)
    bpy.utils.register_module(__name__)
    HaydeeExporter.register()
    HaydeeImporter.register()


def unregister():
    print('Unregistering %s' % __name__)
    HaydeeExporter.unregister()
    HaydeeImporter.unregister()
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()

    # call exporter
    # bpy.ops.xps_tools.export_model('INVOKE_DEFAULT')

    # call importer
    # bpy.ops.xps_tools.import_model('INVOKE_DEFAULT')
