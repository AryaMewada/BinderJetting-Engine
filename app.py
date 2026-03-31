import sys
import json
import os
from Slicer import run_slicer
import shutil
import os
import json
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout,
    QLabel, QFileDialog, QListWidget, QProgressBar,
    QMessageBox, QHBoxLayout, QSpinBox, QFormLayout
)

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QSlider

from PyQt5.QtCore import Qt



# =========================
# WORKER THREAD
# =========================F
class SlicerWorker(QThread):

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, object)

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

        self.btn_save = QPushButton("Save Project")
        self.btn_save.clicked.connect(self.save_project)
        btn_layout.addWidget(self.btn_save)

        self.btn_load = QPushButton("Load Project")
        self.btn_load.clicked.connect(self.load_project)
        btn_layout.addWidget(self.btn_load)

        self.btn_export = QPushButton("Export Job")
        self.btn_export.clicked.connect(self.export_job)
        btn_layout.addWidget(self.btn_export)

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
        # BINDER SETTINGS
        # =========================

        # Shell Thickness
        self.shell_thickness = QSpinBox()
        self.shell_thickness.setRange(1, 10)
        self.shell_thickness.setValue(2)
        form.addRow("Shell Thickness (px)", self.shell_thickness)

        # Core Density
        self.core_density = QSpinBox()
        self.core_density.setRange(10, 100)
        self.core_density.setValue(60)
        form.addRow("Core Density (%)", self.core_density)

        # Gamma
        self.gamma = QSpinBox()
        self.gamma.setRange(1, 50)
        self.gamma.setValue(25)  # = 2.5
        form.addRow("Gamma (x0.1)", self.gamma)

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

        # =========================
        # LIVE PREVIEW
        # =========================
        self.preview_label = QLabel()
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setStyleSheet("background-color: black;")
        self.layout.addWidget(self.preview_label)

        # =========================
        # SLIDER
        # =========================
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.valueChanged.connect(self.on_slider_change)

        self.layout.addWidget(self.slider)

        self.layer_images = []
        
        

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
                self.file_list.addItem(os.path.basename(f))

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
    # SaveProject
    # =========================
    def save_project(self):

        if not self.files:
            QMessageBox.warning(self, "Warning", "No project to save")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "Project Files (*.json)"
        )

        if not path:
            return

        data = {
            "files": self.files,
            "settings": {
                "bed_x": self.bed_x.value(),
                "bed_y": self.bed_y.value(),
                "layer_height": self.layer_height.value() / 10.0,
                "dpi": self.dpi.value(),

                # NEW
                "shell_thickness": self.shell_thickness.value(),
                "core_density": self.core_density.value(),
                "gamma": self.gamma.value()
            }
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=4)

        QMessageBox.information(self, "Saved", "Project saved successfully")

    # =========================
    # LoadProject
    # ========================= 

    def load_project(self):

        path, _ = QFileDialog.getOpenFileName(
            self, "Load Project", "", "Project Files (*.json)"
        )

        if not path:
            return

        with open(path, "r") as f:
            data = json.load(f)

        # clear existing
        self.files = []
        self.file_list.clear()

        # load files
        for fpath in data.get("files", []):

            if os.path.exists(fpath):
                self.files.append(fpath)
                self.file_list.addItem(os.path.basename(fpath))
            else:
                print("Missing file:", fpath)

        # load settings
        settings = data.get("settings", {})

        self.bed_x.setValue(settings.get("bed_x", 500))
        self.bed_y.setValue(settings.get("bed_y", 500))
        self.layer_height.setValue(int(settings.get("layer_height", 0.2) * 10))
        self.dpi.setValue(settings.get("dpi", 300))
        self.shell_thickness.setValue(settings.get("shell_thickness", 2))
        self.core_density.setValue(settings.get("core_density", 60))
        self.gamma.setValue(settings.get("gamma", 25))

        QMessageBox.information(self, "Loaded", "Project loaded successfully")

    # =========================
    # Export
    # =========================       

    def export_job(self):

        if not hasattr(self, "last_result"):
            QMessageBox.warning(self, "Warning", "No job to export")
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Export Folder")

        if not folder:
            return

        # =========================
        # CREATE JOB FOLDER
        # =========================
        job_name = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        job_path = os.path.join(folder, job_name)

        os.makedirs(job_path, exist_ok=True)

        # =========================
        # COPY TIFF FILES
        # =========================
        src_tiff = "job_001/tiff"   # your slicer output folder

        if not os.path.exists(src_tiff):
            QMessageBox.warning(self, "Error", "TIFF folder not found. Run slicing first.")
            return

        dst_tiff = os.path.join(job_path, "tiff")

        shutil.copytree(src_tiff, dst_tiff)

        # =========================
        # SAVE CONFIG
        # =========================
        config = {
            "bed_x": self.bed_x.value(),
            "bed_y": self.bed_y.value(),
            "layer_height": self.layer_height.value() / 10.0,
            "dpi": self.dpi.value()
        }

        with open(os.path.join(job_path, "config.json"), "w") as f:
            json.dump(config, f, indent=4)

        # =========================
        # SAVE METADATA
        # =========================
        metadata = {
            "files": self.files,
            "layers": self.last_result["layers"],
            "time_hr": self.last_result["time_hr"],
            "cost": self.last_result["cost"]
        }

        with open(os.path.join(job_path, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=4)

        QMessageBox.information(self, "Export", "Job exported successfully")

    # =========================
    # GENERATE
    # =========================
    def generate(self):

        self.layer_images = []
        self.slider.setValue(0)
        self.slider.setMaximum(0)

        if self.bed_x.value() < 100 or self.bed_y.value() < 100:
            QMessageBox.warning(self, "Warning", "Bed size too small")
            return

        if self.dpi.value() < 100:
            QMessageBox.warning(self, "Warning", "DPI too low")
            return
        
        errors, warnings = self.validate_job()

        if errors:
            QMessageBox.critical(self, "Validation Error", "\n".join(errors))
            return

        if warnings:
            reply = QMessageBox.warning(
                self,
                "Warning",
                "\n".join(warnings) + "\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.No:
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
            "dpi": self.dpi.value(),

            # NEW
            "shell_thickness": self.shell_thickness.value(),
            "core_density": self.core_density.value() / 100.0,
            "gamma": self.gamma.value() / 10.0
        }

        self.worker = SlicerWorker(self.files, settings)

        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)

        self.worker.start()

    # =========================
    # PROGRESS UPDATE
    # =========================
    def update_progress(self, value, image):

        self.progress.setValue(value)

        if image is not None:

            # store image for slider use
            self.layer_images.append(image)
            
            from PyQt5.QtGui import QImage, QPixmap

            h, w = image.shape

            qimg = QImage(
                image.data,
                w,
                h,
                w,
                QImage.Format_Grayscale8
            )

            pixmap = QPixmap.fromImage(qimg)

            # 🔥 SCALE IMAGE TO FIT UI
            pixmap = pixmap.scaled(
                self.preview_label.width(),
                self.preview_label.height(),
                aspectRatioMode=1
            )

            self.preview_label.setPixmap(pixmap)

            self.slider.blockSignals(True)
            self.slider.setMaximum(len(self.layer_images) - 1)
            self.slider.blockSignals(False)

    # =========================
    # FINISHED
    # =========================
    def on_finished(self, result):

        self.last_result = result
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

    def on_slider_change(self, index):

        if not self.layer_images:
            return

        index = max(0, min(index, len(self.layer_images) - 1))

        if index < 0 or index >= len(self.layer_images):
            return

        image = self.layer_images[index]

        from PyQt5.QtGui import QImage, QPixmap

        h, w = image.shape

        qimg = QImage(
            image.data,
            w,
            h,
            w,
            QImage.Format_Grayscale8
        )

        pixmap = QPixmap.fromImage(qimg)

        pixmap = pixmap.scaled(
            self.preview_label.width(),
            self.preview_label.height(),
            aspectRatioMode=1
        )

        self.preview_label.setPixmap(pixmap)


    def validate_job(self):

        errors = []
        warnings = []

        # =========================
        # BED SIZE VALIDATION
        # =========================
        if self.bed_x.value() < 100 or self.bed_y.value() < 100:
            errors.append("Bed size too small")

        # =========================
        # DPI VALIDATION
        # =========================
        dpi = self.dpi.value()

        if dpi < 100:
            errors.append("DPI too low (<100)")

        if dpi > 1200:
            warnings.append("DPI very high (slow processing)")

        # =========================
        # FILE CHECK
        # =========================
        if not self.files:
            errors.append("No STL files selected")

        # =========================
        # RESULT
        # =========================
        return errors, warnings


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SlicerApp()
    window.show()
    sys.exit(app.exec_())