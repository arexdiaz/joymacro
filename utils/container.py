from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSlider, QVBoxLayout, QLabel
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt
from functools import partial
import time
import logging
import psutil


logger = logging.getLogger("main")

def sanitizeInput(string):
    return string.lower().replace(" ", "_")

class ContainerManager:
    def __init__(self):
        self.containers = {}

    def addContainer(self, container):
        self.containers[container.id] = container
        return self.containers[container.id]

    def getContainer(self, id):
        return self.containers.get(sanitizeInput(id))

    def poulateAllContainers(self):
        for container in self.containers.values():
            container.populateContainer()

    def toggleContainers(self, items=None):
        items = self.containers.values() if not items else items
        for container in items:
            if container.childs:
                self.toggleContainers(container.childs.values())
            container.container.setVisible(False)

        self.getContainer("primary_container").container.setVisible(True)

    def deleteContainer(self, label):
        self.containers.pop(label).container.deleteLater()

    def _getCPUStatus(self):
        def recursive(values):
            for container in values:
                if container.childs:
                    recursive(container.childs.values())
                container.getWidget("cpu_stats").widget().setText(" ".join(cpu_status))

        cpu_usage = psutil.cpu_percent(percpu=True)
        cpu_status = []
        for i, usage in enumerate(cpu_usage):
            cpu_status.append(f"CPU{i}: {usage}%")
        recursive(self.containers.values())

class ContainerProp:
    def __init__(self, height, width, gs, label=None, id=None):
        self.label = label

        if id:
            self.id = id
        else:
            self.id = sanitizeInput(self.label) if self.label else None

        self.widgets = {}
        self.childs = {}
        self.gs = gs

        self.screen_height = height
        self.screen_width = width

        self.container = None
        self.parent = None

    def createContainer(self, OW, x, y, w, h, color, visible=True):
        self.OW = OW
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.container = QWidget(self.OW)
        self.container.setGeometry(x, y, w, h)
        self.container.setStyleSheet(f"background-color: {color};")
        self.container.setVisible(visible)

        inner_menu = QWidget(self.container)
        inner_menu.setGeometry(0, 0, self.container.width(), self.container.height())
        inner_menu.setStyleSheet("background-color: transparent;")
        self.layout = QVBoxLayout(inner_menu)
        self.createLabel(" ", "cpu_stats", 12, pos="bottom")


    def createLabel(self, text, id, font_size=21, bg_color="0,0,0", opacity=0, pos="top", solid=False):
        style = f"background-color: rgba({bg_color}, {opacity}); color: white; font-size: {font_size}px;"
        label = QLabel(text)
        label.setObjectName(sanitizeInput(id))
        label.setStyleSheet(style if not solid else f"{style} border-top: 2px solid gray;")
        label.pos = pos
        self.widgets[label.objectName()] = label
        return label

    def createButton(self, label, callback, bg_color="0,0,0", opacity=0, font_size=None, pos="top", id=None):
        button = QPushButton(label)
        button.setObjectName(sanitizeInput(label) if not id else id)
        button.setMinimumHeight(self.gs.elements_height)
        button.clicked.connect(callback)
        button.pos = pos
        button.parent_label = self.label

        fs = font_size if font_size else self.gs.button_font_size

        button.setStyleSheet(self.gs.buttonStyle(bg_color, fs, opacity))
        self.widgets[button.objectName()] = button
        return button

    def createChildContainer(self, label, pos="top", id=None, callback=None):
        def _switchContainer(first_container, second_container):
            first_container.container.setVisible(False)
            second_container.container.setVisible(True)

        child = ContainerProp(
            self.container.height(),
            self.container.width(),
            self.gs,
            label=label,
            id=id
        )

        child.createContainer(
            self.OW, self.x, self.y, self.w, self.h,
            self.gs.menu_color,
            visible=False
        )

        self.childs[child.id] = child
        child.parent = self
        child.createLabel(f"{label}", "header", 28)
        child.createLabel(" ", "separator", 4, solid=True)

        child.createButton(
            "Back",
            partial(_switchContainer, child, self),
            self.gs.gray,
            self.gs.opacity,
            self.gs.button_font_size
        )

        callback = partial(_switchContainer, self, child) if not callback else callback
        self.createButton(
            label,
            callback,
            self.gs.gray,
            self.gs.opacity,
            self.gs.button_font_size,
            pos=pos,
            id=id
        )

        return child

    def createSlider(self, callback, label, value=0, min=0, max=100, pos="top"):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName(sanitizeInput(label))
        slider.pos = pos
        slider.setMinimum(min)
        slider.setMaximum(max)
        slider.setValue(value)
        slider.setMinimumHeight(self.gs.elements_height)
        slider.valueChanged.connect(callback)

        slider.setStyleSheet(f"""
            QSlider {{
                background-color: rgba({self.gs.gray}, {self.gs.opacity});
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
                margin-top: -{(self.gs.elements_height / 2) -10}px;
                margin-bottom: -{(self.gs.elements_height / 2) -10}px;
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

        self.widgets[slider.objectName()] = slider

    def getChild(self, id):
        return self.childs.get(sanitizeInput(id))

    def removeChild(self, id):
        child = self.childs.pop(sanitizeInput(id))

        if child.childs:
            for sub_child in list(child.childs.values()):
                child.removeChild(sub_child.id)

        for i in list(child.widgets.values()):
            child.removeWidget(i.objectName())

        child.container.deleteLater()
        child.widgets.clear()
        child.childs.clear()

    def getWidget(self, id):
        try:
            return self.layout.itemAt(self.layout.indexOf(self.widgets[sanitizeInput(id)]))
        except KeyError:
            return None

    def removeWidget(self, id):
        key = sanitizeInput(id)
        self.layout.removeWidget(self.widgets[key])
        self.widgets[key].deleteLater()
        self.widgets.pop(key)
        self.layout.update()

    def resetLayout(self):
        for id, widget in self.widgets.items():
            if widget.objectName() != "back":
                self.layout.removeWidget(widget)
                widget.deleteLater()
        self.widgets = {}
        self.layout.update()

    def populateContainer(self):
        total_widget_height = sum(widget.minimumHeight() for widget in self.widgets.values())
        empty_height = max(0, self.screen_height - total_widget_height)

        self.empty_widget = QWidget(self.container)
        self.empty_widget.setFixedSize(self.container.width(), empty_height)
        self.empty_widget.pos = "top"
        self.empty_widget.setObjectName("empty")
        self.widgets[self.empty_widget.objectName()] = self.empty_widget

        bottom_widgets = [widget for widget in self.widgets.values() if widget.pos == "bottom"][::-1]

        for widget in self.widgets.values():
            if widget.pos == "top":
                self.layout.addWidget(widget)
        for widget in bottom_widgets:
            if widget.pos == "bottom":
                self.layout.addWidget(widget)
        self.layout.update()
