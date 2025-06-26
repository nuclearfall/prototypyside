# prototypyside/services/export_manager.py
import traceback
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSize, QSizeF, Qt, QRectF
from PySide6.QtGui import QPainter, QImage, QPixmap, QPdfWriter, QPageSize

# Assuming ComponentTemplate and ComponentGraphicsScene are importable
from prototypyside.models.component_template import ComponentTemplate
from prototypyside.views.graphics_scene import ComponentGraphicsScene
from prototypyside.widgets.page_size_selector import PageSizeSelector
from prototypyside.widgets.page_size_dialog import PageSizeDialog


class ExportManager:
    def __init__(self):
        # No initial state needed, as methods will take templates directly
        pass

    def _render_template_to_image(self, template: ComponentTemplate) -> Optional[QImage]:
        """
        Renders a single ComponentTemplate instance to a QImage.
        This is a helper method used by both PNG and PDF export.
        """
        image = QImage(template.width_px, template.height_px, QImage.Format_ARGB32)
        image.fill(Qt.transparent) # Start with a transparent background

        painter = QPainter(image)
        painter.setRenderHints(QPainter.Antialiasing |
                               QPainter.TextAntialiasing |
                               QPainter.SmoothPixmapTransform)

        # Draw background image if available
        if template.background_image_path:
            bg_pixmap = QPixmap(template.background_image_path)
            if not bg_pixmap.isNull():
                scaled_bg = bg_pixmap.scaled(
                    QSize(template.width_px, template.height_px),
                    Qt.IgnoreAspectRatio, # Stretch to fill
                    Qt.SmoothTransformation
                )
                painter.drawPixmap(0, 0, scaled_bg)

        # Create a temporary scene for rendering the template elements
        scene_rect = QRectF(0, 0, template.width_px, template.height_px)
        temp_scene = ComponentGraphicsScene(scene_rect, parent=None)
        for element in template.elements:
            temp_scene.addItem(element)

        # Render the scene content onto the QImage
        temp_scene.render(painter,
                          QRectF(0, 0, template.width_px, template.height_px),
                          temp_scene.sceneRect())
        painter.end() # End the painter before returning the image

        # Clean up temporary scene items to prevent memory leaks
        for item in temp_scene.items():
            temp_scene.removeItem(item)
        del temp_scene # Explicitly delete the temporary scene

        return image

    def export_png(self, templates: List[ComponentTemplate], output_dir: Path, is_cli_mode: bool = False) -> bool:
        """
        Exports a list of ComponentTemplates as individual PNG images.
        Handles both GUI (through MainDesignerWindow) and CLI modes.
        Returns True on success, False on failure.
        """
        if not templates:
            if is_cli_mode:
                print("CLI Error: No templates provided for PNG export.")
            return False

        output_dir.mkdir(parents=True, exist_ok=True) # Ensure directory exists

        export_count = 0
        for i, template_instance in enumerate(templates):
            image = self._render_template_to_image(template_instance)
            if image:
                if len(templates) > 1:
                    filename = f"merged_output_{i+1}.png"
                else:
                    filename = "template.png" # Default name for a single template export
                
                current_output_file = output_dir / filename
                
                try:
                    if image.save(str(current_output_file)):
                        export_count += 1
                        if is_cli_mode:
                            print(f"CLI Success: Exported {current_output_file}")
                    else:
                        if is_cli_mode:
                            print(f"CLI Error: Failed to save {current_output_file}")
                        else:
                            # In GUI mode, error messages would be handled by MainDesignerWindow
                            pass # MainDesignerWindow will show status message
                except Exception as e:
                    if is_cli_mode:
                        print(f"CLI Error: Exception saving {current_output_file}: {e}")
                    else:
                        pass # MainDesignerWindow will show status message
            else:
                if is_cli_mode:
                    print(f"CLI Warning: Could not render template {i+1} for PNG export.")
                else:
                    pass # MainDesignerWindow will show status message

        if export_count > 0:
            if is_cli_mode:
                print(f"CLI Success: Successfully exported {export_count} PNG(s) to {output_dir.resolve()}")
            return True
        else:
            if is_cli_mode:
                print("CLI Error: No PNG templates were exported.")
            return False

    def export_pdf(
        self,
        templates: list,
        output_file_path: Path,
        page_size: Optional[QPageSize] = None,
        is_cli_mode: bool = False
    ) -> bool:
        """
        Exports a list of ComponentTemplates as a single PDF document.
        Handles both GUI (through MainDesignerWindow) and CLI modes.
        Returns True on success, False on failure.
        """
        if not templates:
            if is_cli_mode:
                print("CLI Error: No templates provided for PDF export.")
            return False

        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        first_template = templates[0]
        print(f"[DEBUG] First template size: {first_template.width_in} in × {first_template.height_in} in @ {first_template.dpi} DPI")

        pdf_writer = QPdfWriter(str(output_file_path))
        pdf_writer.setResolution(first_template.dpi)

        if page_size:
            size_in = page_size.size(QPageSize.Inch)
            print(f"[DEBUG] Using provided page size: {size_in.width():.2f} × {size_in.height():.2f} in")
            pdf_writer.setPageSize(page_size)
        else:
            fallback_size = QPageSize(
                QSizeF(first_template.width_in, first_template.height_in),
                QPageSize.Inch,
                "Custom"
            )
            size_in = fallback_size.size(QPageSize.Inch)
            print(f"[DEBUG] Using fallback page size: {size_in.width():.2f} × {size_in.height():.2f} in")
            pdf_writer.setPageSize(fallback_size)

        painter = QPainter(pdf_writer)
        success = False

        try:
            for i, template_instance in enumerate(templates):
                print(f"[DEBUG] Rendering template {i+1}/{len(templates)}")
                if i > 0:
                    pdf_writer.newPage()
                    print(f"[DEBUG] Added new page")

                image = self._render_template_to_image(template_instance)
                if image:
                    print(f"[DEBUG] Image size: {image.width()} x {image.height()} px")
                    target_rect = QRectF(0, 0, template_instance.width_px, template_instance.height_px)
                    painter.drawImage(target_rect, image)
                else:
                    print(f"[WARNING] Could not render template {i+1} to image.")
                    if is_cli_mode:
                        print(f"CLI Warning: Skipping template {i+1} due to render failure.")

            success = True
            if is_cli_mode:
                print(f"CLI Success: Successfully exported PDF to {output_file_path.resolve()}")

        except Exception as e:
            print(f"[ERROR] Exception occurred during PDF export: {e}")
            traceback.print_exc()  # Print full stack trace to console

        finally:
            if painter.isActive():
                print("[DEBUG] Ending painter...")
                painter.end()

        return success