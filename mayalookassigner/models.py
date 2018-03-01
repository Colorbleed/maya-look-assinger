from collections import defaultdict
from avalon.tools.cbsceneinventory import model


class AssetModel(model.TreeModel):

    COLUMNS = ["asset"]
    NAMESPACE = False

    def add_items(self, items):
        """
        Add items to model with needed data
        Args:
            items(list): collection of item data

        Returns:
            None
        """

        self.beginResetModel()

        for item in items:
            item_node = model.Node()
            item_node.update(item)
            self.add_child(item_node)

        self.endResetModel()

    def data(self, index, role):

        if not index.isValid():
            return

        if role == model.TreeModel.NodeRole:
            node = index.internalPointer()
            return node

        return super(AssetModel, self).data(index, role)


class LookModel(model.TreeModel):

    COLUMNS = ["subset", "match"]

    def add_items(self, items):
        """
        Add items to model with needed data
        Args:
            items(list): collection of item data

        Returns:
            None
        """

        self.beginResetModel()

        subsets = defaultdict(list)
        for item in items:
            subsets[item["subset"]].append(item)

        for subset, assets in sorted(subsets.iteritems()):

            item_node = model.Node()

            item_node["subset"] = subset
            item_node["match"] = len(assets)
            item_node["matches"] = {asset["asset_name"]: asset["version"]
                                    for asset in assets}

            self.add_child(item_node)

        self.endResetModel()


class QueueModel(AssetModel):

    COLUMNS = ["asset", "subset", "version_name"]

    def data(self, index, role):

        if not index.isValid():
            return

        if role == model.TreeModel.NodeRole:
            node = index.internalPointer()
            return node

        return super(AssetModel, self).data(index, role)
