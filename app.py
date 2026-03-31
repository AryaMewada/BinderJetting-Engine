import sys
from Slicer import run_slicer

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout,
    QLabel, QFileDialog, QListWidget, QProgressBar,
    QMessageBox, QHBoxLayout, QSpinBox, QFormLayout
)

from PyQt5.QtCore import QThread, pyqtSignal


# =========================
# WORKER THREAD
# =========================
class SlicerWorker(QThread):

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, files, settings):
        super().__init__()
        self.files = files
        self.settings = settings

    def run(self):
        try:
            result = run_slicer(
                self.files,
                progress_callback=self.progress.emit,
                settings=self.settings
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# =========================
# MAIN APP
# =========================
class SlicerApp(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Binder Jetting Slicer")
        self.setGeometry(200, 200, 450, 650)

        self.layout = QVBoxLayout()

        # =========================
        # FILE SECTION
        # =========================
        self.label = QLabel("Select STL Files")
        self.layout.addWidget(self.label)

        self.file_list = QListWidget()
        self.layout.addWidget(self.file_list)

        # buttons row
        btn_layout = QHBoxLayout()

        self.btn_add = QPushButton("Add STL")
        self.btn_add.clicked.connect(self.add_files)
        btn_layout.addWidget(self.btn_add)

        self.btn_new = QPushButton("New Project")
        self.btn_new.clicked.connect(self.new_project)
        btn_layout.addWidget(self.btn_new)

        self.layout.addLayout(btn_layout)

        # =========================
        # SETTINGS PANEL
        # =========================
        self.settings_label = QLabel("Settings")
        self.layout.addWidget(self.settings_label)

        form = QFormLayout()

        # Bed X
        self.bed_x = QSpinBox()
        self.bed_x.setRange(50, 2000)
        self.bed_x.setValue(500)
        form.addRow("Bed X (mm)", self.bed_x)

        # Bed Y
        self.bed_y = QSpinBox()
        self.bed_y.setRange(50, 2000)
        self.bed_y.setValue(500)
        form.addRow("Bed Y (mm)", self.bed_y)

        # Layer Height
        self.layer_height = QSpinBox()
        self.layer_height.setRange(1, 50)
        self.layer_height.setValue(2)  # = 0.2 mm
        form.addRow("Layer Height (x0.1 mm)", self.layer_height)

        # DPI
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 1200)
        self.dpi.setValue(300)
        form.addRow("DPI", self.dpi)

        self.layout.addLayout(form)

        # =========================
        # GENERATE
        # =========================
        self.btn_generate = QPushButton("Generate")
        self.btn_generate.clicked.connect(self.generate)
        self.layout.addWidget(self.btn_generate)

        # progress
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.layout.addWidget(self.progress)

        # output
        self.output_label = QLabel("Output:")
        self.layout.addWidget(self.output_label)

        self.setLayout(self.layout)

        self.files = []

    # =========================
    # ADD FILES
    # =========================
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select STL Files", "", "STL Files (*.stl)"
        )

        for f in files:
            if f not in self.files:
                self.files.append(f)
                self.file_list.addItem(f)

    # =========================
    # NEW PROJECT
    # =========================
    def new_project(self):

        reply = QMessageBox.question(
            self,
            "New Project",
            "Are you sure you want to reset?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.files = []
            self.file_list.clear()
            self.progress.setValue(0)
            self.output_label.setText("Output:")

    # =========================
    # GENERATE
    # =========================
    def generate(self):

        if self.bed_x.value() < 100 or self.bed_y.value() < 100:
            QMessageBox.warning(self, "Warning", "Bed size too small")
            return

        if self.dpi.value() < 100:
            QMessageBox.warning(self, "Warning", "DPI too low")
            return

        if not self.files:
            self.output_label.setText("No files selected")
            return

        self.output_label.setText("Processing...")
        self.progress.setValue(0)

        # disable buttons
        self.btn_generate.setEnabled(False)
        self.btn_add.setEnabled(False)
        self.btn_new.setEnabled(False)

        # collect settings
        settings = {
            "bed_x": self.bed_x.value(),
            "bed_y": self.bed_y.value(),
            "layer_height": self.layer_height.value() / 10.0,
            "dpi": self.dpi.value()
        }

        self.worker = SlicerWorker(self.files, settings)

        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)

        self.worker.start()

    # =========================
    # PROGRESS UPDATE
    # =========================
    def update_progress(self, value):
        self.progress.setValue(value)

    # =========================
    # FINISHED
    # =========================
    def on_finished(self, result):

        self.progress.setValue(100)

        # re-enable buttons
        self.btn_generate.setEnabled(True)
        self.btn_add.setEnabled(True)
        self.btn_new.setEnabled(True)

        self.output_label.setText(
            f"Done!\n"
            f"Layers: {result['layers']}\n"
            f"Time: {result['time_hr']:.2f} hr\n"
            f"Cost: ₹{result['cost']:.2f}"
        )

    # =========================
    # ERROR HANDLING
    # =========================
    def on_error(self, message):

        self.progress.setValue(0)

        # re-enable buttons
        self.btn_generate.setEnabled(True)
        self.btn_add.setEnabled(True)
        self.btn_new.setEnabled(True)

        QMessageBox.critical(self, "Error", message)

        self.output_label.setText(f"Error: {message}")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SlicerApp()
    window.show()
    sys.exit(app.exec_())