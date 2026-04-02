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
    ,QInputDialog , QSlider , QGroupBox , QComboBox
)

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtCore import Qt
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

        self.part_settings = {}

        self.loading_part = False
        

        self.setWindowTitle("Binder Jetting Slicer Engine")
        self.setGeometry(200, 200, 450, 650)

        # =========================
        # CREATE ALL WIDGETS FIRST
        # =========================

        # Buttons
        self.btn_add = QPushButton("Add STL")
        self.btn_new = QPushButton("New Project")
        self.btn_save = QPushButton("Save Project")
        self.btn_load = QPushButton("Load Project")
        self.btn_export = QPushButton("Export Job")
        self.btn_save_printer = QPushButton("Save Printer")
        self.btn_load_printer = QPushButton("Load Printer")
        self.btn_save_job = QPushButton("Save Job")
        self.btn_load_job = QPushButton("Load Job")

        self.btn_generate = QPushButton("Generate")

        # File list
        self.file_list = QListWidget()

        # Progress + output
        self.progress = QProgressBar()
        self.output_label = QLabel("Output:")

        # Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self.on_slider_change)

        # =========================
        # SETTINGS FORM
        # =========================
        form = QFormLayout()

        self.bed_x = QSpinBox()
        self.bed_x.setValue(500)

        self.bed_y = QSpinBox()
        self.bed_y.setValue(500)

        self.layer_height = QSpinBox()
        self.layer_height.setValue(2)

        self.dpi = QSpinBox()
        self.dpi.setValue(300)

        self.shell_thickness = QSpinBox()
        self.shell_thickness.setValue(2)

        self.shell_layers = QSpinBox()
        self.shell_layers.setValue(2)

        self.core_density = QSpinBox()
        self.core_density.setValue(60)

        self.gamma = QSpinBox()
        self.gamma.setValue(25)

        self.infill_type = QComboBox()
        self.infill_type.addItems(["Grid", "Random"])

        self.print_mode = QComboBox()
        self.print_mode.addItems(["Solid", "Hollow"])
        self.print_mode.currentTextChanged.connect(self.toggle_density_visibility)

        self.hollow_density = QSpinBox()
        self.hollow_density.setValue(50)

        self.infill_size = QSpinBox()
        self.infill_size.setValue(10)

        # Bed
        self.bed_x.setRange(50, 2000)
        self.bed_y.setRange(50, 2000)

        # Layer height (x0.1 mm)
        self.layer_height.setRange(1, 50)

        # DPI
        self.dpi.setRange(72, 1200)

        # Shell
        self.shell_thickness.setRange(1, 20)
        self.shell_layers.setRange(1, 10)

        # Core density
        self.core_density.setRange(1, 100)

        # Gamma
        self.gamma.setRange(1, 50)

        # Hollow density
        self.hollow_density.setRange(1, 100)

        # Infill size
        self.infill_size.setRange(1, 50)

        # ADD TO FORM
        form.addRow("Bed X", self.bed_x)
        form.addRow("Bed Y", self.bed_y)
        form.addRow("Layer Height", self.layer_height)
        form.addRow("DPI", self.dpi)
        form.addRow("Shell Thickness", self.shell_thickness)
        form.addRow("Shell Layers", self.shell_layers)
        form.addRow("Core Density", self.core_density)
        form.addRow("Gamma", self.gamma)
        form.addRow("Print Mode", self.print_mode)
        form.addRow("Infill Type", self.infill_type)
        form.addRow("Hollow Density", self.hollow_density)
        form.addRow("Infill Size", self.infill_size)

        self.btn_add.clicked.connect(self.add_files)
        self.btn_new.clicked.connect(self.new_project)
        self.btn_save.clicked.connect(self.save_project)
        self.btn_load.clicked.connect(self.load_project)
        self.btn_export.clicked.connect(self.export_job)
        self.btn_generate.clicked.connect(self.generate)
        self.btn_save_printer.clicked.connect(self.save_printer_profile)
        self.btn_load_printer.clicked.connect(self.load_printer_profile)
        self.btn_save_job.clicked.connect(self.save_job_profile)
        self.btn_load_job.clicked.connect(self.load_job_profile)

        self.file_list.currentItemChanged.connect(self.on_part_changed)

        self.print_mode.currentTextChanged.connect(self.save_part_settings)
        self.hollow_density.valueChanged.connect(self.save_part_settings)
        self.shell_thickness.valueChanged.connect(self.save_part_settings)
        self.shell_layers.valueChanged.connect(self.save_part_settings)
        self.core_density.valueChanged.connect(self.save_part_settings)
        self.gamma.valueChanged.connect(self.save_part_settings)
        self.infill_type.currentTextChanged.connect(self.save_part_settings)
        self.infill_size.valueChanged.connect(self.save_part_settings)

       

        # =========================
        # MAIN LAYOUT STRUCTURE
        # =========================

        main_layout = QVBoxLayout()
        title = QLabel("Addon Binder Jetting Engine")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: white;
        """)

        main_layout.addWidget(title)

        # =========================
        # TOP TOOLBAR
        # =========================
        toolbar = QHBoxLayout()

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_new)
        toolbar.addWidget(self.btn_save)
        toolbar.addWidget(self.btn_load)
        toolbar.addWidget(self.btn_export)
        toolbar.addWidget(self.btn_save_printer)
        toolbar.addWidget(self.btn_load_printer)
        toolbar.addWidget(self.btn_save_job)
        toolbar.addWidget(self.btn_load_job)

        main_layout.addLayout(toolbar)

        toolbar.setSpacing(10)
        toolbar.setContentsMargins(5, 5, 5, 5)

        # =========================
        # CENTER (PREVIEW + PANEL)
        # =========================
        content_layout = QHBoxLayout()

        # -------- LEFT (PREVIEW) --------
        left_layout = QVBoxLayout()

        self.preview_label = QLabel()
        self.overlay_label = QLabel(self.preview_label)
        self.overlay_label.setStyleSheet("""
            background-color: rgba(0, 0, 0, 150);
            color: white;
            padding: 8px;
            border-radius: 5px;
        """)
        self.overlay_label.move(10, 10)
        self.overlay_label.hide()
        self.preview_label.setMinimumSize(800, 600)
        self.preview_label.setStyleSheet("""
            background-color: #0d1117;
            border: 1px solid #30363d;
        """)

        left_layout.addWidget(self.preview_label)
        left_layout.addWidget(self.slider)

        content_layout.addLayout(left_layout, 3)

        # -------- RIGHT PANEL --------
        right_layout = QVBoxLayout()

        # File list
        right_layout.addWidget(QLabel("Select STL Files"))
        right_layout.addWidget(self.file_list)

        # Settings
        # =========================
        # STATIC SETTINGS
        # =========================
        static_box = QGroupBox("Static Settings")
        static_form = QFormLayout()

        static_form.addRow("Bed X", self.bed_x)
        static_form.addRow("Bed Y", self.bed_y)
        static_form.addRow("Layer Height", self.layer_height)
        static_form.addRow("DPI", self.dpi)

        static_box.setLayout(static_form)

        # =========================
        # DYNAMIC SETTINGS
        # =========================
        dynamic_box = QGroupBox("Dynamic Settings")
        dynamic_form = QFormLayout()

        dynamic_form.addRow("Shell Thickness", self.shell_thickness)
        dynamic_form.addRow("Shell Layers", self.shell_layers)
        dynamic_form.addRow("Core Density", self.core_density)
        dynamic_form.addRow("Gamma", self.gamma)

        dynamic_form.addRow("Print Mode", self.print_mode)
        dynamic_form.addRow("Infill Type", self.infill_type)
        dynamic_form.addRow("Hollow Density", self.hollow_density)
        dynamic_form.addRow("Infill Size", self.infill_size)

        dynamic_box.setLayout(dynamic_form)

        # ADD TO UI
        right_layout.addWidget(static_box)
        right_layout.addWidget(dynamic_box)

        # Generate button
        self.btn_generate.setMinimumHeight(60)
        right_layout.addWidget(self.btn_generate)
        self.btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #1f6feb;
                color: white;
                font-size: 18px;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #388bfd;
            }
        """)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setFixedWidth(300)

        content_layout.addWidget(right_widget)

        main_layout.addLayout(content_layout)

        # =========================
        # BOTTOM (SLIDER + STATUS)
        # =========================
        bottom_layout = QVBoxLayout()

        bottom_layout.addWidget(self.progress)

        bottom_layout.addWidget(self.output_label)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #30363d;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #1f6feb;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
        """)

        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

        self.files = []
    
        self.toggle_density_visibility(self.print_mode.currentText())

    def toggle_density_visibility(self, mode):

        is_hollow = (mode == "Hollow")

        # Hollow density
        self.hollow_density.setVisible(is_hollow)

        # Infill controls
        self.infill_type.setEnabled(is_hollow)
        self.infill_size.setEnabled(is_hollow)

    #---------
    #On Part Selected
    #---------
    def on_part_changed(self, current, previous):

        # ✅ SAVE PREVIOUS PART
        if previous:
            name = previous.text()
            self.part_settings[name] = {
                "mode": self.print_mode.currentText(),
                "density": self.hollow_density.value(),

                "shell_thickness": self.shell_thickness.value(),
                "shell_layers": self.shell_layers.value(),
                "core_density": self.core_density.value(),
                "gamma": self.gamma.value(),

                "infill": self.infill_type.currentText(),
                "infill_size": self.infill_size.value()
            }

        if not current:
            return

        name = current.text()

        # 🚨 BLOCK SIGNALS
        self.loading_part = True

        data = self.part_settings.get(name, {})

        self.print_mode.setCurrentText(data.get("mode", "Solid"))
        self.hollow_density.setValue(data.get("density", 50))

        self.shell_thickness.setValue(data.get("shell_thickness", 2))
        self.shell_layers.setValue(data.get("shell_layers", 2))
        self.core_density.setValue(data.get("core_density", 60))
        self.gamma.setValue(data.get("gamma", 25))

        self.infill_type.setCurrentText(data.get("infill", "Grid"))
        self.infill_size.setValue(data.get("infill_size", 10))

        self.toggle_density_visibility(data.get("mode", "Solid"))

        self.loading_part = False

    #---------
    #On Save Part Setting
    #---------
    def save_part_settings(self):

        if self.loading_part:
            return
    
        item = self.file_list.currentItem()
        if not item:
            return

        name = item.text()

        self.part_settings[name] = {
            "mode": self.print_mode.currentText(),
            "density": self.hollow_density.value(),

            "shell_thickness": self.shell_thickness.value(),
            "shell_layers": self.shell_layers.value(),
            "core_density": self.core_density.value(),
            "gamma": self.gamma.value(),

            "infill": self.infill_type.currentText(),
            "infill_size": self.infill_size.value()
        }

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
                "gamma": self.gamma.value(),
                "hollow_density": self.hollow_density.value() / 100.0,
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
    # SAVE Printer Profile
    # =========================
    def save_printer_profile(self):

        name, ok = QInputDialog.getText(self, "Printer Name", "Enter profile name:")

        if not ok or not name:
            return

        os.makedirs("profiles/printers", exist_ok=True)

        data = {
            "name": name,
            "bed_x": self.bed_x.value(),
            "bed_y": self.bed_y.value(),
            "dpi": self.dpi.value(),
            "layer_height": self.layer_height.value()
        }

        path = f"profiles/printers/{name}.json"

        with open(path, "w") as f:
            json.dump(data, f, indent=4)

        QMessageBox.information(self, "Saved", "Printer profile saved")

    # =========================
    # Load Printer Profile
    # =========================

    def load_printer_profile(self):

        folder = "profiles/printers"
        if not os.path.exists(folder):
            return

        files = os.listdir(folder)

        item, ok = QInputDialog.getItem(self, "Load Printer", "Select:", files, 0, False)

        if not ok:
            return

        with open(os.path.join(folder, item)) as f:
            data = json.load(f)

        self.bed_x.setValue(data["bed_x"])
        self.bed_y.setValue(data["bed_y"])
        self.dpi.setValue(data["dpi"])
        self.layer_height.setValue(data["layer_height"])


    # =========================
    # Save Job Profile
    # =========================
    def save_job_profile(self):

        name, ok = QInputDialog.getText(self, "Job Profile", "Enter name:")

        if not ok or not name:
            return

        os.makedirs("profiles/jobs", exist_ok=True)

        data = {
            "name": name,
            "shell_thickness": self.shell_thickness.value(),
            "core_density": self.core_density.value(),
            "gamma": self.gamma.value(),

            "print_mode": self.print_mode.currentText(),
            "hollow_density": self.hollow_density.value() / 100.0,

            # ✅ NEW (IMPORTANT)
            "part_settings": self.part_settings
        }

        path = f"profiles/jobs/{name}.json"

        with open(path, "w") as f:
            json.dump(data, f, indent=4)

        QMessageBox.information(self, "Saved", "Job profile saved")

    # =========================
    # Load Job Profile
    # =========================
    def load_job_profile(self):

        folder = "profiles/jobs"
        if not os.path.exists(folder):
            return

        files = os.listdir(folder)

        item, ok = QInputDialog.getItem(
            self, "Load Job Profile", "Select:", files, 0, False
        )

        if not ok:
            return

        with open(os.path.join(folder, item)) as f:
            data = json.load(f)

        # =========================
        # LOAD GLOBAL SETTINGS
        # =========================
        self.shell_thickness.setValue(data.get("shell_thickness", 2))
        self.core_density.setValue(data.get("core_density", 60))
        self.gamma.setValue(data.get("gamma", 25))

        self.print_mode.setCurrentText(data.get("print_mode", "Solid"))

        self.hollow_density.setValue(
            int(data.get("hollow_density", 0.5) * 100)
        )

        # =========================
        # LOAD PER-PART SETTINGS
        # =========================
        self.part_settings = data.get("part_settings", {})

        # =========================
        # REFRESH UI FOR CURRENT PART
        # =========================
        current_item = self.file_list.currentItem()

        if current_item:
            self.on_part_selected(current_item)

        # ensure correct visibility
        self.toggle_density_visibility(self.print_mode.currentText())
        
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
            "shell_layers": self.shell_layers.value(),
            "core_density": self.core_density.value() / 100.0,
            "gamma": self.gamma.value() / 10.0,
            "print_mode": self.print_mode.currentText(),
            "part_settings": self.part_settings,

            "infill_type": self.infill_type.currentText(),
            "infill_size": self.infill_size.value(),
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
                aspectRatioMode=Qt.KeepAspectRatio
            )
            self.preview_label.setAlignment(Qt.AlignCenter)  # ✅ ADD THIS
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

        # self.output_label.setText(
        #     f"Done!\n"
        #     f"Layers: {result['layers']}\n"
        #     f"Time: {result['time_hr']:.2f} hr\n"
        #     f"Binder: {result['binder_ml']:.2f} ml\n"
        #     f"Powder: {result['powder_l']:.2f} L\n"
        #     f"Cost: ₹{result['cost']:.2f}"
        # )

        overlay_text = (
            f"Layers: {result['layers']}\n"
            f"Time: {result['time_hr']:.2f} hr\n"
            f"Binder: {result['binder_ml']:.2f} ml\n"
            f"Powder: {result['powder_l']:.2f} L\n"
            f"Cost: ₹{result['cost']:.2f}"
        )

        self.overlay_label.setText(overlay_text)
        self.overlay_label.adjustSize()
        self.overlay_label.show()

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
            aspectRatioMode=Qt.KeepAspectRatio
        )

        self.preview_label.setAlignment(Qt.AlignCenter)  # ✅ ADD THIS
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