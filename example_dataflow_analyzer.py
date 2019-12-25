from __future__ import absolute_import
from __future__ import print_function
import sys
import os
from optparse import OptionParser

# the next line can be removed after installation
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyverilog.utils.version
from pyverilog.dataflow.dataflow_analyzer import VerilogDataflowAnalyzer

import pyverilog.utils.util as util
import pyverilog.utils.verror as verror
import pyverilog.utils.signaltype as signaltype
import pyverilog.dataflow.replace as replace
from pyverilog.dataflow.dataflow import *
from pyverilog.dataflow.visit import *
from pyverilog.dataflow.merge import VerilogDataflowMerge
from pyverilog.dataflow.optimizer import VerilogDataflowOptimizer
from pyverilog.dataflow.filelist import *

def show(self,buf=sys.stdout, offset=0, attrnames=False, showlineno=True):
    indent = 2
    lead = ' ' * offset
    buf.write(lead + self.__class__.__name__ + ': ')
    if self.attr_names:
        if attrnames:
            nvlist = [(n, getattr(self,n)) for n in self.attr_names]
            attrstr = ', '.join('%s=%s' & nv for nv in nvlist)
        else:
            vlist = [getattr(self,n) for n in self.attr_names]
            attrstr = ', '.join('%s' % v for v in vlist)
        buf.write(attrstr)
    if showlineno:
        buf.write(' (at %s)' % self.lineno)
    buf.write('\n')
    for c in self.children():
        c.show(buf, offset + indent, attrnames, showlineno)

def main():
    print("Verilg Parser Tool \n ")
    print("User Guide:")
    print("Method 1 : When VerologParser.exe in the same path with filelist," +
           "program can auto scan and find the filelist ")
    print("Method 2 : When VerologParser.exe not in the same path with filelist," +
           "you should input the filelist path and name \n")
    print("Analysis Data:")
    print("The tool generate analysis data in the same path with filelist." + 
          "The \"verilog_parser_gen_data\" directory will be created .\n")

    optparser = OptionParser()
    optparser.add_option("-f","--file", action="store", dest="filename", help="assign filelist *.f") 
    optparser.add_option("-v","--version",action="store_true",dest="showversion",
                         default=False,help="Show the version")
    optparser.add_option("-I","--include",dest="include",action="append",
                         default=[],help="Include path")
    optparser.add_option("-D",dest="define",action="append",
                         default=[],help="Macro Definition")
    optparser.add_option("-t","--top",dest="topmodule",
                         default="TOP",help="Top module, Default=TOP")
    optparser.add_option("--nobind",action="store_true",dest="nobind",
                         default=False,help="No binding traversal, Default=False")
    optparser.add_option("--noreorder",action="store_true",dest="noreorder",
                         default=False,help="No reordering of binding dataflow, Default=False")

    (options, args) = optparser.parse_args()

    if True:
        curr_path = os.path.dirname(os.path.realpath(sys.executable))
        files = os.listdir(curr_path)
        for file in files:
            file_split = file.split('.')
            if 'f' in file_split:
                target_file = file

        print("current path: " + curr_path)
        if "target_file" in dir():
            print("target file : " + target_file)
            abs_path_file = curr_path + "\\" + target_file
            print("filelist : " + abs_path_file)
        else:
            print(" No filelist *.f found \n")
            while True:
                print("Please input filelist path and name, format:")
                print("Windows: D:\\project\\file.f")
                print("Linux: /project/file.f \n")
                abs_path_file = input("Input your filelist:")
                print("Your filelist:" + abs_path_file)
                if os.access(abs_path_file, os.F_OK):
                    print (abs_path_file + " exist")
                else:
                    print(abs_path_file + "not exist" )
                    continue

                if os.access(abs_path_file, os.R_OK):
                    print (abs_path_file +" is accessible to read")
                    break
                else:
                    print (abs_path_file +" is not accessible to read")
                    continue

    else:
        abs_path_file = 'D:\\project\\py_verilog\\verilogcode\\tod\\tod.f'
        
    fd = open(abs_path_file, 'r', encoding = 'utf-8')
    try:
        for line in fd.readlines():
            if line == '\n':
                continue
            else:
                line = line.strip('\n')
                args.append(line)
    finally:
        fd.close()

    (filepath, filename) = os.path.split(abs_path_file)
    print("path: " + filepath)

    dir_file = "verilog_parser_gen_data"
    new_dir = filepath + "\\" + dir_file
    if os.path.exists(new_dir):
        print(new_dir + " exists")
    else:
        print(new_dir + " not exists, create it")
        os.mkdir(new_dir)

    os.chdir(new_dir)
    print("Generate data in " + new_dir)

    filelist = args
    for f in filelist:
        if not os.path.exists(f): raise IOError("file not found: " + f)

    if len(filelist) == 0:
        showVersion()

    filelist_analyzer = VerilogFilelistAnalyzer(filelist)
    filelist_analyzer.GenModuleTree()
    filelist_seq = filelist_analyzer.GenFileSeq()
    #options.topmodule = filelist_analyzer.get_top_module_name()

    module_file_map = filelist_analyzer.get_module_file_map()
    for i in range(len(filelist_seq)):
        node = filelist_seq[i]
        print('Start parse:' + node.name)
        
        #if node.name != 'tod_cm':
            #continue
        file = module_file_map[node.name]
        filelist = [file]
        options.topmodule = node.name
        analyzer=VerilogDataflowAnalyzer(filelist, options.topmodule,
                                       noreorder=options.noreorder,
                                       nobind=options.nobind,
                                       preprocess_include=options.include,
                                       preprocess_define=options.define)

        analyzer.generate()
        print('finish')

    """
    module_file_map = filelist_analyzer.get_module_file_map()
    name = 'partselect'
    file = module_file_map[name]
    filelist = [file]
    options.topmodule = name
    analyzer=VerilogDataflowAnalyzer(filelist, options.topmodule,
                                   noreorder=options.noreorder,
                                   nobind=options.nobind,
                                   preprocess_include=options.include,
                                   preprocess_define=options.define)

    analyzer.generate()  
    """
    print('finish all')
    print('Any question, pls contact hu.shaohua@zte.com.cn.')

if __name__ == '__main__':
    main()
