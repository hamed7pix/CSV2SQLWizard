import sys
import csv
import os
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
                           QFileDialog, QPushButton, QVBoxLayout, QHBoxLayout, QWidget,
                           QLabel, QStatusBar, QMessageBox, QDialog, QLineEdit, QComboBox,
                           QGridLayout, QGroupBox, QTextEdit, QPlainTextEdit)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class SqlViewDialog(QDialog):
    def __init__(self, sql_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SQL Query Viewer")
        self.setGeometry(100, 100, 800, 600)
        self.setup_ui(sql_text)
        
    def setup_ui(self, sql_text):
        layout = QVBoxLayout()
        
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(sql_text)
        self.text_edit.setReadOnly(True)
        font = QFont("Courier New")
        font.setPointSize(10)
        self.text_edit.setFont(font)
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        QMessageBox.information(self, "Copied", "SQL query copied to clipboard!")

class HeaderEditWindow(QDialog):
    def __init__(self, headers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Headers and Data Types")
        self.setMinimumWidth(600)
        self.headers = headers
        self.data_types = ['VARCHAR(255)', 'INT', 'FLOAT', 'DATE', 'TEXT', 'BOOLEAN', 'DECIMAL(10,2)']
        self.column_types = {header: 'VARCHAR(255)' for header in headers}
        self.setup_ui()
        
    def setup_ui(self):
        layout = QGridLayout()
        
        header_group = QGroupBox("Column Headers and Types")
        header_layout = QGridLayout()
        
        header_layout.addWidget(QLabel("Original Header"), 0, 0)
        header_layout.addWidget(QLabel("New Header Name"), 0, 1)
        header_layout.addWidget(QLabel("SQL Data Type"), 0, 2)
        
        self.header_edits = {}
        self.type_combos = {}
        
        for i, header in enumerate(self.headers):
            header_layout.addWidget(QLabel(header), i+1, 0)
            
            header_edit = QLineEdit(header)
            header_layout.addWidget(header_edit, i+1, 1)
            self.header_edits[header] = header_edit
            
            type_combo = QComboBox()
            type_combo.addItems(self.data_types)
            header_layout.addWidget(type_combo, i+1, 2)
            self.type_combos[header] = type_combo
        
        header_group.setLayout(header_layout)
        layout.addWidget(header_group, 0, 0)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout, 1, 0)
        self.setLayout(layout)
    
    def get_edited_headers(self):
        result = {}
        for original, edit in self.header_edits.items():
            result[original] = edit.text()
        return result
    
    def get_column_types(self):
        result = {}
        for original, combo in self.type_combos.items():
            new_header = self.header_edits[original].text()
            result[new_header] = combo.currentText()
        return result

class CSVToSQLConverter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSV2SQLWizard")
        self.setGeometry(100, 100, 800, 600)
        self.csv_data = None
        self.df = None
        self.headers = []
        self.column_types = {}
        self.original_to_new_headers = {}
        self.sql_statements = []
        self.setup_ui()
        
    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        button_layout = QHBoxLayout()
        
        self.load_btn = QPushButton("Load CSV")
        self.load_btn.clicked.connect(self.load_csv)
        button_layout.addWidget(self.load_btn)
        
        self.edit_headers_btn = QPushButton("Edit Headers & Types")
        self.edit_headers_btn.clicked.connect(self.edit_headers)
        self.edit_headers_btn.setEnabled(False)
        button_layout.addWidget(self.edit_headers_btn)
        
        self.generate_sql_btn = QPushButton("Generate SQL")
        self.generate_sql_btn.clicked.connect(self.generate_sql)
        self.generate_sql_btn.setEnabled(False)
        button_layout.addWidget(self.generate_sql_btn)
        
        self.save_sql_btn = QPushButton("Save SQL")
        self.save_sql_btn.clicked.connect(self.save_sql)
        self.save_sql_btn.setEnabled(False)
        button_layout.addWidget(self.save_sql_btn)
        
        self.view_sql_btn = QPushButton("View Full SQL")
        self.view_sql_btn.clicked.connect(self.view_full_sql)
        self.view_sql_btn.setEnabled(False)
        button_layout.addWidget(self.view_sql_btn)
        
        main_layout.addLayout(button_layout)
        
        self.table_info_label = QLabel("No data loaded")
        main_layout.addWidget(self.table_info_label)
        
        self.table_widget = QTableWidget()
        self.table_widget.cellChanged.connect(self.cell_changed)
        main_layout.addWidget(self.table_widget)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.setCentralWidget(central_widget)
    
    def load_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv)")
        if not file_path:
            return
            
        try:
            self.df = pd.read_csv(file_path)
            self.headers = list(self.df.columns)
            self.column_types = {header: 'VARCHAR(255)' for header in self.headers}
            self.original_to_new_headers = {header: header for header in self.headers}
            
            self.display_data()
            
            rows, cols = self.df.shape
            self.table_info_label.setText(f"Table: {os.path.basename(file_path)} | Rows: {rows} | Columns: {cols}")
            
            self.edit_headers_btn.setEnabled(True)
            self.generate_sql_btn.setEnabled(True)
            
            self.status_bar.showMessage(f"Loaded {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load CSV file: {str(e)}")
    
    def display_data(self):
        if self.df is None:
            return
            
        self.table_widget.cellChanged.disconnect(self.cell_changed)
        
        rows, cols = self.df.shape
        self.table_widget.setRowCount(rows)
        self.table_widget.setColumnCount(cols)
        
        display_headers = [self.original_to_new_headers[h] for h in self.headers]
        self.table_widget.setHorizontalHeaderLabels(display_headers)
        
        for i in range(rows):
            for j in range(cols):
                value = str(self.df.iloc[i, j])
                item = QTableWidgetItem(value)
                self.table_widget.setItem(i, j, item)
        
        self.table_widget.resizeColumnsToContents()
        
        self.table_widget.cellChanged.connect(self.cell_changed)
    
    def cell_changed(self, row, col):
        if self.df is not None:
            new_value = self.table_widget.item(row, col).text()
            self.df.iloc[row, col] = new_value
    
    def edit_headers(self):
        if not self.headers:
            return
        
        dialog = HeaderEditWindow(self.headers, self)
        result = dialog.exec_()
        
        if result == QDialog.Accepted:
            self.original_to_new_headers = dialog.get_edited_headers()
            self.column_types = dialog.get_column_types()
            
            display_headers = [self.original_to_new_headers[h] for h in self.headers]
            self.table_widget.setHorizontalHeaderLabels(display_headers)
            
            self.status_bar.showMessage("Headers and data types updated")
    
    def generate_sql(self):
        if self.df is None:
            return
        
        table_name = "table_name"
        
        self.sql_statements = []
        
        create_sql = f"CREATE TABLE {table_name} (\n"
        columns = []
        
        for original_header in self.headers:
            new_header = self.original_to_new_headers[original_header]
            data_type = self.column_types.get(new_header, "VARCHAR(255)")
            columns.append(f"    {new_header} {data_type}")
        
        create_sql += ",\n".join(columns)
        create_sql += "\n);"
        
        self.sql_statements.append(create_sql)
        
        insert_header = f"INSERT INTO {table_name} ({', '.join([self.original_to_new_headers[h] for h in self.headers])}) VALUES"
        insert_values = []
        
        for i in range(len(self.df)):
            values = []
            for j, col in enumerate(self.df.columns):
                val = self.df.iloc[i, j]
                if pd.isna(val):
                    values.append("NULL")
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                else:
                    val_str = str(val)
                    val_str = val_str.replace("'", "''")
                    values.append(f"'{val_str}'" if val else "NULL")
            
            insert_values.append(f"({', '.join(values)})")
        
        batch_size = 50
        for i in range(0, len(insert_values), batch_size):
            batch = insert_values[i:i+batch_size]
            insert_sql = insert_header + "\n" + ",\n".join(batch) + ";"
            
            self.sql_statements.append(insert_sql)
        
        self.save_sql_btn.setEnabled(True)
        self.view_sql_btn.setEnabled(True)
        self.status_bar.showMessage("SQL generated successfully")
        
        self.view_full_sql()
    
    def view_full_sql(self):
        if not self.sql_statements:
            return
            
        full_sql = "\n\n".join(self.sql_statements)
        
        dialog = SqlViewDialog(full_sql, self)
        dialog.exec_()
    
    def save_sql(self):
        if not self.sql_statements:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Save SQL File", "", "SQL Files (*.sql)")
        if not file_path:
            return
            
        try:
            with open(file_path, 'w') as file:
                for sql in self.sql_statements:
                    file.write(sql + "\n\n")
                    
            self.status_bar.showMessage(f"SQL saved to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save SQL file: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CSVToSQLConverter()
    window.show()
    sys.exit(app.exec_())
