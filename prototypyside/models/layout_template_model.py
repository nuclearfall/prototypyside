class UnitStrWhitespace:
    margin_top: UnitStr
    margin_bottom: UnitStr
    margin_left: UnitStr
    
    def __init__(self):


class LayoutTemplate:
    pid: str
    name: str
    registry: ProtoRegistry
    pagination_policy: str
    geometry: UnitStrGeometry
    whitespace: UnitStrWhitespace

    UnitStrGeometry(width="8.5in", height="11in", unit="in", dpi=300), 
                page_size = "letter", parent=None,
                rows=3, columns=3, dpi=300,
                name=None, margin_top=UnitStr("0.25in"), margin_bottom = UnitStr("0.25in"),
                margin_left = UnitStr("0.5in"), margin_right = UnitStr("0.5in"),
                spacing_x = UnitStr("0.0in"), spacing_y  = UnitStr("0.0in"), orientation=False
pol = PRINT_POLICIES.get(pagination_policy)
self._rows = pol.get("rows")
self._columns = pol.get("columns")
self._page_size = pol.get("page_size")
self._geometry = PAGE_SIZES.get(self._page_size)
self._whitespace = pol.get("whitespace")# ordered [top, bottom, left, right, spacing_x, spacing_y]
self._orientation = pol.get("orientation")
self.lock_at: int = pol.get("lock_at") # The number of components a given policy will accept.
####

self._dpi = 300
self._unit = "px"
self._content = None
self.items = []
        self.setAcceptHoverEvents(True)

        self.set_policy_props(pagination_policy)

    def set_policy_props(self, policy):
        if policy in PRINT_POLICIES:
            for prop, value in PRINT_POLICIES.get(policy).items():
                fprop = f"_{prop}"
                if hasattr(self, prop):
                    setattr(self, prop, value)

    @property
    def pagination_policy(self):
        return self._pagination_policy
    
    @pagination_policy.setter
    def pagination_policy(self, pol):
        if pol != self._pagination_policy and pol in PRINT_POLICIES:
            self._pagination_policy = pol
            self._rows = pol.get("rows")
            self._columns = pol.get("columns")
            self._geometry = pol.get("geometry")
            self._whitespace = pol.get("whitespace")# ordered [top, bottom, left, right, spacing_x, spacing_y]
            self._orientation = pol.get("orientation")
            self.lock_at: int = pol.get("lock_at") # The number of components a given policy will accept.
            self.updateGrid()

    @property