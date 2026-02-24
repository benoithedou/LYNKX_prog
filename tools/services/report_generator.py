"""Production test PDF report generator.

Generates PDF reports with test results, RF measurements, and
environmental data for each tested device.
"""
import os
from typing import Dict, List, Optional
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from services.state_manager import AppState
from utils.constants import TEST_NAMES, DEVICE_TYPE_SUMMIT


class ReportGenerator:
    """Generates production test PDF reports."""

    def __init__(self, state: AppState):
        self._state = state

    def generate(
        self,
        device_id: str,
        test_results: Dict[str, bool],
        operator_name: str = "",
        output_dir: str = "./Reports"
    ) -> str:
        """
        Generate a production test PDF report.

        Args:
            device_id: Device barcode ID
            test_results: Dict of test_name -> passed (True/False)
            operator_name: Operator name
            output_dir: Output directory for PDF files

        Returns:
            Path to generated PDF file
        """
        os.makedirs(output_dir, exist_ok=True)

        # Build status list
        status = []
        for name in TEST_NAMES:
            status.append("OK" if test_results.get(name, False) else "NOT OK")

        # Device info
        device_type = self._get_device_type_name()
        hw_version = self._state.hardware_version
        serial_info = f" Device type : {device_type} {hw_version} : {device_id}"
        title_name = f"Operator name : {operator_name}" if operator_name else ""

        # Create PDF
        pdf = FPDF('P', 'mm', 'A4')
        pdf_width = pdf.w
        pdf.add_page()

        # Title
        pdf.set_font('Helvetica', '', 16)
        title = 'Production check list'
        self._center_string(title, pdf, pdf_width)
        pdf.cell(pdf.get_string_width(title), 12, title)
        pdf.ln()

        # Device info
        pdf.set_font('Helvetica', '', 12)
        self._center_string(serial_info, pdf, pdf_width)
        pdf.cell(pdf.get_string_width(serial_info), 10, serial_info)
        pdf.ln()

        # Table 1: Component tests
        data_table_1 = {
            "Components": list(TEST_NAMES),
            "Status": status,
        }
        self._create_table(
            pdf, table_data=data_table_1, title=title_name,
            align_header='C', align_data='C',
            cell_width=[60, 60], x_start='C',
            emphasize_data=["OK", "NOT OK"],
            emphasize_color=[(0, 255, 0), (255, 0, 0)]
        )
        pdf.ln()

        # Table 2: RF measurements
        data_table_2 = {
            "Technology": ["BLE", "LoRa"],
            "Frequency (Hz)": [self._state.max_freq_ble, self._state.max_freq_lora],
            "Power (dBm)": [self._state.max_power_ble, self._state.max_power_lora],
            "Status": ["OK", "OK"]
        }
        self._create_table(
            pdf, table_data=data_table_2, title='RF Testing',
            align_header='C', align_data='C',
            cell_width=[30, 30, 30, 30], x_start='C',
            emphasize_data=["OK", "NOT OK"],
            emphasize_color=[(0, 255, 0), (255, 0, 0)]
        )
        pdf.ln()

        # Table 3: Environmental (only for LYNKX+ SUMMIT)
        if self._state.device_type == DEVICE_TYPE_SUMMIT:
            data_table_3 = {
                "Environment caracteristics": ["Pressure (mbar)"],
                "Value": [self._state.current_pressure],
                "Status": ["OK"]
            }
            self._create_table(
                pdf, table_data=data_table_3, title='Testing environment',
                align_header='C', align_data='C',
                cell_width=[40, 40, 40], x_start='C',
                emphasize_data=["OK", "NOT OK"],
                emphasize_color=[(0, 255, 0), (255, 0, 0)]
            )

        # Save
        filename = f"Device_ID_{device_id}_OK.pdf"
        filepath = os.path.join(output_dir, filename)
        pdf.output(filepath)
        return filepath

    def _get_device_type_name(self) -> str:
        if self._state.device_type == DEVICE_TYPE_SUMMIT:
            return "LYNKX+ SUMMIT"
        return "LYNKX+"

    @staticmethod
    def _center_string(text: str, pdf: FPDF, pdf_width: float) -> None:
        str_width = pdf.get_string_width(text)
        pdf.set_x((pdf_width - str_width) / 2)

    @staticmethod
    def _create_table(
        pdf, table_data, title='', data_size=9, title_size=11,
        align_data='L', align_header='L', cell_width='even',
        x_start='x_default', emphasize_data=None, emphasize_style=None,
        emphasize_color=None
    ):
        """Create a table in the PDF (ported from production_test.py)."""
        if emphasize_data is None:
            emphasize_data = []
        if emphasize_color is None:
            emphasize_color = [(0, 0, 0)]

        default_style = pdf.font_style
        if emphasize_style is None:
            emphasize_style = default_style

        # Convert dict to list-of-lists
        if isinstance(table_data, dict):
            header = list(table_data.keys())
            data = [list(a) for a in zip(*table_data.values())]
        else:
            header = table_data[0]
            data = table_data[1:]

        # Get column widths
        if cell_width == 'even':
            col_width = pdf.epw / len(header) - 1
        elif isinstance(cell_width, list):
            col_width = cell_width
        else:
            col_width = int(cell_width)

        line_height = pdf.font_size * 2.5
        pdf.set_font(size=title_size)

        # Center table
        if x_start == 'C':
            if isinstance(col_width, list):
                table_width = sum(col_width)
            else:
                table_width = col_width * len(header)
            x_start = (pdf.w - table_width) / 2
            pdf.set_x(x_start)
        elif isinstance(x_start, int):
            pdf.set_x(x_start)
        elif x_start == 'x_default':
            pdf.set_x(pdf.l_margin)

        # Title
        if title:
            pdf.multi_cell(
                0, line_height, title, border=0, align='j',
                new_x=XPos.RIGHT, new_y=YPos.TOP,
                max_line_height=pdf.font_size
            )
            pdf.ln(line_height)

        pdf.set_font(size=data_size)

        # Header
        y1 = pdf.get_y()
        x_left = x_start if isinstance(x_start, (int, float)) else pdf.get_x()
        if isinstance(x_start, (int, float)):
            pdf.set_x(x_start)

        if isinstance(col_width, list):
            for i, datum in enumerate(header):
                pdf.multi_cell(
                    col_width[i], line_height, datum, border=0,
                    align=align_header, new_x=XPos.RIGHT, new_y=YPos.TOP,
                    max_line_height=pdf.font_size
                )
            x_right = pdf.get_x()
            pdf.ln(line_height)
            y2 = pdf.get_y()
            pdf.line(x_left, y1, x_right, y1)
            pdf.line(x_left, y2, x_right, y2)

            for row in data:
                if isinstance(x_start, (int, float)):
                    pdf.set_x(x_start)
                for i, datum in enumerate(row):
                    if not isinstance(datum, str):
                        datum = str(datum)
                    if datum in emphasize_data:
                        pdf.set_text_color(*(emphasize_color[emphasize_data.index(datum)]))
                        pdf.set_font(style=emphasize_style)
                        pdf.multi_cell(
                            col_width[i], line_height, datum, border=0,
                            align=align_data, new_x=XPos.RIGHT, new_y=YPos.TOP,
                            max_line_height=pdf.font_size
                        )
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_font(style=default_style)
                    else:
                        pdf.multi_cell(
                            col_width[i], line_height, datum, border=0,
                            align=align_data, new_x=XPos.RIGHT, new_y=YPos.TOP,
                            max_line_height=pdf.font_size
                        )
                pdf.ln(line_height)
        else:
            for datum in header:
                pdf.multi_cell(
                    col_width, line_height, datum, border=0,
                    align=align_header, new_x=XPos.RIGHT, new_y=YPos.TOP,
                    max_line_height=pdf.font_size
                )
            x_right = pdf.get_x()
            pdf.ln(line_height)
            y2 = pdf.get_y()
            pdf.line(x_left, y1, x_right, y1)
            pdf.line(x_left, y2, x_right, y2)

            for row in data:
                if isinstance(x_start, (int, float)):
                    pdf.set_x(x_start)
                for datum in row:
                    if not isinstance(datum, str):
                        datum = str(datum)
                    if datum in emphasize_data:
                        pdf.set_text_color(*(emphasize_color[emphasize_data.index(datum)]))
                        pdf.set_font(style=emphasize_style)
                        pdf.multi_cell(
                            col_width, line_height, datum, border=0,
                            align=align_data, new_x=XPos.RIGHT, new_y=YPos.TOP,
                            max_line_height=pdf.font_size
                        )
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_font(style=default_style)
                    else:
                        pdf.multi_cell(
                            col_width, line_height, datum, border=0,
                            align=align_data, new_x=XPos.RIGHT, new_y=YPos.TOP,
                            max_line_height=pdf.font_size
                        )
                pdf.ln(line_height)

        y3 = pdf.get_y()
        pdf.line(x_left, y3, x_right, y3)
