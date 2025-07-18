from functools import lru_cache

from prototypyside.utils.unit_str_geometry import UnitStrGeometry
from prototypyside.utils.unit_str import UnitStr
from prototypyside.utils.ustr_helpers import geometry_with_px_pos, geometry_with_px_rect 

class UnitManager:
	def __init__(self, settings):

		@lru_cache(maxsize=1024)
		self.settings = settings 
		self.display_dpi = settings.display_dpi
		self.display_unit = settings.display_unit
		self.print_dpi = settings.print_dpi
		self._ustr_store = {}
		self._ustr_g_store = {}

	def new_ustr(self, owner, owner_prop, **kwargs):
		self._ustr_store[owner.pid] = {
			"measure": 
			"property": owner_prop,

		}
	def ustr(self, owner, owner_prop):
	
	def register(self, u_obj, owner, owner_prop, **kwargs):
		if isinstance(u_obj, UnitStr):
			return self._register_ustr(owner, owner_prop, **kwargs)
		elif isinstance(u_obj, UnitStrGeometry):
			return self._register_ustr_g(owner, owner_prop, **kwargs)
		else:
			raise TypeError
			print(f"{u_obj} is not a valid measurement. Must be UnitStr or UnitStrGeometry.")

    def regsiter_ustr_g(self, owner, owner_prop, **kwargs):
    	"""
        Create (or return existing) UnitStrGeometry.  
        kwargs might be x=..., y=..., width=..., height=..., unit=..., dpi=...
        """
        key = (owner, prop_name)
        if key not in self._ustr_geoms:
            g = UnitStrGeometry(**kwargs)
            self._ustr_geoms[key] = g
        return self._ustr_geoms[key]

    def _register_ustr(self, owner, owner_prop, **kwargs)
		"""
        Create (or return existing) UnitStr for this owner/prop.
        You can pass initial="1.25in" or initial="30mm", etc.
        """
        key = (owner, prop_name)
        if key not in self._ustrs:
            u = UnitStr(**kwargs)
            self._ustrs[key] = u
        return self._ustrs[key]

 	@lru_cache(maxsize=1024)
    def convert(self, value: str, *, to_unit: str, dpi: int = None) -> str:
        """
        Generic converter: parses `value` (e.g. "2.5in"), 
        then formats to `to_unit` (e.g. "63.5mm").
        """
        dpi = dpi or self.settings.dpi
        inches = parse_dimension(value)           # → float in inches
        return format_dimension(inches, to_unit, dpi=dpi)

    def to_display(self, value: str, unit: str = None) -> str:
        """Convert any dim to our display_unit using display DPI."""
        return self.convert(
            value,
            to_unit=unit or self.settings.unit,
            dpi=self.settings.dpi,
        )

    def to_print(self, value: str, unit: str = None) -> str:
        """Convert any dim to unit for print/export using print DPI."""
        return self.convert(
            value,
            to_unit=unit or self.settings.unit,
            dpi=self.settings.print_dpi,
        )

    # ——— React to Settings Changes ———

    def _on_dpi_changed(self, new_dpi: int):
        """
        If your settings object broadcasts DPI changes, call this.
        We’ll propagate the new DPI into every registered UnitStr/Geometry.
        """
        for u in self._ustrs.values():
            u.dpi = new_dpi
        for g in self._ustr_geoms.values():
            g.dpi = new_dpi

    def _on_unit_changed(self, new_unit: str):
        """
        If the user changes their preferred display unit,
        you may want to re–format or re–sync your UIs.
        """
        # nothing intrinsic to UnitStr, but you could re-render property panels, etc.

        

      	  



