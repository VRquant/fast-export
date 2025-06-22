bl_info = {
    "name": "Fast Export",
    "author": "DmitriyHi",
    "version": (7, 2),
    "blender": (3, 6, 5),
    "location": "View3D > Sidebar > Fast Export",
    "description": "Быстрый экспорт в FBX с локальным Origin",
    "doc_url": "",
    "tracker_url": "",
    "category": "Import-Export"
}

import bpy
import os
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    CollectionProperty,
    EnumProperty,
)
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup

ADDON_NAME = "FastExport"

def check_keymap_conflict(self, kc, key_type, ctrl=False, shift=False, alt=False):
    if not kc:
        return False
    
    allowed_conflicts = {
        ('ALT', 'Q'): "object.transfer_mode",
        ('ALT', 'W'): "wm.toolbar_fallback_pie"
    }
    
    current_combo = (
        'ALT' if alt else '',
        key_type
    )
    
    for km in kc.keymaps:
        for kmi in km.keymap_items:
            if (kmi.type == key_type and 
                kmi.ctrl == ctrl and 
                kmi.shift == shift and 
                kmi.alt == alt and
                not kmi.idname.startswith("fastexport.")):
                
                if current_combo in allowed_conflicts and kmi.idname == allowed_conflicts[current_combo]:
                    continue
                    
                self.report({'WARNING'}, 
                    f"Горячая клавиша уже используется в Blender для: {kmi.idname}")
                return True
    return False

def select_file_in_explorer(file_path):
    """Открывает проводник и выделяет файл"""
    if os.name == 'nt':  # Windows
        import subprocess
        subprocess.Popen(f'explorer /select,"{file_path}"')
    else:  # Linux/Mac
        import subprocess
        folder = os.path.dirname(file_path)
        subprocess.Popen(['xdg-open', folder])

def get_active_export_path():
    """Получить активный путь для экспорта"""
    if ADDON_NAME not in bpy.context.preferences.addons:
        return None
    prefs = bpy.context.preferences.addons[ADDON_NAME].preferences
    return prefs.export_path if os.path.isdir(prefs.export_path) else None

class FastExportPathItem(PropertyGroup):
    name: StringProperty()

def update_history(path):
    if not os.path.isdir(path):
        return
    
    if ADDON_NAME not in bpy.context.preferences.addons:
        return
        
    prefs = bpy.context.preferences.addons[ADDON_NAME].preferences
    
    existing_paths = []
    for item in prefs.export_history:
        if item.name not in existing_paths and os.path.isdir(item.name):
            existing_paths.append(item.name)
    
    if path not in existing_paths:
        existing_paths.insert(0, path)
    else:
        existing_paths.remove(path)
        existing_paths.insert(0, path)
    
    existing_paths = existing_paths[:prefs.history_limit]
    
    prefs.export_history.clear()
    
    for p in existing_paths:
        item = prefs.export_history.add()
        item.name = p

    prefs.selected_history_path = path
    prefs.display_path = path
    prefs.export_path = path

def on_export_path_updated(self, context):
    if ADDON_NAME not in context.preferences.addons:
        return
        
    if self.export_path and os.path.isdir(self.export_path):
        update_history(self.export_path)

class FASTEXPORT_OT_modal_hotkey_register(Operator):
    bl_idname = "fastexport.modal_hotkey_register"
    bl_label = "Register Hotkey"
    bl_description = "Нажмите комбинацию клавиш для назначения"

    target: StringProperty()
    is_recording: BoolProperty(default=False)

    def modal(self, context, event):
        if event.type == 'ESC':
            self.is_recording = False
            if self.target == 'export':
                context.window_manager.fastexport_recording_export = False
            else:
                context.window_manager.fastexport_recording_path = False
            self.report({'INFO'}, "Отмена записи горячей клавиши")
            return {'FINISHED'}

        if event.value == 'PRESS':
            if event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_CTRL', 
                            'RIGHT_CTRL', 'LEFT_ALT', 'RIGHT_ALT'}:
                return {'RUNNING_MODAL'}

            prefs = context.preferences.addons[ADDON_NAME].preferences
            wm = context.window_manager
            kc = wm.keyconfigs.user

            if check_keymap_conflict(self, kc, event.type, 
                                   event.ctrl, event.shift, event.alt):
                self.is_recording = False
                if self.target == 'export':
                    context.window_manager.fastexport_recording_export = False
                else:
                    context.window_manager.fastexport_recording_path = False
                return {'FINISHED'}

            key_string = []
            if event.ctrl:
                key_string.append('Ctrl')
            if event.shift:
                key_string.append('Shift')
            if event.alt:
                key_string.append('Alt')
            key_string.append(event.type)
            key_combo = ' + '.join(key_string)

            if self.target == 'export':
                prefs.export_hotkey = key_combo
            else:
                prefs.choose_path_hotkey = key_combo

            update_keymaps()

            self.is_recording = False
            if self.target == 'export':
                context.window_manager.fastexport_recording_export = False
            else:
                context.window_manager.fastexport_recording_path = False
            self.report({'INFO'}, f"Горячая клавиша назначена: {key_combo}")
            return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.is_recording = True
        if self.target == 'export':
            context.window_manager.fastexport_recording_export = True
        else:
            context.window_manager.fastexport_recording_path = True
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class FASTEXPORT_OT_clear_hotkey(Operator):
    bl_idname = "fastexport.clear_hotkey"
    bl_label = "Clear Hotkey"
    bl_description = "Очистить горячую клавишу"
    
    target: StringProperty()
    
    def execute(self, context):
        prefs = context.preferences.addons[ADDON_NAME].preferences
        if self.target == 'export':
            prefs.export_hotkey = ""
        else:
            prefs.choose_path_hotkey = ""
        update_keymaps()
        return {'FINISHED'}


