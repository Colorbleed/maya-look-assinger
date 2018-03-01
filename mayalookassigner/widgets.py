import json
import logging

from avalon.vendor.Qt import QtWidgets, QtCore

import models
import commands
import views


NODEROLE = QtCore.Qt.UserRole + 1
MODELINDEX = QtCore.QModelIndex()


class AssetOutliner(QtWidgets.QWidget):

    selection_changed = QtCore.Signal()

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)

        layout = QtWidgets.QVBoxLayout()

        title = QtWidgets.QLabel("Assets")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 12px")

        model = models.AssetModel()
        view = views.View()
        view.setModel(model)
        view.customContextMenuRequested.connect(self.right_mouse_menu)

        from_selection_btn = QtWidgets.QPushButton("Get Looks From Selection")
        from_all_asset_btn = QtWidgets.QPushButton("Get Looks From All Assets")

        layout.addWidget(title)
        layout.addWidget(from_selection_btn)
        layout.addWidget(from_all_asset_btn)
        layout.addWidget(view)

        # Build connections
        from_selection_btn.clicked.connect(self.get_selected_assets)
        from_all_asset_btn.clicked.connect(self.get_all_assets)

        selection_model = view.selectionModel()
        selection_model.selectionChanged.connect(self.selection_changed)

        self.view = view
        self.model = model

        self.setLayout(layout)

        self.log = logging.getLogger(__name__)

    def clear(self):
        self.model.clear()

    def add_items(self, items):
        """Add new items to the outliner"""

        self.model.add_items(items)

    def get_look_from_selected_items(self):
        """Get look data from selected items

        Returns:
            list: list of dictionaries
        """

        items = []
        datas = self.get_selected_items()
        for data in datas:
            items.extend(data.get("looks", []))

        return items

    def get_selected_items(self):
        """Get current selected items from view

        Returns:
            list: list of dictionaries
        """

        selection_model = self.view.selectionModel()
        items = [row.data(NODEROLE) for row in
                 selection_model.selectedRows(0)]

        return items

    def get_all_assets(self):
        """Add all items from the current scene"""

        self.clear()
        items = commands.get_all_assets()
        self.add_items(items)

        return len(items) > 0

    def get_selected_assets(self):
        """Add all selected items from the current scene"""

        self.clear()
        items = commands.get_items_from_selection()
        self.add_items(items)

    def select_asset_from_items(self):
        """Select nodes from listed asset"""

        nodes = []
        items = self.get_selected_items()
        for item in items:
            nodes.extend(item["nodes"])

        commands.select(nodes)

    def right_mouse_menu(self, pos):
        """Build RMB menu for asset outliner"""

        active = self.view.currentIndex()  # index under mouse
        active = active.sibling(active.row(), 0)  # get first column
        globalpos = self.view.viewport().mapToGlobal(pos)

        menu = QtWidgets.QMenu(self.view)

        # Direct assignment
        apply_action = QtWidgets.QAction(menu, text="Select nodes")
        apply_action.triggered.connect(self.select_asset_from_items)

        if not active.isValid():
            apply_action.setEnabled(False)

        menu.addAction(apply_action)

        menu.exec_(globalpos)


class LookOutliner(QtWidgets.QWidget):

    menu_apply_action = QtCore.Signal()
    menu_queue_action = QtCore.Signal()

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)

        # look manager layout
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(10)

        # Looks from database
        title = QtWidgets.QLabel("Look Assignment")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 12px")
        title.setAlignment(QtCore.Qt.AlignCenter)

        model = models.LookModel()

        view = views.View()
        view.setModel(model)
        view.setMinimumHeight(180)
        view.setToolTip("Use right mouse button menu for direct actions")
        view.customContextMenuRequested.connect(self.right_mouse_menu)

        layout.addWidget(title)
        layout.addWidget(view)

        self.view = view
        self.model = model

        self.setLayout(layout)

        self.log = logging.getLogger(__name__)

    def clear(self):
        self.model.clear()

    def add_items(self, items):
        self.model.add_items(items)

    def get_selected_items(self):
        """Get current selected items from view

        Returns:
            list: list of dictionaries
        """

        datas = [i.data(NODEROLE) for i in self.view.get_indices()]
        items = [d for d in datas if d is not None]  # filter Nones

        return items

    def right_mouse_menu(self, pos):
        """Build RMB menu for look view"""

        active = self.view.currentIndex()  # index under mouse
        active = active.sibling(active.row(), 0)  # get first column
        globalpos = self.view.viewport().mapToGlobal(pos)

        if not active.isValid():
            return

        menu = QtWidgets.QMenu(self.view)

        # Direct assignment
        apply_action = QtWidgets.QAction(menu, text="Assign Directly")
        apply_action.triggered.connect(self.menu_apply_action)

        queue_action = QtWidgets.QAction(menu, text="Queue Assignment")
        queue_action.triggered.connect(self.menu_queue_action)

        menu.addAction(apply_action)
        menu.addAction(queue_action)

        menu.exec_(globalpos)


