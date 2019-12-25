import math
from pyverilog.dataflow.dataflow_translate import *
#hush from graphviz import Digraph

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

RTL_THRESHOLD_VALUE = 24

class inout():
    def __init__(self, name, msb=None, lsb=None, type=None):
        self.name = name
        self.msb = msb
        self.lsb = lsb
        self.type = type
    
    def __eq__(self, other):
        if type(self) != type(other): 
            return False
        return (self.name, self.msb, self.lsb) == (other.name, other.msb, other.lsb)

    def __hash__(self):
        return hash((self.name, self.msb, self.lsb))

class data_flow_delay_calc():
    def __init__(self, top_module='graph', trans_list = None, reg_list=None):
        self.topmodule= top_module
        self.trans_ori_list = trans_list
        self.trans_end_list = copy.deepcopy(self.trans_ori_list)
        self.signal_delay = {}
        self.chain_path = []
        self.current_delay = {}
        self.current_signal = []
        self.concat_partselect = {}
        self.reg_list = reg_list
        self.reg_delay = {}
        
        for trans in self.trans_end_list:
            self.update_width(trans)
            self.update_delay(trans)
            if trans.msb is None:
                self.set_signal_delay_normal(trans)
                delay = copy.deepcopy(self.current_delay)
                self.signal_delay_update(delay)
                self.current_delay.clear()
            else:
                if trans.output in self.concat_partselect:
                    self.concat_partselect[trans.output].append(trans)
                else:
                    self.concat_partselect[trans.output] = [trans]

        for output, trans_list in self.concat_partselect.items():
            split_trans_list = self.get_concat_partselect_trans_list(trans_list)
            for trans in split_trans_list:
                self.set_signal_delay_concat_partselect(trans)
                delay = copy.deepcopy(self.current_delay)
                self.signal_delay_update(delay)
                self.current_delay.clear()

        # data flow graph visualization
        """        
        g = Digraph(self.topmodule)
        for key, value in self.signal_delay.items():
            g.edge(str(key[0]), str(key[1]), label= str(value),color='blue')
        g.view()
        """
        fo = open(self.topmodule+ ".dat", "w")

        self.calc_reg_delay()

        fo.write("line")
        fo.write("\t")
        fo.write("start register")
        fo.write("\t")
        fo.write("end register")
        fo.write("\t")
        fo.write("RTL value")
        fo.write("\n")

        #(input, output):
        for key, value in self.reg_delay.items():
            fo.write(value[1])

            fo.write("\t")
            input = key[0]
            if input.msb is not None:
                fo.write(input.name[-1].__repr__() + f"[{input.msb}:{input.lsb}]" )
            else:
                 fo.write(input.name[-1].__repr__())

            fo.write("\t")
            output = key[1]
            if output.msb is not None:
                fo.write(output.name[-1].__repr__() + f"[{output.msb}:{output.lsb}]" )
            else:
                 fo.write(output.name[-1].__repr__())

            fo.write("\t")
            fo.write(str(value[0]))

            fo.write("\t")
            if value[0] < RTL_THRESHOLD_VALUE:
                fo.write("warning")
                msg = self.reg_optimize(input, output)
                if len(msg) > 0:
                    fo.write("\t")
                    fo.write(msg)
                            
            fo.write("\n")

        fo.write("\n")
        fo.write("\n")
        fo.write("all signal RTL value")
        fo.write("\n")

        fo.write("line")
        fo.write("\t")
        fo.write("input")
        fo.write("\t")
        fo.write("output")
        fo.write("\t")
        fo.write("RTL value")
        fo.write("\n")

        #(input, output):
        for key, value in self.signal_delay.items():
            fo.write(value[1])

            fo.write("\t")
            input = key[0]
            if input.msb is not None:
                fo.write(input.name[-1].__repr__() + f"[{input.msb}:{input.lsb}]" )
            else:
                 fo.write(input.name[-1].__repr__())

            fo.write("\t")
            output = key[1]
            if output.msb is not None:
                fo.write(output.name[-1].__repr__() + f"[{output.msb}:{output.lsb}]" )
            else:
                 fo.write(output.name[-1].__repr__())


            fo.write("\t")
            fo.write(str(value[0]))
            fo.write("\n")
    
        fo.close()

    def reg_optimize(self, input, output):
        if input.msb is None:
            input_msg = self.reg_optimize_msg(input)
            if len(input_msg) > 0:
                input_str = f"optimize {input.name[-1]}"
                input_str += input_msg
                return input_str

        if output.msb is None:
            output_msg = self.reg_optimize_msg(output)
            if (len(output_msg) > 0):
                output_str = f"optimize {output.name[-1]} : "
                output_str += output_msg
                return output_str

        return ""

    def reg_optimize_msg(self, reg):
        reg_in_out_list = self.reg_optimize_one(reg)
        reg_in_list = reg_in_out_list[0]
        reg_out_list = reg_in_out_list[1]

        str = ""
        if reg_in_list and reg_out_list:
            for input in reg_in_list:
                for output in reg_out_list:
                    #self.print_optimize_msg(reg, input, output)
                    tmp = self.get_optimize_msg(reg , input, output)
                    if  tmp is not None:
                        str += tmp + ";"

        return str

    def reg_optimize_one(self, reg):
        reg_in = []
        reg_out= []
        for key, value in self.reg_delay.items():
            if reg == key[1]:
                reg_in.append(key[0])
            if reg == key[0]:
                reg_out.append(key[1])
        
        reg_in_max = self.find_reg_max_in_delay(reg, reg_in)
        reg_out_max = self.find_reg_max_out_delay(reg, reg_out)
        if (reg_in_max + reg_out_max) >  RTL_THRESHOLD_VALUE:
            return [[], []]
        else:
            return [reg_in, reg_out]

    def print_optimize_msg(self, reg , input ,output):
        if reg.msb is not None:
            return

        if input.msb is None and output.msb is None:
            print(f"optimize : {reg.name} {input.name} -> {output.name}")
        elif input.msb is not None and output.msb is None:
            print(f"optimize : {reg.name} {input.name}[{input.msb}:{input.lsb}] -> {output.name}")
        elif input.msb is None and output.msb is not None:
            print(f"optimize : {reg.name} {input.name} -> {output.name}[{output.msb}:{output.lsb}]")
        else:
            print(f"optimize : {reg.name} {input.name}[{input.msb}:{input.lsb}] -> {output.name}[{output.msb}:{output.lsb}]")

    def get_optimize_msg(self, reg , input ,output):
        if reg.msb is not None:
            return

        if input.msb is None and output.msb is None:
            return f" {input.name[-1]} -> {output.name[-1]}"
        elif input.msb is not None and output.msb is None:
            return f" {input.name[-1]}[{input.msb}:{input.lsb}] -> {output.name[-1]}"
        elif input.msb is None and output.msb is not None:
            return f"{input.name[-1]} -> {output.name[-1]}[{output.msb}:{output.lsb}]"
        else:
            return f"{input.name[-1]}[{input.msb}:{input.lsb}] -> {output.name[-1]}[{output.msb}:{output.lsb}]"

    def find_reg_max_in_delay(self, reg, inputs):
        max = 0
        inputs_copy = copy.deepcopy(inputs)
        while (len(inputs_copy)):
            input = inputs_copy.pop()
            value = self.reg_delay[(input, reg)]
            delay = value[0]
            if max < delay:
                max = delay

        return max

    def find_reg_max_out_delay(self, reg, outputs):
        max = 0
        outputs_copy = copy.deepcopy(outputs)
        while (len(outputs_copy)):
            out = outputs_copy.pop()
            value = self.reg_delay[(reg, out)]
            delay = value[0]
            if max < delay:
                max = delay

        return max        

    def calc_reg_delay(self):
        for reg in self.reg_list:
            if self.current_delay:
                self.current_delay.clear()

            if self.current_signal:
                self.current_signal.clear()

            signal_list = self.get_reg_start_signal(reg, self.signal_delay)
            if not signal_list:
                continue

            self.current_delay = self.get_signal_delay_by_start_signal_list(signal_list, self.signal_delay)

            if self.chain_path:
                self.chain_path.clear()
            while(len(self.current_delay)):
                 self.chain_generate(self.current_delay)
            #print(f'chain length : {len(self.chain_path)}')
            self.get_and_update_chain_reg_delay()

    def get_reg_delay(self):
        return self.reg_delay

    def get_reg_start_signal(self, start, signal_delay):
        signal_list= []
        for key in signal_delay:
            input = key[0]
            if input.name == start:
                if input not in signal_list:
                    signal_list.append(input)

        return signal_list

    def get_signal_delay_by_start_signal_list(self, signal_list, signal_delay):
        part_signal_delay = {}
        avoid_loop = []
        while(len(signal_list)):
            input = signal_list.pop()
            avoid_loop.append(input)
            for key,value in signal_delay.items():
                if input == key[0]:
                    part_signal_delay[key] = value
                    output = key[1]
                    if output not in signal_list and output not in avoid_loop:
                        signal_list.append(output)

        return part_signal_delay

    """
        'Uminus':0, 'Ulnot':0, 'Unot':0, 'Uand':0, 'Unand':0,
        'Uor':0, 'Unor':0, 'Uxor':0, 'Uxnor':0,
        'Power':1,
        'Times':2, 'Divide':2, 'Mod':2, 
        'Plus':3, 'Minus':3,
        'Sll':4, 'Srl':4, 'Sra':4,
        'LessThan':5, 'GreaterThan':5, 'LessEq':5, 'GreaterEq':5,
        'Eq':6, 'NotEq':6, 'Eql':6, 'NotEql':6,
        'And':7, 'Xor':7, 'Xnor':7,
        'Or':8,
        'Land':9,
        'Lor':10
    """   
    def update_width(self, trans):
        if trans.type == 'operator':
            if trans.operator == 'Times':
                for node in trans.children:
                    if node.width == 0:
                        self.update_width(node)
                    trans.width += node.width                        
            else:
                for node in trans.children:    
                    if node.width == 0:
                        self.update_width(node)
                    if trans.width < node.width:
                        trans.width = node.width

        if trans.type == 'branch':
            for node in trans.children:
                self.update_width(node)

    def update_delay(self, trans):
        if trans.type == 'operator':        
            width_list = [trans.width]

            if trans.operator == 'Times':
                width_list.extend(self.get_times_width(trans))
            trans.delay = self.delay_calc(trans.operator, len(trans.children), width_list)
            for node in trans.children:
                if node.type == 'operator':
                    self.update_delay(node)
                    
        if trans.type == 'branch':
            #if trans.tr
            trans.delay = 1
            
            for node in trans.children:
                self.update_delay(node)
   
    def signal_delay_update(self, delay):
        if delay == {}:
            return
        for key ,value in delay.items():
            if key in self.signal_delay:
                if value[0] <= self.signal_delay[key][0]:
                    continue
            self.signal_delay[key] = value

    """
    def signal_delay_update(self, delay):
        if delay == {}:
            return
        for key ,value in delay.items():
            flag = 0
            for gk, gv in self.signal_delay.items():
                if key[0].name == gk[0].name and key[0].msb == gk[0].msb and key[0].lsb == gk[0].lsb and \
                   key[1].name == gk[1].name and key[1].msb == gk[1].msb and key[1].lsb == gk[1].lsb:
                    if key in self.signal_delay:
                        print("key in signal_delay")
                    flag = 1
                    if value[0] <= gv[0]:
                        break
                    else:
                        self.signal_delay.pop(gk)
                        self.signal_delay[key] = value
                        break
            if flag == 0:
                self.signal_delay[key] = value
    """

    def set_signal_delay_normal(self, trans):
        if trans.parent:
            trans.root_path_delay = trans.parent.root_path_delay + trans.delay
        else:
            trans.root_path_delay = trans.delay
        
        if trans.type == 'terminal':
            """
            input = trans.input[-1].__repr__()
            output = trans.output[-1].__repr__()
            lineno = str(trans.lineno)
            """
            if trans.input in self.reg_list:
                type = "Reg"
            else:
                type = None
            input = inout(name=trans.input, msb=trans.msb, lsb=trans.lsb, type=type)
            if trans.output in self.reg_list:
                type = "Reg"
            else:
                type = None
            output = inout(name=trans.output, msb=trans.root.msb, lsb=trans.root.lsb, type=type)
            lineno = str(trans.lineno)

           # filter reset signal
            split_list = input.name[-1].__repr__().split("_")
            if "rst" in split_list or "RST" in split_list:
                return
            elif input.name == output.name:
                return
            else:
                self.current_delay[(input, output)] = (trans.root_path_delay, lineno)
             
        if trans.type == 'operator':
            for node in trans.children:
                self.set_signal_delay_normal(node)
        
        if trans.type == 'branch':
            for node in trans.children:
                self.set_signal_delay_normal(node)        

    def set_signal_delay_concat_partselect(self, trans):
        if trans.parent:
            trans.root_path_delay = trans.parent.root_path_delay + trans.delay
        else:
            trans.root_path_delay = trans.delay
        
        if trans.type == 'terminal':
            if trans.input in self.reg_list:
                type = "Reg"
            else:
                type = None

            input = inout(name=trans.input, msb=trans.msb, lsb=trans.lsb, type=type)

            if trans.output in self.reg_list:
                type = "Reg"
            else:
                type = None
            output = inout(name=trans.output, msb=trans.root.msb, lsb=trans.root.lsb, type=type)            

            lineno = str(trans.lineno)

            """
            if trans.msb is not None:
                input = trans.input[-1].__repr__() + f"[{trans.msb}:{trans.lsb}]"
            else:
                input = trans.input[-1].__repr__()

            if trans.root.msb is not None:
                output = trans.output[-1].__repr__() + f"[{trans.root.msb}:{trans.root.lsb}]"
            else:
                output = trans.output[-1].__repr__()
            """

            # filter reset signal
            split_list = input.name[-1].__repr__().split("_")
            if "rst" in split_list or "RST" in split_list:
                return
            elif input.name == output.name:
                return
            else:
                self.current_delay[(input, output)] = (trans.root_path_delay, lineno)
         
        elif trans.type == 'operator':
            for node in trans.children:
                self.set_signal_delay_concat_partselect(node)
        
        elif trans.type == 'branch':
            for node in trans.children:
                self.set_signal_delay_concat_partselect(node)  

        elif trans.type == 'concat':
            for node in trans.children:
                self.set_signal_delay_concat_partselect(node) 

    def get_concat_partselect_trans_list(self, trans_list):
        trans_list_split = []       
        trans_list_head = trans_list.pop(0)
        trans_list_split.append(trans_list_head)
        while len(trans_list):
            trans_list_head = trans_list.pop(0)
            #trans_list_split_copy = copy.deepcopy(trans_list_split) 
            #hushh modify
            trans_list_split_copy = copy.copy(trans_list_split)            
            for trans_split in trans_list_split_copy:
                self.split_concat_partselect(trans_list_head, trans_split, trans_list_split)

        return trans_list_split
                
    def split_concat_partselect(self, trans, split, trans_list_split):
        if trans in trans_list_split:
            return 

        if trans.msb < split.lsb:
            trans_list_split.append(trans)
        elif trans.lsb > split.msb:
            trans_list_split.append(trans)
        elif trans.lsb < split.lsb and trans.msb > split.lsb and trans.msb < split.msb:
            trans_low = copy.deepcopy(trans)
            trans_low.msb = split.lsb - 1

            trans_high = copy.deepcopy(trans)
            trans_high.lsb = split.lsb
                 
            split_low = copy.deepcopy(split)
            split_low.msb = trans.msb

            split_high = copy.deepcopy(split)
            split_high.lsb = trans.msb + 1

            trans_list_split.remove(split)
            trans_list_split.append(trans_low)
            trans_list_split.append(trans_high)
            trans_list_split.append(split_low)
            trans_list_split.append(split_high)

        elif trans.lsb > split.lsb and trans.lsb < split.msb and trans.msb > split.msb:
            trans_low = copy.deepcopy(trans)
            trans_low.msb = split.msb

            trans_high = copy.deepcopy(trans)
            trans_high.lsb = split.msb + 1
                 
            split_low = copy.deepcopy(split)
            split_low.msb = trans.lsb - 1

            split_high = copy.deepcopy(split)
            split_high.lsb = trans.lsb

            trans_list_split.remove(split)
            trans_list_split.append(trans_low)
            trans_list_split.append(trans_high)
            trans_list_split.append(split_low)
            trans_list_split.append(split_high)            

        elif trans.lsb >= split.lsb and trans.msb <= split.msb:
            if trans.lsb == split.lsb and trans.msb == split.msb:
                trans_list_split.append(trans)
            elif trans.lsb == split.lsb and trans.msb < split.msb:                                 
                split_low = copy.deepcopy(split)
                split_low.msb = trans.msb
            
                split_high = copy.deepcopy(split)
                split_high.lsb = trans.msb + 1
            
                trans_list_split.remove(split)
                trans_list_split.append(trans)
                trans_list_split.append(split_low)
                trans_list_split.append(split_high)                
            elif trans.lsb > split.lsb and trans.msb == split.msb:                                 
                split_low = copy.deepcopy(split)
                split_low.msb = trans.lsb - 1
            
                split_high = copy.deepcopy(split)
                split_high.lsb = trans.msb
            
                trans_list_split.remove(split)
                trans_list_split.append(trans)
                trans_list_split.append(split_low)
                trans_list_split.append(split_high)           
            elif trans.lsb > split.lsb and trans.msb < split.msb:                    
                split_low = copy.deepcopy(split)
                split_low.msb = trans.lsb - 1

                split_mid = copy.deepcopy(split)
                split_mid.lsb = trans.lsb
                split_mid.msb = trans.msb
            
                split_high = copy.deepcopy(split)
                split_high.lsb = trans.msb + 1
            
                trans_list_split.remove(split)
                trans_list_split.append(trans)
                trans_list_split.append(split_low)
                trans_list_split.append(split_mid)
                trans_list_split.append(split_high)

        elif trans.lsb <= split.lsb and trans.msb >= split.msb:
            if trans.lsb == split.lsb and trans.msb == split.msb:
                trans_list_split.append(trans)
            elif trans.lsb == split.lsb and trans.msb > split.msb:                                 
                trans_low = copy.deepcopy(split)
                trans_low.msb = split.msb
            
                trans_high = copy.deepcopy(trans)
                trans_high.lsb = split.msb + 1
            
                trans_list_split.append(trans_low)
                trans_list_split.append(trans_high)                

            elif trans.lsb < split.lsb and trans.msb == split.msb:                                 
                trans_low = copy.deepcopy(split)
                trans_low.msb = split.lsb - 1
            
                trans_high = copy.deepcopy(trans)
                trans_high.lsb = split.lsb
            
                trans_list_split.append(trans_low)
                trans_list_split.append(trans_high)           
            elif trans.lsb < split.lsb and trans.msb > split.msb:                    
                trans_low = copy.deepcopy(split)
                trans_low.msb = split.lsb - 1
        
                trans_mid = copy.deepcopy(split)
                trans_mid.lsb = split.lsb
                trans_mid.msb = split.msb
            
                trans_high = copy.deepcopy(split)
                trans_high.lsb = split.msb + 1
            
                trans_list_split.append(trans_low)
                trans_list_split.append(trans_mid)
                trans_list_split.append(trans_high)

    def delay_calc(self, operator, nr, width_list): 
        delay = 0
        width = width_list[0]
        if width == 0:
            width = 16 # some condition not consider,such as part_selct
        
        if 'Plus' == operator:
            if nr == 2: 
                delay = self.delay_calc_add(width)
            else :
                delay = self.delay_calc_add_seq(width, nr)

        elif 'Minus' == operator:
            if nr == 2: 
                delay = self.delay_calc_sub(width)
            else :
                delay = self.delay_calc_add_sub_seq(width, nr)

        elif 'Times' == operator:
            if len(width_list) != 3:
                print('error ,delay_calc() times operation : width_h,width_l')
                return
            width_h = width_list[1]
            width_l = width_list[2]
            delay = self.delay_calc_multi(width_h, width_l)

        elif 'Eq' == operator or 'NotEq' == operator:
            delay = self.delay_calc_equal_or_not(width)

        elif 'LessThan' == operator or 'GreaterThan' == operator:
            delay = self.delay_calc_great_or_less(width)
   
        elif 'LessEq' == operator or 'GreaterEq' == operator:
            delay = self.delay_calc_great_eq_or_less_eq(width)

        elif 'Sll' == operator or 'Srl' == operator:
            delay = self.delay_calc_shift_logic(width)

        elif 'Land' == operator or 'Lor' == operator:
            delay = self.delay_calc_land_lor(nr)

        elif 'Ulnot' == operator:
            delay = 1
        else: # "concat"
            delay = 0

        return delay

    def chain_generate(self, link_delay):
        if not link_delay:
            return
       
        link, delay = link_delay.popitem()
        link = list(link)
        input = link[0]
        output = link[1]
        #chain_path = copy.deepcopy(self.chain_path)
        chain_path = self.chain_path
        if not chain_path:
            self.chain_path.append(link)
        else:
            flag = 0
            for chain in chain_path:
                if input in chain and output in chain:
                    flag = 1
                    index_input = chain.index(input)
                    index_output = chain.index(output)
                    if (index_output - index_input) == 1:
                        continue
                    
                    elif index_input > index_output:
                        #print(f'warning input:{input.name} ,output:{output.name} reverse')
                        continue
                    else:
                        index = index_input + 1
                        while chain[index] != output:
                            chain.pop(index)
                        if chain not in self.chain_path:
                            self.chain_path.append(chain)
                    
                elif input in chain and output not in chain:
                    flag = 1
                    if input == chain[0]:
                        if link not in self.chain_path:
                            self.chain_path.append(link)
                    elif input == chain[-1]:
                        index = self.chain_path.index(chain)
                        self.chain_path[index].append(output)
                    else:
                        sig_index = chain.index(input)
                        new_chain = chain[0:sig_index + 1]
                        new_chain.append(output)
                        if new_chain not in self.chain_path:
                            self.chain_path.append(new_chain)
                elif input not in chain and output in chain:
                    flag = 1
                    index_output = chain.index(output)
                    new_chain = [input] + chain[index_output:]
                    
                    if new_chain not in self.chain_path:
                        self.chain_path.append(new_chain)
                    if output == chain[0]:
                        self.chain_path.remove(chain)
            if flag == 0:
                self.chain_path.append(link)

    def chain_calc(self,sig1, sig2):
        max_delay = 0
        max_path = []
        for chain in self.chain_path:
            if sig1 in chain and sig2 in chain:
                index_sig1 = chain.index(sig1)
                index_sig2 = chain.index(sig2)
                if index_sig1 < index_sig2:
                    path = chain[index_sig1 : index_sig2 + 1]
                else:
                    path = chain[index_sig2 : index_sig1 + 1]
                index = 0
                delay = 0
                while index + 1 < len(path) :
                    delay += self.signal_delay[tuple(path[index : index + 2])]
                    index += 1
                if delay > max_delay:
                    max_delay = delay
                    max_path = path
                    max_chain = chain
        return max_delay

    def get_and_update_chain_reg_delay(self):
        for chain in self.chain_path:
            for i in range(len(chain)):
                if i == 0:
                    continue
                if chain[i].type == "Reg": 
                    index = 0
                    delay = 0
                    while index < i :
                        delay += self.signal_delay[tuple(chain[index : index + 2])][0]
                        lineno = self.signal_delay[tuple(chain[index : index + 2])][1]
                        index += 1
                    key = (chain[0], chain[i])
                    if key in self.reg_delay:
                        if delay <= self.reg_delay[key][0]:
                            continue
                    self.reg_delay[key] = (delay, lineno)

    def delay_calc_add(self, width):
        return self.log_base2_ceil(width) + 3

    def delay_calc_sub(self, width):
        return self.log_base2_ceil(width) + 5

    def delay_calc_add_seq(self, width, nr):
        return self.delay_calc_wallace(nr) +                                   \
               self.log_base2_ceil(width + self.log_base2_ceil(nr)) + 3

    def delay_calc_add_sub_seq(self, width, nr):
        return self.delay_calc_add_seq(width, nr) + 1

    def delay_calc_multi_add_seq(self, width_h, width_l, nr):
        return 3 + self.log_base2_ceil(width_h) +                              \
               self.delay_calc_wallace(nr * math.ceil(width_l/2)) +            \
               self.log_base2_ceil(width_h + width_l + self.log_base2_ceil(nr))\
                + 3

    def delay_calc_multi_add(self, width_h, width_l):
        return 3 + self.log_base2_ceil(width_h) +                              \
               self.delay_calc_wallace(1 + math.ceil(width_l/2)) +             \
               self.log_base2_ceil(width_h + width_l + 1) + 3

    def delay_calc_multi(self, width_h, width_l):
        return 3 + self.log_base2_ceil(width_h) +                              \
               self.delay_calc_wallace(math.ceil(width_l/2)) +                 \
               self.log_base2_ceil(width_h + width_l) + 3

    def delay_calc_equal_or_not(self, width):
        return self.log_base2_ceil(width) + 1

    def delay_calc_great_or_less(self, width):
        return self.log_base2_ceil(width) + 4

    def delay_calc_great_eq_or_less_eq(self, width):
        return self.log_base2_ceil(width) + 5

    def delay_calc_shift_logic(self, width):
        return self.log_base2_ceil(width)

    def delay_calc_land_lor(self, nr):
        return self.log_base2_ceil(nr)
    
    def delay_calc_wallace(self, nr):
        if nr <= 2:
            return 1
        d0 = int(nr / 3)
        r0 = nr % 3
        i = 1
        while d0 != 1 and r0 != 0:
            d1 = int((2 * d0 + r0) / 3)
            r1 = (2 * d0 + r0) % 3
            d0 = d1
            r0 = r1
            i += 1
        return i

    def log_base2_ceil(self, width):
        return math.ceil(math.log(width, 2))

    def get_trans_depth(self, trans):
            depth = 0
            while trans.parent:
                depth +=1
                trans = trans.parent
        
            return depth
        
    def get_trans_branch_depth(self, trans):
        depth = 0
        while trans.parent:
            trans = trans.parent
            if trans.type:
                depth +=1
    
        return depth
    
    def search_first_trans_node(self, trans):
        if trans.children:
            return self.search_first_trans_node(trans.children[0])
        else:
            return trans       
    
    def search_next_trans_node(self, trans):
        if not trans.parent:
            return trans
    
        if trans == trans.parent.children[-1]:
            return trans.parent
    
        trans_list = trans.parent.children
        index = trans_list.index(trans)
        return trans_list[index + 1]   

    def get_times_width(self, trans):
        width_list = []
        width_h = trans.children[0].width
        width_l = trans.children[1].width
        if width_h < width_l:
            tmp = width_h
            width_h = width_l
            width_l = tmp
        width_list.append(width_h)
        width_list.append(width_l)
        return width_list