class FastExportPreferences(AddonPreferences):
    bl_idname = ADDON_NAME

    export_path: StringProperty(
        name="Export Path",
        subtype='DIR_PATH',
        default="",
        description="Активный путь для экспорта",
        update=on_export_path_updated,
    )

    display_path: StringProperty(
        name="Display Path",
        default="",
        description="Путь для отображения в интерфейсе"
    )

    open_folder: BoolProperty(
        name="Open folder",
        default=False,
        description="Открывать папку после успешного экспорта"
    )

    export_history: CollectionProperty(type=FastExportPathItem)
    history_limit: IntProperty(
        name="History limit",
        default=5,
        min=1,
        max=20,
        description="Количество сохраняемых в историю путей для экспорта"
    )
    selected_history_path: StringProperty()

    history_items: EnumProperty(
        name="History",
        items=lambda self, context: self.get_history_items(context),
        update=lambda self, context: self.on_history_item_selected(context)
    )

    export_hotkey: StringProperty(
        name="Export Hotkey",
        default="",
        description="Горячая клавиша для экспорта"
    )

    choose_path_hotkey: StringProperty(
        name="Choose Path Hotkey",
        default="",
        description="Горячая клавиша для выбора пути"
    )

    show_clear_geometry: BoolProperty(
        name="Кнопка чистки модели",
        default=False,
        description="Включить кнопку по очистке модели от ребер, не влияющих на форму"
    )

    show_hotkeys_hint: BoolProperty(
        name="Подсказка по горячим клавишам",
        default=False,
        description="Показывать подсказки с назначенными горячими клавишами под кнопкой Export"
    )

    def draw(self, context):
        layout = self.layout
        
        box = layout.box()
        box.label(text="Settings")
        
        row = box.row()
        row.prop(self, "history_limit")
        
        box.label(text="Горячие клавиши:", icon='KEYINGSET')
        
        row = box.row(align=True)
        row.label(text=f"Export: {self.export_hotkey if self.export_hotkey else 'Не назначено'}")
        sub = row.row(align=True)
        sub.operator("fastexport.modal_hotkey_register", 
                    text="", 
                    icon='REC' if getattr(context.window_manager, 
                        "fastexport_recording_export", False) else 'RADIOBUT_OFF').target = 'export'
        sub.operator("fastexport.clear_hotkey", 
                    text="", 
                    icon='X').target = 'export'
        
        row = box.row(align=True)
        row.label(text=f"Choose Path: {self.choose_path_hotkey if self.choose_path_hotkey else 'Не назначено'}")
        sub = row.row(align=True)
        sub.operator("fastexport.modal_hotkey_register", 
                    text="", 
                    icon='REC' if getattr(context.window_manager, 
                        "fastexport_recording_path", False) else 'RADIOBUT_OFF').target = 'choose_path'
        sub.operator("fastexport.clear_hotkey", 
                    text="", 
                    icon='X').target = 'choose_path'

        box.separator()
        box.prop(self, "show_clear_geometry")
        box.prop(self, "show_hotkeys_hint")

    def get_history_items(self, context):
        items = []
        valid_paths = []
        
        for item in self.export_history:
            if os.path.isdir(item.name) and item.name not in valid_paths:
                valid_paths.append(item.name)
                display_name = os.path.basename(item.name) or item.name
                items.append((item.name, display_name, item.name))
        
        if not items:
            items.append(("__EMPTY__", "No history", ""))
        else:
            items.append(("__CLEAR__", "Clear", ""))
        
        return items

    def on_history_item_selected(self, context):
        if self.history_items == "__CLEAR__":
            self.export_history.clear()
            self.selected_history_path = ""
            self.export_path = ""
            self.display_path = ""
        elif self.history_items != "__EMPTY__" and os.path.isdir(self.history_items):
            self.export_path = self.history_items
            self.display_path = self.history_items
            self.selected_history_path = self.history_items
            update_history(self.history_items)

