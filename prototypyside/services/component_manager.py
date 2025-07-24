
class ComponentManager
COMPONENT_SIZES = {
    "cards": [
        {
            "name": "Standard Poker Size (Bridge Cut)",
            "dimensions": "UnitStrGeometry(width='2.5in', height='3.5in', unit='in', dpi=300)"
        },
        {
            "name": "Standard Poker Size (Graphic/Poker Cut)",
            "dimensions": "UnitStrGeometry(width='2.48in', height='3.46in', unit='in', dpi=300)"
        },
        {
            "name": "Bridge Size",
            "dimensions": "UnitStrGeometry(width='2.25in', height='3.5in', unit='in', dpi=300)"
        },
        {
            "name": "Mini American Size",
            "dimensions": "UnitStrGeometry(width='1.61in', height='2.48in', unit='in', dpi=300)"
        },
        {
            "name": "Mini European Size",
            "dimensions": "UnitStrGeometry(width='44mm', height='67mm', unit='mm', dpi=300)"
        },
        {
            "name": "Tarot Size",
            "dimensions": "UnitStrGeometry(width='2.75in', height='4.75in', unit='in', dpi=300)"
        },
        {
            "name": "European Playing Card Size",
            "dimensions": "UnitStrGeometry(width='61mm', height='97mm', unit='mm', dpi=300)"
        },
        {
            "name": "Small Square Card",
            "dimensions": "UnitStrGeometry(width='2in', height='2in', unit='in', dpi=300)"
        },
        {
            "name": "Large Square Card",
            "dimensions": "UnitStrGeometry(width='3.5in', height='3.5in', unit='in', dpi=300)"
        }
    ],
    "game_boards": [
        {
            "name": "Common Unfolded Size (e.g., Monopoly, Clue)",
            "dimensions": "UnitStrGeometry(width='20in', height='20in', unit='in', dpi=300)"
            "page_folds": 4
        },
        {
            "name": "Common Unfolded Size (e.g., Risk)",
            "dimensions": "UnitStrGeometry(width='20in', height='30in', unit='in', dpi=300)"
            "page_folds": 6
        },
        {
            "name": "Large Unfolded Size",
            "dimensions": "UnitStrGeometry(width='24in', height='24in', unit='in', dpi=300)"
        },
        {
            "name": "Small Unfolded Size (No Fold)",
            "dimensions": "UnitStrGeometry(width='12.5in', height='12.5in', unit='in', dpi=300)"
        },
        {
            "name": "Bi-Fold Board (Unfolded)",
            "dimensions": "UnitStrGeometry(width='9in', height='18in', unit='in', dpi=300)":
            "page_folds": 2
        },
        {
            "name": "Quad-Fold Board (Unfolded)",
            "dimensions": "UnitStrGeometry(width='18in', height='18in', unit='in', dpi=300)",
            "page_folds": 4
        },
        {
            "name": "Large Quad-Fold Board (Unfolded)",
            "dimensions": "UnitStrGeometry(width='20in', height='20in', unit='in', dpi=300)"
        },
        {
            "name": "Six-Fold Board (Unfolded)",
            "dimensions": "UnitStrGeometry(width='18in', height='27in', unit='in', dpi=300)"
        }
    ],
    "tokens": [
        {
            "name": "Small Square Token",
            "dimensions": "UnitStrGeometry(width='0.5in', height='0.5in', unit='in', dpi=300)"
        },
        {
            "name": "Medium Square Token",
            "dimensions": "UnitStrGeometry(width='0.75in', height='0.75in', unit='in', dpi=300)"
        },
        {
            "name": "Standard Square Token",
            "dimensions": "UnitStrGeometry(width='1in', height='1in', unit='in', dpi=300)"
        },
        {
            "name": "Large Square Token",
            "dimensions": "UnitStrGeometry(width='1.5in', height='1.5in', unit='in', dpi=300)"
        },
        {
            "name": "Small Round Token",
            "dimensions": "UnitStrGeometry(width='0.5in', height='0.5in', unit='in', dpi=300)"
        },
        {
            "name": "Medium Round Token",
            "dimensions": "UnitStrGeometry(width='0.75in', height='0.75in', unit='in', dpi=300)"
        },
        {
            "name": "Standard Round Token",
            "dimensions": "UnitStrGeometry(width='1in', height='1in', unit='in', dpi=300)"
        },
        {
            "name": "Large Round Token",
            "dimensions": "UnitStrGeometry(width='1.25in', height='1.25in', unit='in', dpi=300)"
        },
        {
            "name": "Small Hexagonal Token (Flat-to-flat)",
            "dimensions": "UnitStrGeometry(width='0.65in', height='0.75in', unit='in', dpi=300)"
        },
        {
            "name": "Medium Hexagonal Token (Flat-to-flat)",
            "dimensions": "UnitStrGeometry(width='1.19in', height='1.37in', unit='in', dpi=300)"
        },
        {
            "name": "Standard Hexagonal Token (Flat-to-flat)",
            "dimensions": "UnitStrGeometry(width='1.5in', height='1.73in', unit='in', dpi=300)"
        }
    ],
    "tiles": [
        {
            "name": "Standard Square Tile",
            "dimensions": "UnitStrGeometry(width='2in', height='2in', unit='in', dpi=300)"
        },
        {
            "name": "Large Square Tile",
            "dimensions": "UnitStrGeometry(width='3.9in', height='3.9in', unit='in', dpi=300)"
        },
        {
            "name": "Standard Hexagonal Tile (e.g., Catan Compatible)",
            "dimensions": "UnitStrGeometry(width='3.12in', height='3.60in', unit='in', dpi=300)"
        },
        {
            "name": "Common Hexagonal Tile",
            "dimensions": "UnitStrGeometry(width='3.25in', height='3.75in', unit='in', dpi=300)"
        }
    ],
    "player_boards": [
        {
            "name": "Typical Player Board (Small)",
            "dimensions": "UnitStrGeometry(width='8.5in', height='11in', unit='in', dpi=300)"
        },
        {
            "name": "Typical Player Board (Medium)",
            "dimensions": "UnitStrGeometry(width='10in', height='10in', unit='in', dpi=300)"
        },
        {
            "name": "Typical Player Board (Large, Single Sheet)",
            "dimensions": "UnitStrGeometry(width='12.5in', height='12.5in', unit='in', dpi=300)"
        }
    ],
    "rulebooks": [
        {
            "name": "US Letter Size Rulebook",
            "dimensions": "UnitStrGeometry(width='8.5in', height='11in', unit='in', dpi=300)"
        },
        {
            "name": "A4 Size Rulebook",
            "dimensions": "UnitStrGeometry(width='210mm', height='297mm', unit='mm', dpi=300)"
        }
    ],
    "punchboards": [
        {
            "name": "Typical Punchboard Thickness",
            "dimensions": "UnitStrGeometry(width='N/A', height='N/A', unit='mm', dpi=300) (Thickness is typically 1.5mm to 2mm)"
        },
        {
            "name": "Punchboard Size (Relative to Box)",
            "dimensions": "UnitStrGeometry(width='N/A', height='N/A', unit='in', dpi=300) (Typically 10mm smaller than the corresponding box dimension)"
        }
    ]
}