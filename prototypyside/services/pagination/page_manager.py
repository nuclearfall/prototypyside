import re
import math
import uuid
from typing import Dict, List, Tuple, Any, TYPE_CHECKING

from prototypyside.utils.units.unit_str import UnitStr
from prototypyside.utils.units.unit_str_geometry import UnitStrGeometry
from prototypyside.services.undo_commands import ChangePropertiesCommand
if TYPE_CHECKING:
    from prototypyside.models.layout_template import LayoutTemplate

def parse_prop_name(s: str) -> Tuple[str, str]:
    """
    Splits `s` into (before, after) at the *first* underscore.
    If there is no underscore, returns (s, '').
    """
    m = re.match(r'^([^_]+)_(.*)$', s)
    if m:
        # group(1) is everything up to the first “_”
        # group(2) is everything after it (including any further underscores)
        return m.group(1), m.group(2)

    else:
        # no underscore found
        return s, ''

PAGE_SIZES = {
    # North American Standard & Common Wide-Format Sizes
    "Letter (8.5x11 inches)": UnitStrGeometry(width="8.5in", height="11.0in", unit="in"),
    "Legal (8.5x14 inches)": UnitStrGeometry(width="8.5in", height="14.0in", unit="in"),
    "Tabloid / Ledger (11x17 inches)": UnitStrGeometry(width="11.0in", height="17.0in", unit="in"),
    "Super B (13x19 inches)": UnitStrGeometry(width="13.0in", height="19.0in", unit="in"),

    # International Standard (ISO 216 "A" Series) & Common Wide-Format Sizes
    "A4 (210x297 mm)": UnitStrGeometry(width="210mm", height="297mm", unit="mm"),
    "A3 (297x420 mm)": UnitStrGeometry(width="297mm", height="420mm", unit="mm"),
    "A3+ (329x483 mm)": UnitStrGeometry(width="329mm", height="483mm", unit="mm"), # Equivalent to Super B
    "A2 (420x594 mm)": UnitStrGeometry(width="420mm", height="594mm", unit="mm"),
    "A1 (594x841 mm)": UnitStrGeometry(width="594mm", height="841mm", unit="mm"),
    "A0 (841x1189 mm)": UnitStrGeometry(width="841mm", height="1189mm", unit="mm"),
}

PRINT_POLICIES = {
    'Letter: 3x3 Standard Cards (2.5"x3.5")': {
        "page_size": "Letter (8.5x11 inches)",
        "geometry": UnitStrGeometry(width="8.5in", height="11in", unit="in", dpi=300),
        "orientation": False,
        "rows": 3,
        "columns": 3,
        "whitespace": [            # margins: top, bottom, left, right — spacing: x, y
            UnitStr("0.25in", dpi=300), 
            UnitStr("0.25in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.0in", dpi=300),
            UnitStr("0.0in", dpi=300)
        ],
        "duplex": False,
        "oversized": False,
        "lock_at": 1,
        # "component_geometry": UnitStrGeometry(width="2.5in", height="3.5in", unit="in", dpi=300),
        # "component_bleed": UnitStrGeometry(width="0.0in", height="0.0in", unit="in", dpi=300)
    },
    'Letter: 2x4 Standard Front & Back (2.5"x3.5")': {
        "page_size": "Letter (8.5x11 inches)",
        "geometry": UnitStrGeometry(width="11.0in", height="8.5in", unit="in", dpi=300),
        "orientation": True,
        "rows": 2,
        "columns": 4,
        "whitespace": [            # margins: top, bottom, left, right — spacing: x, y
            UnitStr("0.75in", dpi=300), 
            UnitStr("0.75in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.0in", dpi=300),
            UnitStr("0.0in", dpi=300)
        ],
        "oversized": False,
        "static": False,
        "lock_at": 2,
        # "component_geometry": UnitStrGeometry(width="2.5in", height="3.5in", unit="in", dpi=300),
        # "component_bleed": UnitStrGeometry(width="0.0in", height="0.0in", unit="in", dpi=300)
    },
    'Letter: 2x4 Standard Front & Back (2.5"x3.5")': {
        "page_size": "Letter (8.5x11 inches)",
        "geometry": UnitStrGeometry(width="8.5in", height="11in", unit="in", dpi=300),
        "orientation": True,
        "rows": 3,
        "columns": 3,
        "whitespace": [            # margins: top, bottom, left, right — spacing: x, y
            UnitStr("0.25in", dpi=300), 
            UnitStr("0.25in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.5in", dpi=300),
            UnitStr("0.0in", dpi=300),
            UnitStr("0.0in", dpi=300)
        ],
        "lock_at": 2,
        # "component_geometry": UnitStrGeometry(width="2.5in", height="3.5in", unit="in", dpi=300),
        # "component_bleed": UnitStrGeometry(width="0.0in", height="0.0in", unit="in", dpi=300)
    }
}

