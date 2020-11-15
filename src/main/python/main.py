import sys
import contextlib
import os

from shutil import copyfile
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QWidget, QWidgetAction, QSlider, QMainWindow, QDialog, QFormLayout, QLabel, QCheckBox, QComboBox, QDialogButtonBox
from PyQt5.QtCore import Qt, QSettings, QRect, QMetaObject, QCoreApplication
from fbs_runtime.application_context.PyQt5 import ApplicationContext

import pulsectl

pulse = pulsectl.Pulse("t")

class CadmusPulseInterface:
    @staticmethod
    def cli_command(command):
        if not isinstance(command, list):
            command = [command]
        with contextlib.closing(pulsectl.connect_to_cli()) as s:
            for c in command:
                s.write(c + "\n")

    @staticmethod
    def load_modules(mic_name, cadmus_lib_path):
        print(mic_name)
        print(cadmus_lib_path)

        pulse.module_load(
            "module-null-sink",
            "sink_name=mic_denoised_out "
            "sink_properties=\"device.description='Cadmus Microphone Sink'\"",
        )
        pulse.module_load(
            "module-ladspa-sink",
            "sink_name=mic_raw_in sink_master=mic_denoised_out label=noise_suppressor_mono plugin=%s control=%d "
            "sink_properties=\"device.description='Cadmus Raw Microphone Redirect'\""
            % (cadmus_lib_path, CadmusApplication.control_level),
        )

        pulse.module_load(
            "module-loopback",
            "latency_msec=1 source=%s sink=mic_raw_in channels=1" % mic_name,
        )

        pulse.module_load(
            "module-remap-source",
            "master=mic_denoised_out.monitor source_name=denoised "
            "source_properties=\"device.description='Cadmus Denoised Microphone (Use me!)'\"",
        )

        print("Set suppression level to %d" % CadmusApplication.control_level)

    @staticmethod
    def unload_modules():
        CadmusPulseInterface.cli_command(
            [
                "unload-module module-loopback",
                "unload-module module-null-sink",
                "unload-module module-ladspa-sink",
                "unload-module module-remap-source",
            ]
        )


class AudioMenuItem(QAction):
    def __init__(self, text, parent, mic_name):
        super().__init__(text, parent)
        self.mic_name = mic_name
        self.setStatusTip("Use the %s as an input for noise suppression" % text)

class CadmusApplication(QSystemTrayIcon):
    control_level = 50

    def __init__(self, app_context, parent=None):
        QSystemTrayIcon.__init__(self, parent)
        self.app_context = app_context
        self.enabled_icon = QIcon(app_context.get_resource("icon_enabled.png"))
        self.disabled_icon = QIcon(app_context.get_resource("icon_disabled.png"))
        self.cadmus_lib_path = ""

        self.disable_suppression_menu = QAction("Disable Noise Suppression")
        self.enable_suppression_menu = QMenu("Enable Noise Suppression")
        self.settings_menu = QAction("Settings")
        self.level_section = None
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setTickInterval(5)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(CadmusApplication.control_level)
        self.slider.valueChanged.connect(self.slider_valuechange)
        self.exit_menu = QAction("Exit")

        self.gui_setup()
        self.drop_cadmus_binary()

    def get_section_message(self):
        return "Suppression Level: %d" % self.slider.value()

    def slider_valuechange(self):
        CadmusApplication.control_level = self.slider.value()
        self.level_section.setText(self.get_section_message())

    def drop_cadmus_binary(self):
        cadmus_cache_path = os.path.join(os.environ["HOME"], ".cache", "cadmus")
        if not os.path.exists(cadmus_cache_path):
            os.makedirs(cadmus_cache_path)

        self.cadmus_lib_path = os.path.join(cadmus_cache_path, "librnnoise_ladspa.so")

        copyfile(
            self.app_context.get_resource("librnnoise_ladspa.so"), self.cadmus_lib_path
        )

    def gui_setup(self):
        main_menu = QMenu()

        self.disable_suppression_menu.setEnabled(False)
        self.disable_suppression_menu.triggered.connect(self.disable_noise_suppression)

        for src in pulse.source_list():
            mic_menu_item = AudioMenuItem(
                src.description, self.enable_suppression_menu, src.name,
            )
            self.enable_suppression_menu.addAction(mic_menu_item)
            mic_menu_item.triggered.connect(self.enable_noise_suppression)
        self.exit_menu.triggered.connect(self.quit)
        self.settings_menu.triggered.connect(self.open_settings)

        main_menu.addMenu(self.enable_suppression_menu)
        main_menu.addAction(self.disable_suppression_menu)
        main_menu.addAction(self.settings_menu)
        main_menu.addAction(self.exit_menu)

        # Add slider widget
        self.level_section = self.enable_suppression_menu.addSection(self.get_section_message())
        wa = QWidgetAction(self.enable_suppression_menu)
        wa.setDefaultWidget(self.slider)
        self.enable_suppression_menu.addAction(wa)

        self.setIcon(self.disabled_icon)
        self.setContextMenu(main_menu)

    def enable_noise_suppression(self):
        CadmusPulseInterface.load_modules(self.sender().mic_name, self.cadmus_lib_path)
        self.setIcon(self.enabled_icon)
        self.enable_suppression_menu.setEnabled(False)
        self.disable_suppression_menu.setEnabled(True)

    def disable_noise_suppression(self):
        CadmusPulseInterface.unload_modules()
        self.disable_suppression_menu.setEnabled(False)
        self.enable_suppression_menu.setEnabled(True)
        self.setIcon(self.disabled_icon)
    
    def open_settings(self):
        settingswindow.show()

    def quit(self):
        self.disable_noise_suppression()
        self.app_context.app.quit()

