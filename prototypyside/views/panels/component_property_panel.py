from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, QObject

from prototypyside.widgets.unit_field import UnitField
import inspect


class PropertyPanel(QWidget):
    def __init__(self, target_object=None, property_dict, parent=None):
        super().__init__(parent)
        self.target_object = target_object
        self.property_dict = property_dict
        self.layout = QVBoxLayout(self)
        self.widgets = {}
        self.setup_ui()

    def clear(self):
        """Clear and disable all fields in the property panel."""
        for widget in self.findChildren(QWidget):
            # Skip QLabel widgets - they should keep their text
            if isinstance(widget, QLabel):
                continue
                
            if isinstance(widget, UnitField):
                widget.setValue(None)
            elif isinstance(widget, QLineEdit): 
                widget.setText("")
            elif isinstance(widget, QComboBox):
                if widget.count() > 0:
                    widget.setCurrentIndex(0)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(False)
            elif isinstance(widget, ColorPickerWidget):
                widget.set_color(QColor(0, 0, 0, 0))
            elif hasattr(widget, 'setValue'):
                widget.setValue(0)

            widget.setEnabled(False)
    def setup_ui(self):
        for prop, settings in self.property_dict.items():
            label = QLabel(settings.get('label', prop))
            widget = self.widget_factory(settings)

            getter = settings['getter']
            setter = settings['setter']
            connect = settings['connect']

            # Set initial value
            current_value = getter(self.target_object, prop)
            self.set_widget_value(widget, current_value)

            # Connect signals
            connect(widget, lambda val, s=setter, p=prop: s(self.target_object, val, p))

            self.layout.addWidget(label)
            self.layout.addWidget(widget)

            self.widgets[prop] = widget

        self.layout.addStretch()

    def set_widget_value(self, widget, value):
        if isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, QComboBox):
            index = widget.findText(value)
            if index >= 0:
                widget.setCurrentIndex(index)
        elif isinstance(widget, QListWidget):
            items = widget.findItems(value, Qt.MatchExactly)
            if items:
                widget.setCurrentItem(items[0])
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox, UnitField)):
            widget.setValue(value)

    def widget_factory(self, settings):
        widget_class = settings['widget']
        widget_args = settings.get('args', [])
        widget_kwargs = settings.get('kwargs', {})
        return widget_class(*widget_args, **widget_kwargs)

    @staticmethod
    def generate_property_dict(obj, template_name):
        property_dict = {}
        for name, attr in inspect.getmembers(type(obj), lambda o: isinstance(o, property)):
            property_dict[name] = {
                **widget_templates[template_name],
                'label': name.capitalize(),
                'getter': lambda o, attr=name: getattr(o, attr),
                'setter': lambda o, val, attr=name: setattr(o, attr, val)
            }
        return property_dict


# Complete dictionary for widget templates
widget_templates = {
    'line_edit': {
        'widget': QLineEdit,
        'args': [],
        'kwargs': {},
        'getter': lambda obj, attr: getattr(obj, attr),
        'setter': lambda obj, val, attr: setattr(obj, attr, val),
        'connect': lambda widget, setter: widget.editingFinished.connect(
            lambda w=widget: (setter(w.text()), w.clearFocus())
        )
    },
    'combo_box': {
        'widget': QComboBox,
        'args': [],
        'kwargs': {'editable': False},
        'getter': lambda obj, attr: getattr(obj, attr),
        'setter': lambda obj, val, attr: setattr(obj, attr, val),
        'connect': lambda widget, setter: widget.currentTextChanged.connect(setter)
    },
    'spin_box': {
        'widget': QSpinBox,
        'args': [],
        'kwargs': {'minimum': 0, 'maximum': 100},
        'getter': lambda obj, attr: getattr(obj, attr),
        'setter': lambda obj, val, attr: setattr(obj, attr, val),
        'connect': lambda widget, setter: widget.valueChanged.connect(setter)
    },
    'double_spin_box': {
        'widget': QDoubleSpinBox,
        'args': [],
        'kwargs': {'minimum': 0.0, 'maximum': 100.0, 'decimals': 2},
        'getter': lambda obj, attr: getattr(obj, attr),
        'setter': lambda obj, val, attr: setattr(obj, attr, val),
        'connect': lambda widget, setter: widget.valueChanged.connect(setter)
    },
    'list_widget': {
        'widget': QListWidget,
        'args': [],
        'kwargs': {},
        'getter': lambda obj, attr: getattr(obj, attr),
        'setter': lambda obj, val, attr: setattr(obj, attr, val),
        'connect': lambda widget, setter: widget.itemSelectionChanged.connect(
            lambda w=widget: setter(w.currentItem().text() if w.currentItem() else None)
        )
    },
    'unit_field': {
        'widget': UnitField,
        'args': [],
        'kwargs': {'default_unit': 'in', 'dpi': 300},
        'getter': lambda obj, attr: getattr(obj, attr),
        'setter': lambda obj, val, attr: setattr(obj, attr, val),
        'connect': lambda widget, setter: widget.editingFinished.connect(
            lambda w=widget: (setter(w.value()), w.clearFocus())
        )
    }
}
