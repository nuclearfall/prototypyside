# validator.py

import json
from pathlib import Path
from jsonschema import RefResolver, validate
from jsonschema.exceptions import ValidationError

class SchemaValidator:
    # map pid prefixes → schema filenames
    PREFIX_MAP = {
        "ct": "component_template.json",
        "lt": "layout_template.json",
        "ie": "image_element.json",
        "te": "text_element.json",
        "ls": "layout_slot.json",
    }

    def __init__(self, schema_dir):
        self.schema_dir = schema_dir
        self.schema_store = self._load_schemas()

    def _load_schemas(self):
        """Load every .json and key the store by both filename and $id (if present)."""
        store = {}

        for schema_file in self.schema_dir.glob("*.json"):
            text = schema_file.read_text(encoding="utf-8")
            try:
                schema = json.loads(text)
            except json.JSONDecodeError as e:
                print(f"✖ JSON error in {schema_file.name}: {e}")
                raise
            schema = json.loads(schema_file.read_text(encoding="utf-8"))
            # always register under the filename
            store[schema_file.name] = schema
            # also register under its $id if it has one
            sid = schema.get("$id")
            if sid:
                store[sid] = schema
        return store

    def validate(self,
                 data: dict,
                 schema_name: str = None,
                 auto_detect: bool = True
                ) -> (bool, str | None):
        """
        Validate `data` against a schema.
        - If schema_name is provided, we use that directly.
        - Else, if `data["pid"]` exists, we pick via PREFIX_MAP.
        - Else if auto_detect, we fall back to simple shape detection for UnitStr vs UnitStrGeometry.
        Returns (True, None) on success, or (False, "Error message") on failure.
        """
        # 1) pick the schema key
        if schema_name:
            key = schema_name
        else:
            pid = data.get("pid")
            if pid:
                prefix = pid.split("_", 1)[0]
                key = self.PREFIX_MAP.get(prefix)
                if not key:
                    raise ValueError(f"Unknown PID prefix: {prefix}")
            elif auto_detect:
                # heuristic for UnitStr vs UnitStrGeometry
                datakeys = set(data.keys())
                # full UnitStr has these exact keys
                if {"in","mm","cm","pt","px","unit","dpi"}.issubset(datakeys):
                    key = "unit_str.json"
                # UnitStrGeometry will have pos & rect
                elif {"pos","rect","unit","dpi","print_dpi"}.issubset(datakeys):
                    key = "unit_str_geometry.json"
                else:
                    raise ValueError("Cannot auto-detect schema: no pid and unknown shape")
            else:
                raise ValueError("Data must have a 'pid' or you must pass `schema_name`")

        # 2) retrieve the schema
        schema = self.schema_store.get(key)
        if not schema:
            raise FileNotFoundError(f"Schema '{key}' not found in {self.schema_dir!r}")

        # 3) set up a resolver for any $ref inside that schema
        resolver = RefResolver(
            base_uri=self.schema_dir.resolve().as_uri() + "/",
            referrer=schema,
            store=self.schema_store
        )

        # 4) run the validation
        try:
            validate(instance=data, schema=schema, resolver=resolver)
            return True, None
        except ValidationError as e:
            # build a human-friendly path like "items->0->geometry->unit"
            path = "->".join(map(str, e.path)) or "(root)"
            return False, f"Validation Error in {path}: {e.message}"


# # validator.py
# import json
# from pathlib import Path
# from jsonschema import RefResolver, validate
# from jsonschema.exceptions import ValidationError


# class SchemaValidator:
#     def __init__(self, schema_dir: Path):
#         self.schema_dir = schema_dir
#         self.schema_store = self._load_schemas()

#     def _load_schemas(self):
#         """Loads all schemas from the schema directory."""
#         store = {}
#         for schema_file in self.schema_dir.glob("*.json"):
#             with open(schema_file, "r", encoding="utf-8") as f:
#                 schema = json.load(f)
#                 # The store uses the schema's "$id" as the key
#                 # Use schema_file.name for the store key if $id is not always present,
#                 # or ensure $id matches the filename for easier lookup
#                 if "$id" in schema:
#                     store[schema["$id"]] = schema
#                 else:
#                     # Fallback: use filename as ID if $id is missing
#                     store[schema_file.name] = schema
#         return store

#     def validate(self, data: dict):
#         """Validates data against the appropriate schema."""
#         pid = data.get("pid")
#         if not pid:
#             raise ValueError("Data must have a 'pid' to determine the schema.")

#         prefix = pid[:2]
#         if prefix == 'ct':
#             schema_key = "component_template.json" # Use the key you store
#         elif prefix == "lt":
#             schema_key = "layout_template.json" # Use the key you store
#         elif prefix == "ie":
#             schema_key = "image_element.json" # Use the key you store
#         elif prefix == "te":
#             schema_key = "text_element.json" # Use the key you store
#         elif prefix == "ls":
#             schema_key = "layout_slot.json" # Use the key you store
#         else:
#             raise ValueError(f"Unknown PID prefix: {prefix}")

#         # Ensure the schema exists in the store before proceeding
#         if schema_key not in self.schema_store:
#             raise FileNotFoundError(f"Schema '{schema_key}' not found in the loaded schemas.")

#         main_schema = self.schema_store[schema_key]

#         # The resolver needs the store to find referenced schemas
#         # Provide the main_schema as the referrer
#         resolver = RefResolver(
#             base_uri=self.schema_dir.resolve().as_uri() + "/",
#             referrer=main_schema, # THIS IS THE KEY CHANGE
#             store=self.schema_store
#         )

#         try:
#             validate(instance=data, schema=main_schema, resolver=resolver)
#             return True, None # Indicates success
#         except ValidationError as e:
#             # Return failure and a user-friendly error message
#             error_path = "->".join(map(str, e.path))
#             return False, f"Validation Error in '{error_path}': {e.message}"