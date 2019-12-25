from __future__ import absolute_import
from __future__ import print_function
import sys
import os


from pyverilog.vparser.parser import VerilogCodeParser
from pyverilog.dataflow.modulevisitor import ModuleVisitor
from pyverilog.dataflow.signalvisitor import SignalVisitor
from pyverilog.dataflow.bindvisitor import BindVisitor
from pyverilog.dataflow.optimizer import VerilogDataflowOptimizer

from pyverilog.vparser.ast import *
import pyverilog.utils.signaltype as signaltype
from pyverilog.dataflow.dataflow import *
from pyverilog.dataflow.dataflow_translate import *
from pyverilog.dataflow.dataflow_delay_calc import *
from pyverilog.dataflow.binary_to_multi_tree import *

# Increasing the maximum recursion size for deeper traversal
sys.setrecursionlimit(16 * 1024)

import logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')#DEBUG,INFO,WARNING

DELAY_THREAD = 30

class VerilogDataflowAnalyzer(VerilogCodeParser):
    def __init__(self, filelist, topmodule='TOP', noreorder=False, nobind=False,
                 preprocess_include=None,
                 preprocess_define=None):
        self.topmodule = topmodule
        self.terms = {}
        self.binddict = {}
        self.frametable = None
        files = filelist if isinstance(filelist, tuple) or isinstance(filelist, list) else [ filelist ]
        VerilogCodeParser.__init__(self, files,
                                   preprocess_include=preprocess_include,
                                   preprocess_define=preprocess_define)
        self.noreorder = noreorder
        self.nobind = nobind
        self.optimized_terms = None

        ast = self.parse()   
        module_visitor = ModuleVisitor()
        module_visitor.visit(ast)

    def generate(self):
        module_visitor = ModuleVisitor()
        modulenames = module_visitor.get_modulenames()
        moduleinfotable = module_visitor.get_moduleinfotable()
        
        signal_visitor = SignalVisitor(moduleinfotable, self.topmodule)
        signal_visitor.start_visit()
        frametable = signal_visitor.getFrameTable()

        if self.nobind:
            self.frametable = frametable
            return

        bind_visitor = BindVisitor(moduleinfotable, self.topmodule, frametable,
                                   noreorder=self.noreorder)

        bind_visitor.start_visit()
        dataflow = bind_visitor.getDataflows()

        self.frametable = bind_visitor.getFrameTable()        
        self.terms = dataflow.getTerms()
        self.binddict = dataflow.getBinddict()

        optimizer = VerilogDataflowOptimizer(self.terms, self.binddict)
        optimizer.resolveConstant()

        self.optimized_terms = optimizer.getResolvedTerms()
        optimized_binddict = optimizer.getResolvedBinddict()
        constlist = optimizer.getConstlist()
        ################################## debug info  ##########################
        logging.debug('debug info start:')

        ################## moduleinfotable######################################
        logging.debug('\n...ModuleInfoTable parse start:')

        logging.debug(f'modulenames type:{type(modulenames)}, modulenames:{modulenames}')
        logging.debug(f'moduleinfotable type:{type(moduleinfotable)} ,{moduleinfotable}')
        moduleinfo = moduleinfotable.dict[modulenames[0]]
        logging.debug(f'moduleinfo type :{type(moduleinfo)}')

        logging.debug(f'moduleinfo.name type : {type(moduleinfo.name)}, {moduleinfo.name}')
        logging.debug (f'moduleinfo.definition :{type(moduleinfo.definition)}')

        # display abstract syntax tree : ModuleDef 
        #moduleinfo.definition.show()#ast.ModuleDef

        logging.debug(f'moduleinfo.ioports type: {type(moduleinfo.ioports)}, {moduleinfo.ioports}')
        logging.debug(f'moduleinfo.params type : {type(moduleinfo.params)}, {moduleinfo.params}')
        logging.debug(f'moduleinfo.variables type:{type(moduleinfo.variables)}')
        logging.debug(f'moduleinfo.variables.signal type :{type(moduleinfo.variables.signal)}')#moduleinfo.variables.signal = SignalTable()
        logging.debug(f'moduleinfo.variables.const type : {type(moduleinfo.variables.const)}')#moduleinfo.variables.const = ConstTable()            
        logging.debug(f'moduleinfo.variables.genvar type :{type(moduleinfo.variables.genvar)}')#moduleinfo.variables.genvar = GenvarTable()

        logging.debug('module info  signal table:')
        for signal_key,signal_value in moduleinfo.variables.signal.dict.items():
            logging.debug(f'signal_key type :{type(signal_key)}, {signal_key}')
            logging.debug(f'signal_value type : {type(signal_value)}, len:{len(signal_value)}, type signal_value[0] :{type(signal_value[0])}')
            for i in range(len(signal_value)):
                logging.debug(f'name : {signal_value[i].name}, type : {signal_value[i].__class__.__name__}, lineno :{signal_value[i].lineno},width : {signal_value[i].width}')
                #signal_value[i].show() # ast.py node ,node.lineno ,node.name, node.width 

        logging.debug('module info  constant table:')
        for const_key,const_value in moduleinfo.variables.const.dict.items():
            logging.debug(f'const_key type :{type(const_key)}, {const_key}')
            logging.debug(f'const_value type : {type(const_value)}, len:{len(const_value)}, type const_value[0] :{type(const_value[0])}')
            #for i in range(len(const_value)):
                #const_value[i].show()        

        logging.debug('module info  genvar table:')
        for genvar_key,genvar_value in moduleinfo.variables.genvar.dict.items():
            logging.debug(f'genvar_key type :{type(genvar_key)}, {genvar_key}')
            logging.debug(f'genvar_value type : {type(genvar_value)}, len:{len(genvar_value)}, type genvar_value[0] :{type(genvar_value[0])}')
            #for i in range(len(genvar_value)):
                #genvar_value[i].show()
        logging.debug('...ModuleInfoTable parse end \n')
        ######################### Module info table end##############################


        ######################### SignalVisitor  ##############################
        logging.debug('...SignalVisitor parse start:')
        #self.moduleinfotable = moduleinfotable
        #self.top = top               
        frametable = signal_visitor.frames #self.frames = FrameTable()
        lables= signal_visitor.labels #self.labels = Labels()
        logging.debug(f'signal_visitor.labels type :{type(signal_visitor.labels)},{signal_visitor.labels}:')
        for name, label in signal_visitor.labels.labels.items():
            logging.debug(f'name type :{type(name)}, {name} ')#str
            logging.debug(f'label type :{type(label)}, {label.name}') #Label
        # set the top frame of top module
        #self.stackInstanceFrame(top, top)
        logging.debug(f'frametable type : {type(frametable)}')
        
        #frametable.dict = {}
        #frametable.current = ScopeChain()
        #frametable.function_def = False
        #frametable.task_def = False
        #frametable.for_pre = False
        #frametable.for_post = False
        #frametable.for_iter = None
        logging.debug(f'frametable.dict type: {type(frametable.dict)}')
        for frametable.dict_key, frametable.dict_value in frametable.dict.items():
             logging.debug(f'frametable.dict_key type :{type(frametable.dict_key)} , {frametable.dict_key}')#scopechain
             #for scope in frametable.dict_key:
             #   logging.debug(f'scope.scopename : {scope.scopename}, scope.scopetype : {scope.scopetype}')  
             #class Frame()
             #self.name = name
             #self.previous = previous
             #self.next = []
             #self.frametype = frametype
             
             #self.alwaysinfo = alwaysinfo
             #self.condition = condition
             
             #self.module = module
             #self.functioncall = functioncall
             #self.taskcall = taskcall
             #self.generate = generate
             #self.always = always
             #self.initial = initial
             #self.loop = loop
             #self.loop_iter = loop_iter
             
             #self.variables = Variables()
             #self.functions = FunctionInfoTable()
             #self.tasks = TaskInfoTable()
             #self.blockingassign = collections.OrderedDict()
             #self.nonblockingassign = collections.OrderedDict()
             
             #self.modulename = modulename

             
             logging.debug(f'\nframetable.dict_value type :{type(frametable.dict_value)}')#Frame()
             frame = frametable.dict_value
             logging.debug(f'frame.name type :{type(frame.name)}, frame.name : {frame.name}') #scopechain()
             logging.debug(f'frame.frametype type :{type(frame.frametype)}, frame.frametype : {frame.frametype}')# str : ('ifthen', 'ifelse', 'case', 'for', 'while', 'none')
             #logging.debug(f'frame.module type :{type(frame.module)}, frame.module : {frame.module}') #bool
             #logging.debug(f'frame.modulename type :{type(frame.modulename)}, frame.modulename : {frame.modulename}') #str: modulename
             logging.debug(f'frame.condition type :{type(frame.condition)}')
             if frame.condition is not None : logging.debug(f'frame.condition : {frame.condition}')
             else : logging.debug('')

             logging.debug(f'frame.variables type :{type(frame.variables)}:') #Variables()

             if len(frame.variables.signal.dict) : logging.debug('frame.variables.signal:') #signals only saved in module frame
             for signal_key,signal_value in frame.variables.signal.dict.items():
                 logging.debug(f'signal_key type :{type(signal_key)}, {signal_key}')
                 logging.debug(f'signal_value type:{type(signal_value)},len:{len(signal_value)},type signal_value[0]:{type(signal_value[0])}')
                 """
                 for i in range(len(signal_value)):
                    if i == 0:
                        value0 = signal_value[0]
                    if i == 1:
                        value1 = signal_value[1]
                        if value0 == value1:
                            logging.debug('why save twice?')                    
                    logging.debug(f'signal_value[{i}] name : {signal_value[i].name}, signal_value[{i}] type  {signal_value[i].__class__.__name__}, lineno :{signal_value[i].lineno},width type : {type(signal_value[i].width)}')
                    if signal_value[i].width:
                        logging.debug(f'width.msb : {signal_value[i].width.msb},width.lsb : {signal_value[i].width.lsb}')
                    signal_value[i].show() # ast.py node ,node.lineno ,node.name, node.width 
                """

                 i = 0
                 logging.debug(f'signal_value[{i}] name : {signal_value[i].name}, signal_value[{i}] type  {signal_value[i].__class__.__name__}, lineno :{signal_value[i].lineno},width type : {type(signal_value[i].width)}')
                 if signal_value[i].width:
                     logging.debug(f'width.msb : {signal_value[i].width.msb},width.lsb : {signal_value[i].width.lsb}')
                 #signal_value[i].show() # ast.py node ,node.lineno ,node.name, node.width 

             if len(frame.variables.const.dict) : logging.debug('frame.variables.const:')
             for const_key,const_value in frame.variables.const.dict.items():
                 logging.debug(f'const_key type :{type(const_key)}, {const_key}')
                 logging.debug(f'const_value type : {type(const_value)}, len:{len(const_value)}, type const_value[0] :{type(const_value[0])}')
                 #for i in range(len(const_value)):
                     #const_value[i].show()
             
             if len(frame.variables.genvar.dict):logging.debug('frame.variables.genvar:')
             for genvar_key,genvar_value in frame.variables.genvar.dict.items():
                 logging.debug(f'genvar_key type :{type(genvar_key)}, {genvar_key}')
                 logging.debug(f'genvar_value type : {type(genvar_value)}, len:{len(genvar_value)}, type genvar_value[0] :{type(genvar_value[0])}')
                 #for i in range(len(genvar_value)):
                     #genvar_value[i].show()

             logging.debug(f'frame.nonblockingassign type :{type(frame.nonblockingassign)} , {frame.nonblockingassign}')
             for key,value in frame.nonblockingassign.items():
                logging.debug(f'frame.nonblockingassign_key type :{type(key)}, frame.nonblockingassign_key : {key}')#scopechain
                logging.debug(f'frame.nonblockingassign_value type :{type(value)}, frame.nonblockingassign_value length : {len(value)}')#tuple
                for i in range(len(value)):
                    logging.debug(f'frame.nonblockingassign_value[{i}] :{type(value[i])}:')#dataflow.Bind
                    #class Bind 
                    #self.tree = tree
                    #self.dest = dest
                    #self.msb = msb
                    #self.lsb = lsb
                    #self.ptr = ptr
                    #self.alwaysinfo = alwaysinfo
                    #self.parameterinfo = parameterinfo
                    
                    bind = value[i]
                    logging.debug(f'bind.tree type :{type(bind.tree)}, {bind.tree}')
                    logging.debug( 'tree:' + bind.tree.tostr())
                    logging.debug(f'bind.dest type :{type(bind.dest)}, {bind.dest}')
                    #logging.debug(f'bind.msb type :{type(bind.msb)}, {bind.msb}')
                    #logging.debug(f'bind.lsb type :{type(bind.lsb)}, {bind.lsb}')
                    #logging.debug(f'bind.ptr type :{type(bind.ptr)}, {bind.ptr}')
                    #logging.debug(f'bind.alwaysinfo type :{type(bind.alwaysinfo)}, {bind.alwaysinfo}')
                    #logging.debug(f'bind.parameterinfo type :{type(bind.parameterinfo)}, {bind.parameterinfo}')

             logging.debug(f'frame.blockingassign type :{type(frame.blockingassign)} , {frame.blockingassign}:')
             for key,value in frame.blockingassign.items():
                logging.debug(f'frame.blockingassign_key type :{type(key)}, frame.blockingassign_key : {key}')#scopechain
                logging.debug(f'frame.blockingassign_value type :{type(value)}, frame.blockingassign_value length : {len(value)}')#tuple
                for i in range(len(value)):
                    logging.debug(f'frame.blockingassign_value[{i}] :{type(value[i])}:')#dataflow.Bind
                    #class Bind 
                    #self.tree = tree
                    #self.dest = dest
                    #self.msb = msb
                    #self.lsb = lsb
                    #self.ptr = ptr
                    #self.alwaysinfo = alwaysinfo
                    #self.parameterinfo = parameterinfo
                    
                    bind = value[i]
                    logging.debug(f'bind.tree type :{type(bind.tree)}, {bind.tree}')#data flow node
                    logging.debug(f'bind.dest type :{type(bind.dest)}, {bind.dest}')# ScopeChain
                    logging.debug(f'bind.msb type :{type(bind.msb)}, {bind.msb}')
                    logging.debug(f'bind.lsb type :{type(bind.lsb)}, {bind.lsb}')
                    logging.debug(f'bind.ptr type :{type(bind.ptr)}, {bind.ptr}')
                    logging.debug(f'bind.alwaysinfo type :{type(bind.alwaysinfo)}, {bind.alwaysinfo}')
                    logging.debug(f'bind.parameterinfo type :{type(bind.parameterinfo)}, {bind.parameterinfo}')                    



        logging.debug('...SignalVisitor parse end \n')
        ######################### SignalVisitor end##############################

        ######################### Bindvisitor start##############################        
        logging.debug('...BindVisitor parse start \n')

        
        #class BindVisitor:
        #self.moduleinfotable = moduleinfotable
        #self.top = top
        #self.frames = frames # bind_visitor.getFrameTable() same with signal_visitor.getFrameTable()
        #self.labels = Labels()
        #self.dataflow = DataFlow()
        
        logging.debug(f'bind_visitor.moduleinfotable type : {type(bind_visitor.moduleinfotable)},{bind_visitor.moduleinfotable}')
        if bind_visitor.moduleinfotable == moduleinfotable:
            logging.debug('bind visitor and signal visitor moduleinfotable are same')

        logging.debug(f'bind_visitor.top type : {type(bind_visitor.top)}, {bind_visitor.top}')#str:top module name

        logging.debug(f'bind_visitor.labels type : {type(bind_visitor.labels)}, {bind_visitor.labels}:')
        for name, label in bind_visitor.labels.labels.items():
            logging.debug(f'name type :{type(name)}, {name} ')#str
            logging.debug(f'label type :{type(label)}, {label.name}') #Label

        
        logging.debug(f'bind_visitor.dataflow type : {type(bind_visitor.dataflow)}')#DataFlow

        #class DataFlow(object):  
        #self.terms = {}
        #self.binddict = {}

        #self.functions = {}
        #self.function_ports = {}
        #self.tasks = {}
        #self.task_ports = {}
        #self.temporal_value = {}

        for tk, tv in sorted(bind_visitor.dataflow.terms.items(), key=lambda x:str(x[0])):
            logging.debug(f'dataflow.terms_key type : {type(tk)} dataflow.terms_value type : {type(tv)}')
            #logging.debug(tk, type(tv),tv.name,tv.termtype,tv.msb,tv.lsb)
            logging.debug('' + tv.tostr())

        logging.debug('\nfind out all reg sigals:')    
        for tk, tv in sorted(bind_visitor.dataflow.terms.items(), key=lambda x:str(x[0])):
            if signaltype.isReg(tv.termtype):
                logging.debug(f'name:{tv.name},type:{tv.termtype},msb:{tv.msb},lsb:{tv.lsb}')

     
        binddict = bind_visitor.dataflow.binddict
        logging.debug(f'binddic type:{type(binddict)} ,{binddict}')#dict
        logging.debug('\nBind:')
        for key, value in sorted(binddict.items(), key=lambda x:str(x[0])):
            logging.debug(f'binddict_key type : {type(key) , {key}}')#scopechain
            logging.debug(f'binddict_value type : {type(value)}, length of value :{len(value)},binddict_value[0] type:{type(value[0])}')#list,list[0] is Bind
            #if value[0].dest == key:
            #    logging.debug('binddict_value.dest binddict_key  ')

            #class Bind(object):
            #self.tree = tree
            #self.dest = dest
            #self.msb = msb
            #self.lsb = lsb
            #self.ptr = ptr
            #self.alwaysinfo = alwaysinfo


            for bind in value:
                logging.debug(f'bind.dest type : {type(bind.dest)}, bind.dest : {bind.dest}')               
                logging.debug(f'bind.tree type : {type(bind.tree)}, bind.tree :{bind.tree}') 
                logging.debug( 'tree:' + bind.tree.tostr())   

                if bind.msb is not None:logging.debug(f'bind.msb type : {type(bind.msb)}, bind.msb : {bind.msb}')
                if bind.lsb is not None: logging.debug( 'lsb:' + bind.lsb.tostr())
                if bind.ptr is not None: logging.debug( 'ptr:' + bind.ptr.tostr())                


        logging.debug('...BindVisitor parse end \n')
        ######################### Bindvisitor end############################## 

        logging.debug('debug info end')
        ################################ debug info end #######################

        ################################ translate #######################
        signal_translate_list= []
        for scopechain, bindlist in sorted(optimized_binddict.items(), key=lambda x:str(x[0])):
            for bind in bindlist:
                logging.debug(f'{bind.dest}')
                logging.debug('tree : ' +  bind.tree.tostr())
                            
                dataflow_trans = dataflow_translate(self, bind)
                dataflow_trans.start_translate()
                trans = dataflow_trans.get_translate_result()
   
                signal_translate_list.append(trans)

        multi_tree_list = []
        binary_tree_list = copy.deepcopy(signal_translate_list)
        for trans in binary_tree_list:
            bt_to_mt = binary_to_mult_tree()
            bt_to_mt.binary_to_mult(trans)
            multi_tree_list.append(trans)

        logging.debug('reg:')
        reg_list= []
        for tk, tv in sorted(bind_visitor.dataflow.terms.items(), key=lambda x:str(x[0])):
            if signaltype.isReg(tv.termtype):
                #logging.debug(f'name:{tv.name},type:{tv.termtype},msb:{tv.msb},lsb:{tv.lsb}')
                reg_list.append(tv.name)
        #logging.debug(f'reg_list : {reg_list}')            

        logging.debug ('\n...delay calculate:')
        delay_calc = data_flow_delay_calc(self.topmodule, multi_tree_list, reg_list)
        logging.debug ('finish')

        """
        for i in range(len(reg_list) - 1):
            for j in range(i+1, len(reg_list)):
                #logging.debug(i, j)
                delay = delay_calc.chain_calc(reg_list[i],reg_list[j])
                if delay != 0 and delay < DELAY_THREAD:
                    logging.warning(f'Warning {reg_list[i]} and {reg_list[j]} delay :{delay},less than threshold')
        """

    def is_scopechain_rename_type(self, scopechain):
        term = self.get_term_by_name(scopechain)
        if signaltype.isRename(term.termtype):
            return True
        else:
            return False


    def get_term_by_name(self,name):
        return self.terms[name]

    def get_width_by_name_str(self,name):
        for tk, tv in sorted(self.terms.items(), key=lambda x:str(x[0])):
            if name == tk[-1].scopename :
                logging.debug(f'{tk}, {type(tv)}, {tv.name}, {tv.termtype}, {tv.msb}, {tv.lsb}')
                return int(tv.msb.value) - int(tv.lsb.value) + 1


    def get_width_by_name_scopechain(self,name):
        #for tk, tv in sorted(self.terms.items(), key=lambda x:str(x[0])):
        """"
        for tk, tv in sorted(self.optimized_terms.items(), key=lambda x: str(x[0])):
            if name.__repr__() == tk.__repr__():
                logging.debug(f'{tk}, {type(tv)}, {tv.name}, {tv.termtype}, {tv.msb}, {tv.lsb}')
                return int(tv.msb.value) - int(tv.lsb.value) + 1
        """
        term = self.optimized_terms[name]
        return int(term.msb.value) - int(term.lsb.value) + 1

    def getFrameTable(self):
        return self.frametable

    #-------------------------------------------------------------------------
    def getInstances(self):
        if self.frametable is None: return ()
        return self.frametable.getAllInstances()

    def getSignals(self):
        if self.frametable is None: return ()
        return self.frametable.getAllSignals()

    def getConsts(self):
        if self.frametable is None: return ()
        return self.frametable.getAllConsts()

    def getTerms(self):
        return self.terms

    def getBinddict(self):
        return self.binddict
