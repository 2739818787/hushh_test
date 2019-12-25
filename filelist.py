
from __future__ import absolute_import
from __future__ import print_function
import sys
import os

from  pyverilog.vparser.parser import *
from pyverilog.vparser.ast import *
from pyverilog.dataflow.visit import *
#from graphviz import Digraph

class ModulePreVisitor(NodeVisitor):
    def __init__(self):
        self.modulename = ''
        self.InstanceModuleList = []

    def visit_ModuleDef(self, node):
        self.modulename += node.name
        self.generic_visit(node)

    def visit_Portlist(self, node):
        pass

    def visit_Input(self, node):
        pass

    def visit_Output(self, node):
        pass

    def visit_Inout(self, node):
        pass

    def visit_Parameter(self, node):
        pass

    def visit_Locaparam(self, node):
        pass

    # Skip Rule
    def visit_Function(self, node):
        pass

    def visit_Task(self, node):
        pass

    def visit_Always(self, node):
        pass

    def visit_Initial(self, node):
        pass

    def visit_InstanceList(self, node):
        self.visit_Instance(node.instances[0])

    def visit_Instance(self, node):
        modulename = node.module
        if modulename not in self.InstanceModuleList:
            self.InstanceModuleList.append(modulename)

    def visit_Pragma(self, node):
        pass

    # get functions
    def get_modulename(self):
        return self.modulename

    def get_InstanceModuleList(self):
        return self.InstanceModuleList

class modulenode():
    def __init__(self, modulename):
        self.name = modulename
        self.parent = []
        self.child = []
        self.current_parent = None

class VerilogFilelistAnalyzer(VerilogCodeParser):
    def __init__(self, filelist, topmodule='TOP', noreorder=False, nobind=False,
                 preprocess_include=None,
                 preprocess_define=None):
        self.module_file_dict = {}
        self.module_instance_dict = {}
        self.root_node = None
        self.file_seq = None

        
        files = filelist if isinstance(filelist, tuple) or isinstance(filelist, list) else [ filelist ]
        for file in files:
            file = [file]
            VerilogCodeParser.__init__(self, file)
            ast = self.parse()
            module_pre_visitor = ModulePreVisitor()
            module_pre_visitor.visit(ast)
            modulename = module_pre_visitor.get_modulename()
            self.module_file_dict[modulename] = file[0] #str
            instance_module_list = module_pre_visitor.get_InstanceModuleList()
            self.module_instance_dict[modulename] = instance_module_list

    def GenModuleTree(self):
        root_node = []
        node_dict = {}
        #g = Digraph('graph')
        for modulename, instancelist in self.module_instance_dict.items():
            if modulename not in node_dict:
                parent_node = modulenode(modulename)
                node_dict[modulename] = parent_node
            else:
                parent_node = node_dict[modulename]

            if not instancelist:
                pass
            else:
                for instance in instancelist:
                    if instance not in node_dict:
                        child_node = modulenode(instance)
                        node_dict[instance] = child_node
                    else:
                        child_node = node_dict[instance]
                    
                    parent_node.child.append(child_node)
                    child_node.parent.append(parent_node)
                    #g.edge(parent_node.name, child_node.name, color='blue')
            
            if  not parent_node.parent:
                root_node.append(parent_node)

            root_node_copy = root_node[:]
            for node in root_node_copy:
                if node.parent:
                    root_node.remove(node)

        self.root_node = root_node                        
        print('root node:')
        for node in root_node:
            print(node.name)
        for modulename,file in self.module_file_dict.items():
            print(modulename + ':'+ str(file))
        #g.view()


    def GenFileSeq(self):
        file_seq = []
        for root_node in self.root_node:
            seq = []
            node = self.deep_search(root_node)
            while True:
                if node == root_node:
                    seq.append(node)
                    break

                if node == node.current_parent.child[-1]:
                    if node not in seq:
                        seq.append(node)
                    node = node.current_parent
                    continue

                if node not in seq:
                    seq.append(node)
                next_node = self.find_next_node(node)
                node = self.deep_search(next_node)

            #print(f'seq: {seq}')

            if len(file_seq) < len(seq):
                file_seq = copy.deepcopy(seq)

        print('file seq : ')
        for node in file_seq:
            print(node.name)

        self.file_seq = file_seq       
        return self.file_seq


    def deep_search(self, node):
        if node.child:
                node.child[0].current_parent = node
                return self.deep_search(node.child[0])
        else:
            return node

    def find_next_node(self, node):
        if not node.parent:
            return node
        if node == node.current_parent.child[-1]:
            return node.current_parent
        node_list = node.current_parent.child
        index = node_list.index(node)
        node_list[index + 1].current_parent = node.current_parent
        return node_list[index + 1]
            
    def get_module_file_map(self):
        return self.module_file_dict

    def get_top_module_name(self):
        top_node = self.file_seq[-1]
        return top_node.name


        