class PageManager:

    def set_policy_props(self, layout, policy, undo_stack):
        m = re.match(r'^([^_]+)_(.*)$', s)
        if policy not in self.policies or not self.policies.get(policy):
            return
        params = [(p, v) for p, v in policies.get(policy).items()]
        prop_names = new_values = old_values = []

        for prop_key, value in params:
            _, prop = parse_prop_name(prop_key)
            if hasattr(template, prop):
                prop_names.append(prop)
                new_values.append(value)
                old_values.append(getattr(template, prop))

        page_props_command = ChangePropertiesCommand(template, prop_names, new_values, old_values)
        undo_stack.push(page_props_command)
        pritn(template.to_dict())


    def grid_by_slots_dims(
        template: "LayoutTemplate",
        slot_dim: UnitStrGeometry = UnitStrGeometry(width="2.5in", height="3.5in", unit="in", dpi=300),
        whitespace: List[UnitStr] = [
                UnitStr("0.25in", dpi=300),
                UnitStr("0.25in", dpi=300),
                UnitStr("0.5in", dpi=300),
                UnitStr("0.5in", dpi=300),
                UnitStr("0.0in", dpi=300),
                UnitStr("0.0in", dpi=300),
            ]
    ) -> Tuple[Dict[str, Any], Tuple[str, str]]:
        """
        Compute the densest grid of slot_dim rectangles on the template.page,
        respecting at least the given whitespace [top, bottom, left, right, spacing_x, spacing_y].
        Returns (policies_dict, (message, level)).
        """

        # 1) Page geometry & orientation
        page_geo = template.geometry  # UnitStrGeometry
        orientation = template.orientation  # "portrait" or "landscape"

        # 2) Fill defaults if needed
        if whitespace is None:
            # margins: .5in all around, zero spacing
            whitespace = [
                UnitStr("0.5in", dpi=300),
                UnitStr("0.5in", dpi=300),
                UnitStr("0.5in", dpi=300),
                UnitStr("0.5in", dpi=300),
                UnitStr("0.0in", dpi=300),
                UnitStr("0.0in", dpi=300),
            ]
        top, bottom, left, right, spacing_x, spacing_y = whitespace

        # 3) Convert everything to pixels for exact math
        pw = float(page_geo.to("px", dpi=300).width)
        ph = float(page_geo.to("px", dpi=300).height)
        sw = float(slot_dim.to("px", dpi=slot_dim.dpi).width)
        sh = float(slot_dim.to("px", dpi=slot_dim.dpi).height)
        mx = float(spacing_x.to("px", dpi=spacing_x.dpi))
        my = float(spacing_y.to("px", dpi=spacing_y.dpi))
        ml = float(left.to("px", dpi=left.dpi))
        mr = float(right.to("px", dpi=right.dpi))
        mt = float(top.to("px", dpi=top.dpi))
        mb = float(bottom.to("px", dpi=bottom.dpi))

        # 4) Try both orientations of slot (allow rotation)
        def compute_counts(slot_w, slot_h):
            avail_w = pw - (ml + mr)
            avail_h = ph - (mt + mb)
            cols = max(0, math.floor((avail_w + mx) / (slot_w + mx)))
            rows = max(0, math.floor((avail_h + my) / (slot_h + my)))
            return rows, cols

        r1, c1 = compute_counts(sw, sh)
        r2, c2 = compute_counts(sh, sw)
        # pick whichever packs more slots
        if r2 * c2 > r1 * c1:
            rows, cols = r2, c2
            sw, sh = sh, sw  # we’ll record rotated dims
        else:
            rows, cols = r1, c1

        # 5) If nothing fits, bail out
        if rows < 1 or cols < 1:
            return {}, ("Slot dimensions too large to fit on page", "error")

        # 6) Compute leftover space and grow margins symmetrically
        used_w = cols * sw + (cols - 1) * mx
        used_h = rows * sh + (rows - 1) * my
        extra_w = pw - used_w
        extra_h = ph - used_h

        final_ml = (extra_w / 2.0)
        final_mr = extra_w - final_ml
        final_mt = (extra_h / 2.0)
        final_mb = extra_h - final_mt

        # Convert back to UnitStr (in the template’s unit)
        def px_to_unitstr(px: float) -> UnitStr:
            # px → inches → desired unit
            inches = px / template.geometry.dpi
            return UnitStr(f"{inches}in", dpi=template.geometry.dpi)

        final_whitespace = [
            px_to_unitstr(final_mt),
            px_to_unitstr(final_mb),
            px_to_unitstr(final_ml),
            px_to_unitstr(final_mr),
            spacing_x,
            spacing_y,
        ]

        # 7) Build the policy entry
        # Unique key
        # key = f"custom_{uuid.uuid4().hex[:8]}"
        desc = (
            f"Custom: {rows}×{cols} grid of "
            f"{slot_dim.width}×{slot_dim.height} slots on "
            f"{orientation.capitalize()} page"
        )

        policy = {
            desc: {
                # "description": desc,
                "page_geometry": page_geo,
                "page_orientation": orientation,
                "page_whitespace": final_whitespace,
                "slot_geometry": slot_dim,
            }
        }

        return policy, ("", "Info")