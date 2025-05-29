# prototypyside/services/export_manager.py

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSize, Qt, QRectF
from PySide6.QtGui import QPainter, QImage, QPixmap, QPdfWriter

# Assuming GameComponentTemplate and GameComponentGraphicsScene are importable
from prototypyside.models.game_component_template import GameComponentTemplate
from prototypyside.views.graphics_scene import GameComponentGraphicsScene


class ExportManager:
    def __init__(self):
        # No initial state needed, as methods will take templates directly
        pass

    def _render_template_to_image(self, template: GameComponentTemplate) -> Optional[QImage]:
        """
        Renders a single GameComponentTemplate instance to a QImage.
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
        temp_scene = GameComponentGraphicsScene(template.width_px, template.height_px, None)
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

    def export_png(self, templates: List[GameComponentTemplate], output_dir: Path, is_cli_mode: bool = False) -> bool:
        """
        Exports a list of GameComponentTemplates as individual PNG images.
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
                    filename = "current_template.png" # Default name for a single template export
                
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

    def export_pdf(self, templates: List[GameComponentTemplate], output_file_path: Path, is_cli_mode: bool = False) -> bool:
        """
        Exports a list of GameComponentTemplates as a single PDF document.
        Handles both GUI (through MainDesignerWindow) and CLI modes.
        Returns True on success, False on failure.
        """
        if not templates:
            if is_cli_mode:
                print("CLI Error: No templates provided for PDF export.")
            return False

        output_file_path.parent.mkdir(parents=True, exist_ok=True) # Ensure parent directory exists

        pdf_writer = QPdfWriter(str(output_file_path))
        first_template = templates[0] # Assume all templates have same dimensions for PDF pages
        pdf_writer.setPageSizeMM(QSizeF(first_template.width_in * 25.4, first_template.height_in * 25.4))
        pdf_writer.setResolution(first_template.dpi) # Use template DPI for PDF resolution

        painter = QPainter(pdf_writer)

        try:
            for i, template_instance in enumerate(templates):
                if i > 0:
                    pdf_writer.newPage() # Add new page for each template after the first

                image = self._render_template_to_image(template_instance)
                if image:
                    painter.drawImage(QRectF(0, 0, template_instance.width_px, template_instance.height_px),
                                      image)
                else:
                    if is_cli_mode:
                        print(f"CLI Warning: Could not render template {i+1} for PDF export.")
                    else:
                        pass # MainDesignerWindow will show status message

            painter.end()
            if is_cli_mode:
                print(f"CLI Success: Successfully exported PDF to {output_file_path.resolve()}")
            return True
        except Exception as e:
            if is_cli_mode:
                print(f"CLI Error: An error occurred during PDF export: {str(e)}")
            else:
                pass # MainDesignerWindow will show status message
            if painter.isActive():
                painter.end()
            return False