class CadmusSettings(QMainWindow):
    def __init__(self,app_context,parent:None):
        QMainWindow.__init__(self, parent)
        self.setWindowTitle("Cadmus Settings")
        self.app_context = app_context
        self.setObjectName("CadmusSettings")
        self.resize(688, 199)
        self.widget = QWidget()
        self.widget.setGeometry(QRect(190, 20, 308, 157))
        self.widget.setObjectName("widget")
        self.setCentralWidget(self.widget)
        self.formLayout = QFormLayout(self.widget)
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout.setObjectName("formLayout")
        self.label = QLabel(self.widget)
        font = QFont()
        font.setPointSize(18)
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.label)
        self.check_LoadLogon = QCheckBox(self.widget)
        font = QFont()
        font.setPointSize(12)
        self.check_LoadLogon.setFont(font)
        self.check_LoadLogon.setObjectName("check_LoadLogon")
        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.check_LoadLogon)
        self.check_EnableOnStartup = QCheckBox(self.widget)
        font = QFont()
        font.setPointSize(12)
        self.check_EnableOnStartup.setFont(font)
        self.check_EnableOnStartup.setObjectName("check_EnableOnStartup")
        self.formLayout.setWidget(2, QFormLayout.LabelRole, self.check_EnableOnStartup)
        self.combo_DefMic = QComboBox(self.widget)
        self.combo_DefMic.setObjectName("combo_DefMic")
        self.formLayout.setWidget(3, QFormLayout.LabelRole, self.combo_DefMic)
        self.buttonBox_SettingsDialog = QDialogButtonBox(self.widget)
        self.buttonBox_SettingsDialog.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox_SettingsDialog.setObjectName("buttonBox_SettingsDialog")
        self.formLayout.setWidget(4, QFormLayout.LabelRole, self.buttonBox_SettingsDialog)

        self.retranslateUi()
        QMetaObject.connectSlotsByName(parent)

    def retranslateUi(self):
        _translate = QCoreApplication.translate
        self.setWindowTitle("Cadmus Settings")
        self.label.setText(_translate("CadmusSettings", "Cadmus Settings"))
        self.check_LoadLogon.setText(_translate("CadmusSettings", "Load Cadmus on logon?"))
        self.check_EnableOnStartup.setText(_translate("CadmusSettings", "Enable noise supression on startup?"))
        self.combo_DefMic.setCurrentText(_translate("CadmusSettings", "Default Microphone for noise supression on startup"))
        self.combo_DefMic.setPlaceholderText(_translate("CadmusSettings", "Default Microphone for noise supression on startup"))

if __name__ == "__main__":
    cadmus_context = ApplicationContext()
    cadmus_context.app.setQuitOnLastWindowClosed(False)
    parent_widget = QWidget()

    icon = CadmusApplication(cadmus_context, parent_widget)
    icon.show()

    settingswindow = CadmusSettings(cadmus_context, parent_widget)

    sys.exit(cadmus_context.app.exec_())
