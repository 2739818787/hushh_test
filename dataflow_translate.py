from pyverilog.dataflow.dataflow import *

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

CONSTANT_WIDTH = 8
param_table = {}

def get_tree_value(tree):
    if isinstance (tree, DFConstant):
        return int(tree.value)

    if isinstance (tree, DFEvalValue):
        return int(tree.value)

    elif isinstance(tree, DFTerminal):
        if tree.name not in param_table:
            print("error:parameter no value")
            return 0
        return param_table[tree.name]

    elif isinstance(tree, DFOperator):
        trees = tree.nextnodes
        if tree.operator == "Plus":
            return get_tree_value(trees[0]) + get_tree_value(trees[1])
        if tree.operator == "Minus":
            return get_tree_value(trees[0]) - get_tree_value(trees[1])
        if tree.operator == "Times":
            return get_tree_value(trees[0]) * get_tree_value(trees[1])

class translate():
    def __init__(self, bind=None, output=None, parent=None, type=None, tree=None, root=None, lineno=0):
        self.bind = bind
        self.output = output#output=bind.dest
        self.msb = None
        self.lsb = None
        self.input = None
        self.width = 0
        self.operator = None
        self.parent = parent
        self.children = []
        self.type = type
        self.tree = tree
        self.delay = 0
        self.root_path_delay = 0
        self.root = root
        self.lineno = lineno
    """    
    def __eq__(self, other):
        return  self.output     == other.output     and     \
                self.msb        == other.msb        and     \
                self.lsb        == other.lsb        and     \
                self.input      == other.input      and     \
                self.width      == other.width      and     \
                self.operator   == other.operator   and     \
                self.type       == other.type       and     \
                self.delay      == other.delay      and     \
                self.lineno     == other.lineno
    """

    def set_input(self, input):
        self.input = input
        
    def add_operator(self, operator):
        self.operator = operator

    def  update_width(self, width):
        self.width  = width

    def  set_lineno(self, lineno):
        self.lineno  = lineno        

    def add_child(self, child):
        self.children.append(child)

    def set_parent(self, parent):
        self.parent = parent

    def set_type(self, type):
        self.type = type

class dataflow_translate():
    def __init__(self,DataflowAnalyzer,bind):
        self.DataflowAnalyzer = DataflowAnalyzer
        #bind.dest type is scopechain
        self.trans = translate(bind=bind, output=bind.dest, tree=bind.tree)
        self.trans.root = self.trans
        if bind.lsb and bind.msb:
            self.trans.lsb = int(bind.lsb.value)
            self.trans.msb = int(bind.msb.value)
            self.width = self.trans.msb - self.trans.lsb
            self.trans.type = "concat_partselect"

        if bind.parameterinfo == "parameter":
            value = get_tree_value(bind.tree)
            param_table[bind.dest] = value
        
    def start_translate(self):
        self.handle_dataflow(self.trans)

    def get_translate_result(self):
        return self.trans

    """
       value is string,maybe this:
       4"b1011 ,  16'h58F,  10d'33 ,33
    """
    def get_constant_width(self, value):
        return CONSTANT_WIDTH

    def handle_constant(self, trans):
        width = self.get_constant_width(trans.tree.value)
        if trans.root.type == "concat_partselect" and width > trans.root.width:
            width = trans.root.width         
        trans.update_width(width)
        trans.set_type("constant")

    def handle_evalvalue(self, trans):
        width = trans.tree.value
        if trans.root.type == "concat_partselect" and width > trans.root.width:
            width = trans.root.width
        trans.update_width(width)
        trans.set_type("evalvalue")

    def handle_terminal(self, trans):
        terminal = trans.tree
        trans.set_input(terminal.name)
        if trans.width == 0:
            width = self.DataflowAnalyzer.get_width_by_name_scopechain(terminal.name)
        else:
            width = trans.width
        trans.update_width(width)
        trans.set_type("terminal")
        trans.set_lineno(terminal.lineno)
   
    def handle_partselect(self, trans):
        partselect = trans.tree
        trans.tree = trans.tree.var
        if hasattr(partselect, 'var') and isinstance(partselect.var, DFTerminal):
            trans.msb = get_tree_value(partselect.msb)
            trans.lsb = get_tree_value(partselect.lsb)
            width = trans.msb - trans.lsb
        self.handle_dataflow(trans)

    def handle_concat(self, trans):
        if trans.root.type == "concat_partselect":
            width = trans.root.width
        else:
            width = 0
        trans.update_width(width)
        trans.tree.operator = "concat"
        trans.add_operator(trans.tree.operator)
        trans.set_type("concat")
        for tree in trans.tree.nextnodes:
            child = translate(output=trans.output, parent=trans, tree=tree, root=trans.root)
            trans.add_child(child)
            self.handle_dataflow(child)

    # shield
    def handle_pointer(self, trans):
        width = 32
        trans.update_width(width)
        trans.set_type("constant")        
        
    def handle_operator(self, trans):
        trans.add_operator(trans.tree.operator)
        trans.set_type("operator")
        for tree in trans.tree.nextnodes:
            child = translate(output=trans.output, parent=trans, tree=tree, root=trans.root)
            trans.add_child(child)
            self.handle_dataflow(child)

    def handle_branch(self, trans):
        branch = trans.tree
        trans.set_type("branch")# branch delay level is 1

        child = translate(output=trans.output, parent=trans, tree=branch.condnode, root=trans.root)
        trans.add_child(child)
        self.handle_dataflow(child)
                
        if branch.truenode:
            child = translate(output=trans.output, parent=trans, tree=branch.truenode,root=trans.root)
            trans.add_child(child)
            self.handle_dataflow(child)            

        if branch.falsenode:
            child = translate(output=trans.output, parent=trans, tree=branch.falsenode, root=trans.root)
            trans.add_child(child)
            self.handle_dataflow(child)           

    def handle_dataflow(self, trans):
        if isinstance (trans.tree, DFConstant):
            self.handle_constant(trans)
        elif isinstance (trans.tree, DFEvalValue):
            self.handle_evalvalue(trans)
        elif isinstance(trans.tree, DFTerminal):
            self.handle_terminal(trans)
        elif isinstance(trans.tree, DFOperator):
            self.handle_operator(trans)
        elif isinstance(trans.tree, DFBranch):
            self.handle_branch(trans)
        elif isinstance(trans.tree, DFPartselect):
            self.handle_partselect(trans)
        elif isinstance(trans.tree, DFConcat):
            self.handle_concat(trans)
        elif isinstance(trans.tree, DFPointer):
            self.handle_pointer(trans)
        else:
            logging.warning(f"undefined data flow type : {type(trans.tree)}")