class FASTEXPORT_OT_clear_geometry(Operator):
    bl_idname = "fastexport.clear_geometry"
    bl_label = "Clear geometry"
    bl_description = "Удалить рёбра, которые не влияют на форму модели"

    def execute(self, context):
        try:
            selected = context.selected_objects
            if not selected:
                self.report({'WARNING'}, "Нет выбранных объектов")
                return {'CANCELLED'}

            cleaned_objects = 0
            total_edges_removed = 0

            for obj in selected:
                if obj.type != 'MESH':
                    continue

                original_active = context.active_object
                original_mode = context.mode

                context.view_layer.objects.active = obj

                if original_mode != 'EDIT_MESH':
                    bpy.ops.object.mode_set(mode='EDIT')

                initial_edges = len(obj.data.edges)

                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.dissolve_limited(
                    angle_limit=0.0872665,
                    use_dissolve_boundaries=False,
                    delimit={'UV'}
                )

                if original_mode != 'EDIT_MESH':
                    bpy.ops.object.mode_set(mode=original_mode)

                context.view_layer.objects.active = original_active

                final_edges = len(obj.data.edges)
                edges_removed = initial_edges - final_edges
                
                if edges_removed > 0:
                    cleaned_objects += 1
                    total_edges_removed += edges_removed

            if total_edges_removed > 0:
                self.report({'INFO'}, 
                    f"Геометрия очищена: удалено {total_edges_removed} рёбер в {cleaned_objects} объектах")
            else:
                self.report({'INFO'}, "Нет рёбер для удаления")

            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка при очистке геометрии: {str(e)}")
            return {'CANCELLED'}

class FASTEXPORT_OT_set_path(Operator):
    bl_idname = "fastexport.set_path"
    bl_label = "Choose path"
    bl_description = "Добавить путь для экспорта"
    filepath: StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        prefs = context.preferences.addons[ADDON_NAME].preferences
        if not self.filepath or not os.path.isdir(self.filepath):
            self.report({'WARNING'}, "Неверный путь")
            return {'CANCELLED'}
            
        prefs.export_path = self.filepath
        prefs.display_path = self.filepath
        update_history(self.filepath)
        self.report({'INFO'}, f"Путь сохранён: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class FASTEXPORT_OT_export_with_path(Operator):
    bl_idname = "fastexport.export_with_path"
    bl_label = "Export"
    bl_description = "Экспортировать модель/модели по выбранному пути"

    def execute(self, context):
        if ADDON_NAME not in context.preferences.addons:
            self.report({'ERROR'}, "Аддон не активирован")
            return {'CANCELLED'}
            
        export_path = get_active_export_path()
        if export_path:
            return bpy.ops.fastexport.export('INVOKE_DEFAULT')
        else:
            bpy.ops.fastexport.set_path_and_export('INVOKE_DEFAULT')
            return {'FINISHED'}

class FASTEXPORT_OT_set_path_and_export(Operator):
    bl_idname = "fastexport.set_path_and_export"
    bl_label = "Choose and Export"
    filepath: StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        if not self.filepath or not os.path.isdir(self.filepath):
            self.report({'WARNING'}, "Неверный путь")
            return {'CANCELLED'}

        prefs = context.preferences.addons[ADDON_NAME].preferences
        prefs.export_path = self.filepath
        prefs.display_path = self.filepath
        update_history(self.filepath)

        return bpy.ops.fastexport.export('INVOKE_DEFAULT')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class FASTEXPORT_OT_export(Operator):
    bl_idname = "fastexport.export"
    bl_label = "Export selected"

    def execute(self, context):
        try:
            export_path = get_active_export_path()
            if not export_path:
                self.report({'ERROR'}, "Неверный путь экспорта")
                return {'CANCELLED'}

            selected = context.selected_objects
            if not selected:
                self.report({'WARNING'}, "Нет выбранных объектов")
                return {'CANCELLED'}

            original_mode = context.mode
            original_active = context.active_object

            if original_mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='OBJECT')

            exported_files = []
            count = 0

            original_selected = context.selected_objects[:]

            try:
                for obj in selected:
                    if obj.type != 'MESH':
                        continue

                    bpy.ops.object.select_all(action='DESELECT')
                    obj.select_set(True)
                    
                    old_loc = obj.location.copy()
                    obj.location = (0, 0, 0)
                    
                    filepath = os.path.join(export_path, f"{obj.name}.fbx")
                    bpy.ops.export_scene.fbx(
                        filepath=filepath,
                        use_selection=True,
                        apply_unit_scale=True,
                        global_scale=1.0,
                        mesh_smooth_type='FACE'
                    )
                    exported_files.append(filepath)
                    
                    obj.location = old_loc
                    count += 1

            finally:
                bpy.ops.object.select_all(action='DESELECT')
                for obj in original_selected:
                    obj.select_set(True)

                if original_active:
                    context.view_layer.objects.active = original_active

                if original_mode == 'EDIT_MESH':
                    bpy.ops.object.mode_set(mode='EDIT')

            if context.preferences.addons[ADDON_NAME].preferences.open_folder and exported_files:
                select_file_in_explorer(exported_files[-1])

            self.report({'INFO'}, f"Экспортировано: {count}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка при экспорте: {str(e)}")
            return {'CANCELLED'}