class QueueWidget(QtWidgets.QWidget):

    on_process_selected = QtCore.Signal()
    on_process_all = QtCore.Signal()
    on_emptied = QtCore.Signal()
    on_populated = QtCore.Signal()

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)

        layout = QtWidgets.QVBoxLayout()
        stack = QtWidgets.QStackedWidget()

        title = QtWidgets.QLabel("Queue")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 12px")
        title.setAlignment(QtCore.Qt.AlignCenter)

        # Turn off queue at start, show this widget
        queue_off_message = QtWidgets.QLabel("Queue is empty, add items to the"
                                             " queue to activate it")
        queue_off_message.setAlignment(QtCore.Qt.AlignCenter)
        queue_off_message.setStyleSheet("font-size: 12px;")

        # Method buttons, visible when queue is populated
        queue_widget = QtWidgets.QWidget()
        queue_layout = QtWidgets.QVBoxLayout()
        method_buttons_layout = QtWidgets.QHBoxLayout()

        process_selected_queued = QtWidgets.QPushButton("Process Selected")
        process_queued = QtWidgets.QPushButton("Process All")
        save_queue_btn = QtWidgets.QPushButton("fSave Queue to File")

        model = models.QueueModel()
        view = views.View()
        view.setModel(model)
        view.customContextMenuRequested.connect(self.right_mouse_menu)

        method_buttons_layout.addWidget(process_selected_queued)
        method_buttons_layout.addWidget(process_queued)
        method_buttons_layout.addWidget(save_queue_btn)

        queue_layout.addWidget(view)
        queue_layout.addLayout(method_buttons_layout)

        queue_widget.setLayout(queue_layout)

        stack.addWidget(queue_off_message)
        stack.addWidget(queue_widget)

        layout.addWidget(title)
        layout.addWidget(stack)

        self._process_selected_queued = process_selected_queued
        self._process_queued = process_queued
        self._save_queue_btn = save_queue_btn

        self.view = view
        self.model = model
        self.stack = stack

        self.setLayout(layout)

        self.log = logging.getLogger(__name__)

        self.setup_connections()

    def setup_connections(self):
        """Build connection between trigger and function"""

        self._process_selected_queued.clicked.connect(self.on_process_selected)
        self._process_queued.clicked.connect(self.on_process_all)
        self._save_queue_btn.clicked.connect(self.save_queue)

    def clear(self):
        self.model.clear()
        self.stack.setCurrentIndex(0)
        self.on_emptied.emit()

    def create_items(self, looks, assets):
        """Create a queue item based on the selection

        Args:
            looks (list): list of dicts with document information
            assets (list): list of dicts with document information

        Returns:
            list: collection of look and asset data in dictionaries

        """

        items = []

        # Restructure looks
        matches = self._reconstruct_looks(looks)
        for asset in assets:
            view_name = asset["asset"]
            asset_name = asset["asset_name"]
            match = matches[asset_name]

            # Create new item by copying the match
            items.append({"asset": view_name,
                          "asset_name": asset_name,
                          "version_name": match["name"],
                          "subset": match["subset"],
                          "version": match,
                          "nodes": asset["nodes"]})

        return items

    def add_items(self, items):
        """Add items to current queue"""

        validated = [i for i in items if self.validate(i)]
        if not validated:
            return

        if self.stack.currentIndex() != 1:
            self.stack.setCurrentIndex(1)

        self.model.add_items(validated)

    def validate(self, item):
        """If an entry already exists return False

        Args:
            item (dict): collection if look assignment data

        Returns:
            bool

        """

        parent = QtCore.QModelIndex()
        for row in range(self.model.rowCount(parent)):
            idx = self.model.index(row, 0, parent)
            data = idx.data(NODEROLE)
            if item == data:
                self.log.info("Already in queue")
                return False

        return True

    def get_items(self):
        """Get all items from the current queue

        Returns:
            list
        """

        items = []
        for row in range(self.model.rowCount(MODELINDEX)):
            idx = self.model.index(row, 0, MODELINDEX)
            index_data = idx.data(NODEROLE)
            items.append(index_data)

        return items

    def get_selected_items(self):
        """Return selected items

        Returns:
            list
        """

        selection_model = self.view.selectionModel()
        items = [row.data(NODEROLE) for row in
                 selection_model.selectedRows(0)]

        return items

    def remove_selected(self):
        """Remove selected item(s) from the queue"""

        active = self.view.currentIndex()
        active_row = active.row()

        items = self.get_items()
        items.pop(active_row)
        if not items:
            return

        self.clear()
        self.add_items(items)

    def process_items(self):
        """Apply the look based on the queued looks"""

        # Get queued items
        items = self.get_items()
        if not items:
            self.log.error("No looks found")
            return

        for item in items:
            commands.process_queued_item(item)

    def process_selected_items(self):
        """Apply the look based on the selected queued looks"""

        items = self.get_selected_items()
        if not items:
            self.log.error("No looks found")
            return

        for item in items:
            commands.process_queued_item(item)

    def save_queue(self):
        """Store the created queue in a json file"""

        _dir = commands.get_workfolder()
        fdialog = QtWidgets.QFileDialog()
        fpath, ext = fdialog.getSaveFileName(self, "Save File", _dir, "*.json")
        if not fpath:
            return

        assert ext == "*.json", "Wrong file type"

        queued_items = self._get_queued_items()
        if not queued_items:
            self.log.error("No queued items to store")
            return

        queue_data = commands.create_queue_out_data(queued_items)
        commands.save_to_json(fpath, {"queue": queue_data})

    def load_queue(self):
        """Open a file loader and import data from json"""

        _dir = commands.get_workfolder()
        fdialog = QtWidgets.QFileDialog()
        fpath, ext = fdialog.getOpenFileName(self, "Open File", _dir, "*.json")

        with open(fpath, "r") as fp:
            queue_data = json.load(fp)

        if "queue" not in queue_data:
            raise RuntimeError("Invalid queue data")

        items = commands.create_queue_in_data(queue_data["queue"])
        valid_items = [i for i in items if self.validate(i)]

        self.log.info("Found %d new item(s)" % len(valid_items))

        if self.stack.currentIndex() != 1:
            self.stack.setCurrentIndex(1)

        self.add_items(valid_items)

    def right_mouse_menu(self, pos):
        """Build and display RMB menu at current pointer position"""

        active = self.view.currentIndex()  # index under mouse
        active = active.sibling(active.row(), 0)  # get first column
        globalpos = self.view.viewport().mapToGlobal(pos)

        menu = QtWidgets.QMenu(self.view)

        if not active.isValid():
            return

        # region Create actions
        apply_action = QtWidgets.QAction(menu, text="Process All")
        apply_action.triggered.connect(self.process_items)

        apply_action = QtWidgets.QAction(menu, text="Process Selected")
        apply_action.triggered.connect(self.process_selected_items)

        rem_action = QtWidgets.QAction(menu, text="Remove Selected")
        rem_action.triggered.connect(self.remove_selected)

        save_action = QtWidgets.QAction(menu, text="Save Queue")
        save_action.triggered.connect(self.save_queue)

        clear_action = QtWidgets.QAction(menu, text="Clear Queue")
        clear_action.triggered.connect(self.clear)
        # endregion

        # Add actions
        menu.addAction(apply_action)
        menu.addAction(rem_action)
        menu.addSeparator()

        menu.addAction(save_action)
        menu.addAction(clear_action)

        menu.exec_(globalpos)

    def _reconstruct_looks(self, looks):
        """
        Reconstruct data
        Args:
            looks (list): list of dicts

        Returns:
            dict
        """

        look_lookup = {}

        for look in looks:
            match_dict = look["matches"]
            assets = match_dict.keys()
            for asset in assets:
                match = match_dict[asset]
                match["subset"] = look["subset"]
                look_lookup[asset] = match

        return look_lookup
