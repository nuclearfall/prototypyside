from PySide6.QtWidgets import QVBoxLayout, QDockWidget, QWidget, QToolBar
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt, QRectF

from prototypyside.views.graphics_scene import GameComponentGraphicsScene
from prototypyside.views.graphics_view import DesignerGraphicsView

class BaseEditorUI:
    def __init__(self, editor):
        self.editor = editor  # ComponentBuilder or LayoutBuilder
        self.settings = editor.settings
        self.appwin = editor.appwin

        self.editor.scene = None
        self.editor.view = None

        self.setup_docks()
        self.setup_scene_and_view()
        self.setup_toolbars()
        self.populate_toolbar()

    def setup_docks(self):
        # Left Dock
        self.editor.left_dock = QDockWidget("Elements and Layers", self.appwin)
        self.editor.left_dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.editor.left_dock_widget = QWidget()
        self.editor.left_dock_layout = QVBoxLayout(self.editor.left_dock_widget)
        self.editor.left_dock_layout.setContentsMargins(2, 2, 2, 2)
        self.editor.left_dock.setWidget(self.editor.left_dock_widget)
        self.appwin.addDockWidget(Qt.LeftDockWidgetArea, self.editor.left_dock)

        # Right Dock
        self.editor.right_dock = QDockWidget("Properties", self.appwin)
        self.editor.right_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.editor.right_dock_widget = QWidget()
        self.editor.right_dock_layout = QVBoxLayout(self.editor.right_dock_widget)
        self.editor.right_dock_layout.setContentsMargins(2, 2, 2, 2)
        self.editor.right_dock.setWidget(self.editor.right_dock_widget)
        self.appwin.addDockWidget(Qt.RightDockWidgetArea, self.editor.right_dock)

        # Central Widget already exists; we assume it is managed externally

    def setup_scene_and_view(self):
        template = self.editor.current_template

        self.editor.scene = GameComponentGraphicsScene(
            scene_rect=template.rect,
            template=template,
            app_settings=self.editor.settings,
            parent=self.editor
        )

        self.editor.view = DesignerGraphicsView(
            scene=self.editor.scene,
            app_settings=self.settings,
            parent=self.editor
        )
        print(f'Scene and View created...')
        # self.editor.scene.setSceneRect(template.rect)
        self.editor.view.fitInView(t, Qt.KeepAspectRatio)

        for element in template.elements:
            self.editor.scene.addItem(element)

        #self.editor.appwin.setCentralWidget(self.editor.view)  # ✅ This is enough


    def setup_toolbars(self):
        toolbar_name = getattr(self.editor, "toolbar_name", "Main Toolbar")
        self.editor.main_toolbar = QToolBar(toolbar_name, self.appwin)
        self.appwin.addToolBar(self.editor.main_toolbar)

    def populate_toolbar(self):
        # Meant to be overridden by subclasses
        pass
