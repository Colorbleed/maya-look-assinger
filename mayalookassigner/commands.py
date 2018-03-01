from collections import defaultdict
from copy import deepcopy
import json
import logging
import os

import maya.cmds as cmds

import colorbleed.maya.lib as cblib
from avalon import io, api


log = logging.getLogger(__name__)


def get_workfile():
    path = cmds.file(query=True, sceneName=True)
    return os.path.basename(path)


def get_workfolder():
    return os.path.dirname(cmds.file(query=True, sceneName=True))


def select(nodes):
    cmds.select(nodes)


def get_namespace_from_node(node):
    """Get the namespace from the given node

    Args:
        node (str): name of the node

    Returns:
        namespace (str)

    """
    _, ns = cmds.ls(node, showNamespace=True)
    return ns


def get_items_from_selection():
    """Get information from current selection"""

    items = []
    selection = cmds.ls(selection=True)
    hierarchy = cmds.listRelatives(selection,
                                   allDescendents=True,
                                   fullPath=True) or selection

    view_items = create_items_from_selection(hierarchy)
    items.extend(view_items)

    return items


def get_all_assets():
    """Get all assets from the scene, container based

    Returns:
        list: list of dictionaries
    """

    host = api.registered_host()

    items = []
    for container in host.ls():
        # We are not interested in looks but assets!
        if container["loader"] == "LookLoader":
            continue
        # Gather all information
        container_name = container["objectName"]
        content = cmds.sets(container_name, query=True)
        view_items = create_items_from_selection(content)
        if not view_items:
            continue

        items.extend(view_items)

    return items


def get_containers(nodes):
    """Get containers for the nodes

    Args:
        nodes (list): collect of strings, e.g: selected nodes

    Return:
        dict
    """

    host = api.registered_host()
    results = {}
    nodes = set(nodes)
    for container in host.ls():
        container_object = container['objectName']
        members = set(cmds.sets(container_object, query=True) or [])
        if nodes.intersection(members):
            results[container_object] = list(members)

    return results


def get_asset_id_item(item):

    if cmds.objectType(item) == "objectSet":
        content = cmds.sets(item, query=True)
        shapes = cmds.ls(content, long=True, type="shape")
        assert len(shapes) != 0, "Container has no shapes, this is an error"
        item = shapes[0]

    # Take the first shape, assuming all shapes in the container are from
    # the same asset
    cb_id = cblib.get_id(item)
    if not cb_id:
        return

    asset_id = cb_id.rsplit(":")[0]

    return asset_id


def create_asset_id_hash(nodes):
    """Create a hash based on cbId attribute value
    Args:
        nodes (list): a list of nodes

    Returns:
        dict
    """
    node_id_hash = defaultdict(list)
    for node in nodes:
        value = cblib.get_id(node)
        if value is None:
            continue

        asset_id = value.split(":")[0]
        node_id_hash[asset_id].append(node)

    return dict(node_id_hash)


def create_items_from_selection(content):
    """Create an item for the view based the container and content of it

    It fetches the look document based on the asset ID found in the content.
    The item will contain all important information for the tool to work.

    If there is an asset ID which is not registered in the project's collection
    it will log a warning message.

    Args:
        content (list): list of items which are in the container or selection

    Returns:
        list of dicts

    """

    asset_view_items = []

    id_hashes = create_asset_id_hash(content)
    if not id_hashes:
        return asset_view_items

    for _id, nodes in id_hashes.items():
        document = io.find_one({"_id": io.ObjectId(_id)},
                                projection={"name": True})

        # Skip if asset id is not found
        if not document:
            log.warning("Id not found in the database, skipping '%s'." % _id)
            log.warning("Nodes: %s" % nodes)
            continue

        looks = fetch_looks(document)
        namespace = get_namespace_from_node(nodes[0])
        asset = "%s : %s" % (namespace, document["name"])
        asset_view_items.append({"asset": asset,
                                 "asset_name": document["name"],
                                 "document": document,
                                 "looks": looks,
                                 "_id": _id,
                                 "nodes": nodes})
    return asset_view_items


def fetch_looks(document):
    """Get all looks based on the asset id

    Args:
        document (dict): database object

    Returns:
        looks (list): looks per asset {asset_name : [look_data, look_data]}
    """

    publish_looks = []

    # Get all data
    asset_name = document["name"]
    for subset in cblib.list_looks(document["_id"]):
        version = io.find_one({"type": "version",
                               "parent": subset["_id"]},
                               projection={"name": True, "parent": True},
                               sort=[("name", -1)])

        publish_looks.append({"asset_name": asset_name,
                              "subset": subset["name"],
                              "version": version})

    return publish_looks


def process_queued_item(entry):
    """
    Build the correct assignment for the selected asset
    Args:
        entry (dict):

    Returns:
        None

    """
    # Assume content is stored under nodes, fallback to containers
    nodes = entry.get("nodes", [])
    assert nodes, ("Could not find any nodes in selection or from "
                   "any containers")

    cblib.assign_look_by_version(nodes, entry["version"]["_id"])


def get_asset_data(objectId):
    """
    Check if objectId is an asset

    If the objectId is a representation if will look retrieve the parenthood
    and pick the asset from it

    Args:
        objectId:

    Returns:
        asset (dict)
    """

    document = io.find_one({"_id": io.ObjectId(objectId)})
    document_type = document["type"]
    if document_type == "representation":
        version, subset, asset, _ = io.parenthood(document)
    elif document_type == "asset":
        asset = document
    else:
        log.warning("Could not fetch enough data")
        return

    return asset


def create_queue_out_data(queue_items):
    """Create a JSON friendly block to write out

    Args:
        queue_items (list): list of dict

    Returns:
        list: list of dict

    """

    items = []
    for item in queue_items:
        # Ensure the io.ObjectId object is a string
        new_item = deepcopy(item)
        new_item["document"]["_id"] = str(item["document"]["_id"])
        new_item["document"]["parent"] = str(item["document"]["parent"])
        items.append(new_item)

    return items


def create_queue_in_data(queue_items):
    """Create a database friendly data block for the tool

    Args:
        queue_items (list): list of dict

    Returns:
        list: list of dict
    """
    items = []
    for item in queue_items:
        new_item = deepcopy(item)
        document = item["document"]
        new_item["document"]["_id"] = io.ObjectId(document["_id"])
        new_item["document"]["parent"] = io.ObjectId(document["parent"])
        items.append(new_item)

    return items


def save_to_json(filepath, items):
    """Store data in a json file"""

    log.info("Writing queue file ...")
    with open(filepath, "w") as fp:
        json.dump(items, fp, ensure_ascii=False)
    log.info("Successfully written file")


def remove_unused_looks():
    """Removes all loaded looks for which none of the shaders are used.

    This will cleanup all loaded "LookLoader" containers that are unused in
    the current scene.

    """

    host = api.registered_host()

    unused = list()
    for container in host.ls():
        if container['loader'] == "LookLoader":
            members = cmds.sets(container['objectName'], query=True)
            look_sets = cmds.ls(members, type="objectSet")
            for look_set in look_sets:
                # If the set is used than we consider this look *in use*
                if cmds.sets(look_set, query=True):
                    break
            else:
                unused.append(container)

    for container in unused:
        log.warning("Removing unused look container: %s",
                    container['objectName'])
        api.remove(container)
