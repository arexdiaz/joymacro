from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QSlider, QMenu, QAction, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QRect, QThread
from functools import partial
import time
import logging


logger = logging.getLogger("main")

class ContainerManager:
    def __init__(self):
        self.containers = {}

    def addContainer(self, label, container):
        self.containers[label] = container

    def getContainer(self, label):
        return self.containers.get(label)

    def poulateAllContainers(self):
        for label, container in self.containers.items():
            container.populateContainer()

    def toggleContainers(self):
        for label, container_obj in self.containers.items():
            container_obj.container.setVisible(False)

        self.getContainer("Primary").container.setVisible(True)

class ContainerProp:
    def __init__(self, height, width, style_guide):
        self.label = None
        self.widget = None
        self.widgets = {}
        self.style_guide = style_guide

        self.screen_height = height
        self.screen_width = width

        self.container = None
        self.label = None


    def createContainer(self, OW, x, y, w, h, color, visible=True, label=None):
        self.container = QWidget(OW)
        self.container.setGeometry(x, y, w, h)
        self.container.setStyleSheet(f"background-color: {color};")
        self.container.setVisible(visible)
        if label:
            # self.container_objs[label] = self.container
            self.label = label

        inner_menu = QWidget(self.container)
        inner_menu.setGeometry(0, 0, self.container.width(), self.container.height())
        inner_menu.setStyleSheet("background-color: transparent;")
        self.layout = QVBoxLayout(inner_menu)

    def createButton(self, label, callback, bg_color="0,0,0", opacity=0, pos="top"):
        button = QPushButton(label)
        button.id = label.lower().replace(" ", "_")
        button.setMinimumHeight(self.style_guide.elements_height)
        button.clicked.connect(callback)
        button.pos = pos

        button.setStyleSheet(self.style_guide.buttonStyle(bg_color, self.style_guide.button_font_size, opacity))
        self.widgets[button.id] = button
    
    def createSubmenu(self, container, label, bg_color="0,0,0", opacity=0, pos="top"):
        button = QPushButton(label)
        button.setMinimumHeight(self.style_guide.elements_height)
        button.clicked.connect(partial(self.switchContainer, container.container))
        button.pos = pos
        button.id = label.lower().replace(" ", "_")

        button.setStyleSheet(self.style_guide.buttonStyle(bg_color, self.style_guide.button_font_size, opacity))
        self.widgets[button.id] = button

    def switchContainer(self, u2container):
        self.container.setVisible(not self.container.isVisible())
        u2container.setVisible(not u2container.isVisible())

    def createSlider(self, callback, label, value=0, min=0, max=100, pos="top"):
        slider = QSlider(Qt.Horizontal)
        slider.id = label.lower().replace(" ", "_")
        slider.pos = pos
        slider.setMinimum(min)
        slider.setMaximum(max)
        slider.setValue(value)
        slider.setMinimumHeight(self.style_guide.elements_height)
        slider.valueChanged.connect(callback)

        slider.setStyleSheet(f"""
            QSlider {{
                background-color: rgba({self.style_guide.gray}, {self.style_guide.opacity});
                height: 20px;
                border-bottom: 2px solid gray;
                border-radius: 0px;
            }}

            QSlider::groove:horizontal {{
                border: 1px solid #ffffff;
                height: 8px;
                background: #ffffff;
                border-radius: 0px;
            }}

            QSlider::handle:horizontal {{
                background: #2196F3;
                border: 4px solid #2196F3;
                width: 21px;
                border-radius: 10px;
                margin-top: -{(self.style_guide.elements_height / 2) -10}px;
                margin-bottom: -{(self.style_guide.elements_height / 2) -10}px;
            }}

            QSlider::handle:horizontal:hover {{
                background: #64b5f6;
            }}

            QSlider::handle:horizontal:pressed {{
                background: #1976d2;
            }}

            QSlider::add-page:horizontal {{
                background: #b3e5fc;
            }}

            QSlider::sub-page:horizontal {{
                background: #0C7CD5;
            }}
        """)

        self.widgets[slider.id] = slider
    
    def removeWidget(self, id):
        logger.debug(f"Removing widget: {id}")
        self.layout.removeWidget(self.widgets[id])
        self.layout.update()

    def getWidget(self, id):
        return self.layout.itemAt(self.layout.indexOf(self.widgets[id]))

    def resetLayout(self):
        for id, widget in self.widgets.items():
            if id != "back":
                self.layout.removeWidget(widget)
        self.widgets = {}
        self.layout.update()

    def populateContainer(self):
        empty_height = self.screen_height - (self.style_guide.elements_height * len(self.widgets))
        empty_widget = QWidget(self.container)
        empty_widget.setFixedSize(self.container.width(), empty_height)
        empty_widget.pos = "top"
        empty_widget.id = "empty"
        self.widgets[empty_widget.id] = empty_widget
        
        for id, widget in self.widgets.items():
            if widget.pos == "top":
                self.layout.addWidget(widget)
        for id, widget in self.widgets.items():
            if widget.pos == "bottom":
                self.layout.addWidget(widget)
        self.layout.update()
