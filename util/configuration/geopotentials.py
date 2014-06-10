from gribpcraster.application.readers import GRIBReader
from gribpcraster.exc.ApplicationException import ApplicationException
import os

__author__ = 'dominik'
dir_ = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(dir_, '../../configuration/geopotentials.xml')
DIR = os.path.join(dir_, '../../configuration/geopotentials/')
SHORT_NAMES = ['fis', 'z']
ADD_STRING = '<geopotential id=\"%(id)s\" name=\"%(name)s\"/>'


def read(grid_id):
    import untangle
    items = untangle.parse(CONFIG_FILE)
    for item in items.geopotentials.geopotential:
        if item['id'] == grid_id:
            return DIR + item['name']
    raise ApplicationException.get_programmatic_exc(4000, details="using " + grid_id)


def add(geop_file, log):
    import util.file.FileManager as fu
    fu.copy(geop_file, DIR)
    #get id from geofile
    args = {'shortName': SHORT_NAMES}
    id_ = GRIBReader.get_id(geop_file, reader_args=args)
    params={'id': id_, 'name': fu.fileName(geop_file)}
    xml_string = (ADD_STRING % params)
    log_string = '\n\n\nAdding geopotential file %s to configuration\n' % geop_file
    log_string += '\nYou will find the new element %s in %s\n\n\n' % (xml_string, fu.fileName(CONFIG_FILE))
    log(log_string, 'INFO')
    #add item in geopotentials.xml

    import xml.etree.ElementTree as ET
    tree = ET.parse(CONFIG_FILE)
    root = tree.getroot()
    ET.SubElement(root,'geopotential', params)
    ET.ElementTree(root).write(CONFIG_FILE, encoding='utf-8')
    #pretty print...
    from xml.dom import minidom
    pretty = '\n'.join([line for line in minidom.parse(open(CONFIG_FILE)).toprettyxml(indent=' '*2).split('\n') if line.strip()])
    el = ET.fromstring(pretty)
    ET.ElementTree(el).write(CONFIG_FILE, encoding='utf-8')