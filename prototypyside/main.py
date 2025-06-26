# prototypyside/main.py

import sys
from pathlib import Path
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtWidgets import QApplication, QMessageBox
import json

# Import your main window class
from prototypyside.views.main_window import MainDesignerWindow
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.services.export_manager import ExportManager # NEW: Import ExportManager

if __name__ == "__main__":
    # macOS: Enable native gesture support
    if sys.platform == 'darwin':
        QApplication.setAttribute(Qt.AA_NativeWindows, True)
        print("macOS native window attributes set")

    app = QApplication(sys.argv)

    # Command-line argument parsing
    template_path = None
    csv_path = None
    export_png_flag = False
    export_pdf_flag = False
    export_dir = None

    args = sys.argv[1:] # Skip script name

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--template":
            if i + 1 < len(args):
                template_path = args[i + 1]
                i += 1
            else:
                print("Error: --template flag requires a path to a template file.")
                sys.exit(1)
        elif arg == "--csv":
            if i + 1 < len(args):
                csv_path = args[i + 1]
                i += 1
            else:
                print("Error: --csv flag requires a path to a CSV file.")
                sys.exit(1)
        elif arg == "--export-png":
            export_png_flag = True
        elif arg == "--export-pdf":
            export_pdf_flag = True
        elif arg == "--export-dir":
            if i + 1 < len(args):
                export_dir = Path(args[i + 1])
                i += 1
            else:
                print("Error: --export-dir flag requires a path to an output directory.")
                sys.exit(1)
        else:
            print(f"Warning: Unknown argument: {arg}")
        i += 1

    # Determine if we are in any CLI-driven mode that bypasses the GUI
    cli_mode_active = export_png_flag or export_pdf_flag or (template_path and not sys.stdin.isatty())

    designer = MainDesignerWindow()
    export_manager = ExportManager() # NEW: Instantiate ExportManager

    # Set cli_mode for the MainDesignerWindow instance for internal message handling
    designer.set_cli_mode(cli_mode_active)

    template_loaded_successfully = False

    if template_path:
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            new_template = ComponentTemplate.from_dict(data, parent=designer)
            designer.load_template_instance(new_template)
            print(f"CLI: Template loaded from {template_path}")
            template_loaded_successfully = True
        except FileNotFoundError:
            print(f"CLI Error: Template file not found: {template_path}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"CLI Error: Invalid JSON format in template file: {template_path}")
            sys.exit(1)
        except Exception as e:
            print(f"CLI Error: An unexpected error occurred while loading template from {template_path}: {e}")
            sys.exit(1)
    else:
        if not cli_mode_active:
            pass
    csv_loaded_successfully = False
    if csv_path and template_loaded_successfully:
        try:
            designer.load_csv_and_merge_from_cli(csv_path)
            csv_loaded_successfully = True
        except FileNotFoundError:
            print(f"CLI Error: CSV file not found: {csv_path}")
            sys.exit(1)
        except Exception as e:
            print(f"CLI Error: An unexpected error occurred during CSV merge from {csv_path}: {e}")
            sys.exit(1)
    elif csv_path and not template_loaded_successfully:
        print("CLI Error: Cannot load CSV without a template. Please specify --template.")
        sys.exit(1)


    # Handle export based on flags
    if export_png_flag or export_pdf_flag:
        if not template_loaded_successfully:
            print("CLI Error: Cannot export without a loaded template. Please specify --template.")
            sys.exit(1)
        if csv_path and not designer.merged_templates: # Check if merged_templates is populated
            print("CLI Error: CSV merge did not produce any templates, cannot proceed with export.")
            sys.exit(1)

        # Determine templates to export (merged if available, else current)
        templates_to_export = designer.merged_templates if designer.merged_templates else [designer.template]

        if not export_dir:
            export_dir = Path("./cli_exports") # Default output directory for CLI exports
            export_dir.mkdir(parents=True, exist_ok=True)
            print(f"CLI: No --export-dir specified, defaulting to '{export_dir.resolve()}'")
        elif not export_dir.is_dir():
            print(f"CLI Error: --export-dir must be a directory: {export_dir}")
            sys.exit(1)
        
        # Ensure the directory exists
        export_dir.mkdir(parents=True, exist_ok=True)

        export_successful = True

        if export_png_flag:
            # Call ExportManager's export_png method
            if not export_manager.export_png(templates_to_export, output_dir=export_dir, is_cli_mode=True):
                export_successful = False
            
        if export_pdf_flag:
            # Call ExportManager's export_pdf method
            # For PDF, we'll name the single output file "merged_output.pdf" or "template.pdf"
            pdf_output_name = "merged_output.pdf" if designer.merged_templates else "template.pdf"
            if not export_manager.export_pdf(templates_to_export, output_file_path=export_dir / pdf_output_name, is_cli_mode=True):
                export_successful = False

        if not export_successful:
            sys.exit(1) # Exit with error code if any export failed

        QCoreApplication.quit() # Ensure QApplication exits after operation
    else:
        # Only show the main window if not in headless export mode
        designer.show()
        sys.exit(app.exec())