class FASTEXPORT_OT_open_selected_path(Operator):
    bl_idname = "fastexport.open_selected_path"
    bl_label = "Open folder"
    bl_description = "Открыть папку в проводнике по выбранному пути экспорта"

    def execute(self, context):
        path = get_active_export_path()
        if not path:
            self.report({'WARNING'}, "Путь не существует или не выбран")
            return {'CANCELLED'}

        if os.name == 'nt':
            os.startfile(path)
        else:
            import subprocess
            subprocess.Popen(['xdg-open', path])
        return {'FINISHED'}

class FASTEXPORT_PT_panel(Panel):
    bl_label = "Fast Export"
    bl_idname = "FASTEXPORT_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fast Export"
    bl_context = "objectmode"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        if ADDON_NAME not in context.preferences.addons:
            layout = self.layout
            layout.label(text="Аддон не активирован")
            return

        prefs = context.preferences.addons[ADDON_NAME].preferences
        layout = self.layout
        
        box = layout.box()
        box.label(text="Export Path", icon='FILE_FOLDER')
        
        box.operator("fastexport.set_path", text="Choose Path", icon='FILE_FOLDER')

        row = box.row(align=True)
        row.prop(prefs, "history_items", text="History")
        row.operator("fastexport.open_selected_path", text="", icon='FILE_FOLDER')
        
        export_box = layout.box()
        export_box.operator("fastexport.export_with_path", text="Export", icon='EXPORT')
        
        sub = export_box.row()
        sub.prop(prefs, "open_folder", text="Open folder")
        
        if prefs.show_hotkeys_hint and (prefs.export_hotkey or prefs.choose_path_hotkey):
            box = export_box.box()
            if prefs.export_hotkey:
                box.label(text=f"Export: {prefs.export_hotkey}")
            if prefs.choose_path_hotkey:
                box.label(text=f"Choose Path: {prefs.choose_path_hotkey}")
        
        if prefs.show_clear_geometry:
            export_box.operator("fastexport.clear_geometry", text="Clear geometry", icon='MESH_DATA')

def update_keymaps():
    for km, kmi in addon_keymaps:
        if hasattr(km.keymap_items, "remove"):
            km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    
    if ADDON_NAME not in bpy.context.preferences.addons:
        return
        
    prefs = bpy.context.preferences.addons[ADDON_NAME].preferences
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        
        for hotkey_str, operator in [
            (prefs.export_hotkey, "fastexport.export_with_path"),
            (prefs.choose_path_hotkey, "fastexport.set_path")
        ]:
            if hotkey_str and hotkey_str.strip():
                parts = hotkey_str.split(' + ')
                key = parts[-1]
                try:
                    kmi = km.keymap_items.new(
                        operator,
                        key,
                        'PRESS',
                        ctrl='Ctrl' in parts,
                        shift='Shift' in parts,
                        alt='Alt' in parts
                    )
                    addon_keymaps.append((km, kmi))
                except:
                    continue

classes = (
    FastExportPathItem,
    FastExportPreferences,
    FASTEXPORT_OT_modal_hotkey_register,
    FASTEXPORT_OT_clear_hotkey,
    FASTEXPORT_OT_set_path,
    FASTEXPORT_OT_export,
    FASTEXPORT_OT_export_with_path,
    FASTEXPORT_OT_set_path_and_export,
    FASTEXPORT_OT_open_selected_path,
    FASTEXPORT_OT_clear_geometry,
    FASTEXPORT_PT_panel,
)

addon_keymaps = []

def register():
    bpy.types.WindowManager.fastexport_recording_export = BoolProperty(default=False)
    bpy.types.WindowManager.fastexport_recording_path = BoolProperty(default=False)
    
    for cls in classes:
        bpy.utils.register_class(cls)
    update_keymaps()

def unregister():
    del bpy.types.WindowManager.fastexport_recording_export
    del bpy.types.WindowManager.fastexport_recording_path
    
    for km, kmi in addon_keymaps:
        if hasattr(km.keymap_items, "remove"):
            km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()