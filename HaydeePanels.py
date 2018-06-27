# -*- coding: utf-8 -*-
# <pep8 compliant>


import bpy

class _HaydeeToolsPanel():
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = 'Haydee'
    bl_context = 'objectmode'


class HaydeeToolsImportPanel(_HaydeeToolsPanel, bpy.types.Panel):
    '''Haydee Import Toolshelf'''
    bl_idname = 'OBJECT_PT_haydee_import_tools_object'
    bl_label = 'Haydee Import Tools'

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
        r1c1.operator("haydee_importer.dmot", text='Dmotion', icon='NONE')
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


class HaydeeToolsExportPanel(_HaydeeToolsPanel, bpy.types.Panel):
    '''Haydee Export Tools'''
    bl_idname = 'OBJECT_PT_haydee_export_tools_object'
    bl_label = 'Haydee Export Tools'

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
        #r2c2 = r.column(align=True)
        #r2c2.operator('haydee_exporter.skeleton', text='Skel')

        # col.separator()
        col = layout.column()

        col.label('Pose:')
        c = col.column(align=True)
        c.operator('haydee_exporter.dpose', text='DPose')

        # col.separator()
        col = layout.column()

        col.label('Motion:')
        c = col.column(align=True)
        c.operator('haydee_exporter.dmot', text='DMot')


class HaydeeToolsSkelPanel(_HaydeeToolsPanel, bpy.types.Panel):
    '''Haydee Adjust Armature Toolshelf'''
    bl_idname = 'OBJECT_PT_haydee_skel_tools_object'
    bl_label = 'Haydee Skel Tools'

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


