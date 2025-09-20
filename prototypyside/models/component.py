from typing import Optional, Dict, TYPE_CHECKING
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QGraphicsItem

from prototypyside.models.component_template import ComponentTemplate
from prototypyside.utils.render_context import RenderContext, RenderMode, RenderRoute, TabMode

if TYPE_CHECKING:
	from prototypyside.models.layout_slot import LayoutSlot
	from prototypyside.services.proto_class import ProtoClass
	from prototypyside.services.proto_registry import ProtoRegistry
	from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry


class Component(ComponentTemplate):
	"""
	A movable, selectable instance created from a ComponentTemplate
	to be placed inside a LayoutSlot.
	"""
	def __init__(
		self,
		proto: "ProtoClass",
		pid: str,
		registry: "ProtoRegistry",
		ctx,
		geometry: "UnitStrGeometry" = None,
		name: Optional[str] = None,
		shape: str = "rounded_rect",
		file_path: Optional[Path] = None,
		csv_path: Optional[Path] = None,
		csv_row: Optional[Dict] = None,
		parent=None,
	):
		super().__init__(
			proto=proto,
			pid=pid,
			registry=registry,
			ctx = ctx,
			geometry=geometry,
			name=name,
			shape=shape,
			file_path=file_path,
			csv_path=csv_path,
			parent=parent,
		)

		# Will be set by the slot that owns/hosts this component
		self._csv_row: csv_row
		self._has_csv_conent = False
		self._slot_pid: Optional[str] = None

		# Flags
		self.setAcceptHoverEvents(True)
		self.setAcceptedMouseButtons(Qt.LeftButton)
		self.setFlag(QGraphicsItem.ItemIsSelectable, False)
		self.setFlag(QGraphicsItem.ItemIsMovable, False)
		self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
		for item in self.items:
			item.setFlag(QGraphicsItem.ItemIsSelectable, False)
			item.setFlag(QGraphicsItem.ItemIsMovable, False)

	# ---- QGraphicsItem overrides ------------------------------------------

	def boundingRect(self) -> QRectF:
		base = (self._bleed_rect if self._include_bleed else self._geometry).to(self.ctx.unit, dpi=self.dpi).rect
		return QRectF(0, 0, base.width(), base.height())
		
	# ---- Slot binding ------------------------------------------------------

	@property
	def slot_pid(self) -> Optional[str]:
		return self._slot_pid

	@slot_pid.setter
	def slot_pid(self, pid: Optional[str]) -> None:
		if pid != self._slot_pid:
			self._slot_pid = pid

	@property
	def has_csv_content(self):
		return self._has_csv_content

	@has_csv_content.setter
	def has_csv_content(self, state):
		if state == self._has_csv_content:
			return
		self._has_csv_content = not self._has_csv_content
	
	# Components (instances) are not cloneable; clone the template instead.
	def clone(self):
		obj = super().clone(self, register=True)
		for item in self.items:
			item._display_outline = False

	def set_csv_content(self, row: dict):
		"""
		Apply CSV row values
		"""
		if row:
			for item in self.items:
				content = row.get(item.name)
				if content is not None:
				    item.content = conten         
		return self
