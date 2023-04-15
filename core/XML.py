import lxml.etree as ET

class XML:
    def write(self, stream, data):
        out = self.build(data)
        stream.write(out)
    
    def build(self, data):
        root = self.build_nodes(data)
        ET.indent(root, space='    ', level=0)
        return ET.tostring(root, xml_declaration=True, 
                           pretty_print=True, encoding="utf-8").decode('utf-8').strip()

    def build_nodes(self, data, node = None):
        if isinstance(data, dict):
            for key, item in data.items():
                attr = item['attr'] if 'attr' in item else {}
                attr.update({k: str(v) for k, v in attr.items()})
                children = item['children'] if 'children' in item else None

                if (node == None):
                    node = ET.Element(key, attr)
                else:
                    node = ET.SubElement(node, key, attr)
                self.build_nodes(children, node)
        elif isinstance(data, list):
            if (node != None):
                for elt in data:
                    self.build_nodes(elt, node)
        elif (node != None) and (data != None):
            node = ET.SubElement(node, data)

        return node