    @Slot()
    def load_csv_and_merge(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV Data for Merge", "", "CSV Files (*.csv)")
        if path:
            self.perform_csv_merge(path)
        else:
            self.show_status_message("CSV import cancelled.", "info")

    def load_csv_and_merge_from_cli(self, path: str):
        self.perform_csv_merge(path, cli_mode=True)

    def perform_csv_merge(self, filepath: str, cli_mode: bool = False):
        try:
            with open(filepath, newline='', encoding='utf-8') as csvfile:
                header_line = csvfile.readline().strip()
                raw_headers = [h.strip() for h in header_line.split(',')]
                cleaned_headers = [h for h in raw_headers if h]

                csvfile.seek(0)
                if header_line:
                    csvfile.readline()

                reader = csv.reader(csvfile)
                data_rows_raw = list(reader)

                data_rows = []
                for row_list in data_rows_raw:
                    if not row_list or len(row_list) < len(cleaned_headers):
                        print(f"Warning: Skipping empty or malformed row with too few columns: {row_list}")
                        self.show_status_message(f"Warning: Skipping malformed row with too few columns.", "warning")
                        continue
                    if len(row_list) >= len(cleaned_headers):
                        row_data = {cleaned_headers[j]: row_list[j].strip() for j in range(len(cleaned_headers))}
                        data_rows.append(row_data)
                    else:
                        print(f"Warning: Skipping malformed row with too few columns: {row_list}")
                        self.show_status_message(f"Warning: Skipping malformed row with too few columns in row {len(data_rows)+1}.", "warning")

                if not data_rows:
                    self.show_status_message("CSV Merge Error: The CSV file is empty or has no data rows after processing headers.", "error")
                    return

            self.merged_templates = []

            for i, row_data in enumerate(data_rows):
                merged_template = ComponentTemplate.from_dict(self.template.to_dict(), parent=None)
                merged_template.background_image_path = self.template.background_image_path

                for element in merged_template.elements:
                    if element.name.startswith('@'):
                        field_name_in_template = element.name # Remove '@' for lookup
                        if field_name_in_template in row_data:
                            content = row_data[field_name_in_template]
                            if isinstance(element, ImageElement):
                                if content and Path(content).is_file():
                                    element.set_content(content)
                                else:
                                    print(f"Warning: Image file not found for {element.name} (row {i+1}): {content}")
                                    self.show_status_message(f"Warning: Image not found for field '{element.name}' in row {i+1}.", "warning")
                                    element.set_content("")
                            else:
                                element.set_content(content)
                        else:
                            print(f"Warning: Merge field '{element.name}' not found in CSV row {i+1}.")
                            self.show_status_message(f"Warning: Field '{element.name}' not found in CSV row {i+1}.", "warning")
                            element.set_content(f"<{element.name} Not Found>")
                self.merged_templates.append(merged_template)

            if not cli_mode:
                self.show_status_message(f"Successfully created {len(self.merged_templates)} merged template instances. You can now export them as PNGs or PDF.", "success")
            else:
                print(f"Successfully created {len(self.merged_templates)} merged template instances.")

        except FileNotFoundError:
            if not cli_mode:
                QMessageBox.critical(self, "CSV Merge Error", f"File not found: {filepath}")
                self.show_status_message(f"CSV Merge Error: File not found: {filepath}", "error")
            else:
                print(f"Error: File not found: {filepath}")
        except Exception as e:
            if not cli_mode:
                QMessageBox.critical(self, "CSV Merge Error", f"An error occurred during merge: {str(e)}")
                self.show_status_message(f"An error occurred during merge: {str(e)}", "error")
            else:
                print(f"Error during CSV merge: {str(e)}")

    @Slot()
    def export_png_gui(self):
        templates_to_export = self.merged_templates if self.merged_templates else [self.template]
        if not templates_to_export:
            self.show_status_message("PNG Export Failed: No templates to export.", "error")
            return
        output_dir_str = QFileDialog.getExistingDirectory(self, "Select Output Directory for PNGs")
        if not output_dir_str:
            self.show_status_message("PNG Export cancelled.", "info")
            return
        output_dir = Path(output_dir_str)
        if self.export_manager.export_png(templates_to_export, output_dir=output_dir, is_cli_mode=False):
            self.show_status_message(f"Successfully exported PNG(s) to {output_dir.resolve()}", "success")
        else:
            self.show_status_message("PNG Export Failed.", "error")

    @Slot()
    def export_pdf_gui(self):
        templates_to_export = self.merged_templates if self.merged_templates else [self.template]
        if not templates_to_export:
            self.show_status_message("PDF Export Failed: No templates to export.", "error")
            return
        dialog = PDFExportDialog(self)
        if not dialog.exec():
            self.show_status_message("PDF Export cancelled.", "info")
            return
        filenames = dialog.selectedFiles()
        if not filenames:
            self.show_status_message("PDF Export cancelled.", "info")
            return
        output_file_path = Path(filenames[0])
        page_size = dialog.get_page_size()
        if self.export_manager.export_pdf(
            templates_to_export,
            output_file_path=output_file_path,
            page_size=page_size,
            is_cli_mode=False
        ):
            self.show_status_message(f"Successfully exported PDF to {output_file_path.resolve()}", "success")
        else:
            QMessageBox.critical(self, "PDF Export Error", "An error occurred during PDF export.")
            self.show_status_message("PDF Export Failed.", "error")

    def export_png_cli(self, output_dir: Path):
        templates_to_export = self.merged_templates if self.merged_templates else [self.template]
        self.export_manager.export_png(templates_to_export, output_dir=output_dir, is_cli_mode=True)

    def export_pdf_cli(self, output_dir: Path):
        templates_to_export = self.merged_templates if self.merged_templates else [self.template]
        pdf_output_name = "merged_output.pdf" if self.merged_templates else "template.pdf"
        self.export_manager.export_pdf(templates_to_export, output_file_path=output_dir / pdf_output_name, is_cli_mode=True)
