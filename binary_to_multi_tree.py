
class binary_to_mult_tree():
    def __init__(self):
        pass

    def binary_to_mult(self, node, parent=None):
        if parent is None:
            parent = node

        if node.type == 'branch':
            for child in node.children:
                self.binary_to_mult(child, child)
        elif node.type == 'terminal':
            pass
        elif node.type == 'operator':
            if node.operator != parent.operator:#actually should be class
                if node not in parent.children:
                    node.parent = parent
                    parent.children.append(node)
                self.binary_to_mult(node, node)
            else :
                for child in node.children:                    
                    if child.type == 'terminal':
                        if child.parent != parent:
                            child.parent = parent
                            parent.children.append(child)
                    if child.type == 'operator':
                        self.binary_to_mult(child, parent)
                if node != parent:
                    node.parent.children.remove(node)


