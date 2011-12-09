# -*- coding: utf-8 -*-

#+---------------------------------------------------------------------------+
#|         01001110 01100101 01110100 01111010 01101111 01100010             | 
#+---------------------------------------------------------------------------+
#| NETwork protocol modeliZatiOn By reverse engineering                      |
#| ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~+
#| @license      : GNU GPL v3                                                |
#| @copyright    : Georges Bossert and Frederic Guihery                      |
#| @url          : http://code.google.com/p/netzob/                          |
#| ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~+
#| @author       : {gbt,fgy}@amossys.fr                                      |
#| @organization : Amossys, http://www.amossys.fr                            |
#+---------------------------------------------------------------------------+

#+---------------------------------------------- 
#| Global Imports
#+----------------------------------------------
import uuid
import logging
import re
import struct
import gtk
import glib

#+---------------------------------------------- 
#| Local Imports
#+----------------------------------------------
from netzob.Common.ConfigurationParser import ConfigurationParser
from netzob.Common.TypeIdentifier import TypeIdentifier

#+---------------------------------------------- 
#| C Imports
#+----------------------------------------------
import libNeedleman

#+---------------------------------------------- 
#| Group :
#|     definition of a group of messages
#| all the messages in the same group must be 
#| considered as equivalent
#| @author     : {gbt,fgy}@amossys.fr
#| @version    : 0.2
#+---------------------------------------------- 
class Group(object):
    
    #+----------------------------------------------
    #| Fields in a group message definition :
    #|     - unique ID
    #|     - name
    #|     - messages
    #+----------------------------------------------
    
    #+---------------------------------------------- 
    #| Constructor :
    #| @param name : name of the group
    #| @param messages : list of messages 
    #+----------------------------------------------   
    def __init__(self, name, messages, properties={}):
        # create logger with the given configuration
        self.log = logging.getLogger('netzob.Common.Group.py')
        self.id = uuid.uuid4() 
        self.name = name
        self.messages = messages
        for message in self.messages:
            message.setGroup(self)
        self.properties = properties
        self.score = 0
        self.alignment = ""
        self.columns = [] # each column element contains a dict : {'name', 'regex', 'selectedType', 'tabulation', 'description', 'color'}

        

    def __repr__(self, *args, **kwargs):
        return self.name + "(" + str(round(self.score, 2)) + ")"

    def __str__(self, *args, **kwargs):
        return self.name + "(" + str(round(self.score, 2)) + ")"

    def clear(self):
        self.columns = []
        self.alignment = ""
        del self.messages[:]

    

    
   
    
        
    #+---------------------------------------------- 
    #| addMessage : add a message in the list
    #| @param message : the message to add
    #+----------------------------------------------
    def addMessage(self, message):
        message.setGroup(self)
        self.messages.append(message)
        
    def addMessages(self, messages):
        for message in messages:
            message.setGroup(self)
            self.messages.append(message)
    
    #+---------------------------------------------- 
    #| getXMLDefinition : 
    #|  returns the XML description of the group
    #| @return a string containing the xml def.
    #+----------------------------------------------
    def getXMLDefinition(self):
        result = "<dictionnary>\n"
        
        result += self.alignment
        
        result += "\n</dictionnary>\n"
        
        return result

    #+---------------------------------------------- 
    #| getScapyDissector : 
    #| @return a string containing the scapy dissector of the group
    #+----------------------------------------------
    def getScapyDissector(self):
        self.refineRegexes() # In order to force the calculation of each field limits
        s = ""
        s += "class " + self.getName() + "(Packet):\n"
        s += "    name = \"" + self.getName() + "\"\n"
        s += "    fields_desc = [ \n"

        iCol = 0
        for col in self.getColumns():
            if self.isRegexStatic(col['regex']):
                s += "                    StrFixedLenField(\"" + col['name'] + "\", " + self.getRepresentation(col['regex'], iCol) + ")\n"
            else: # Variable field of fixed size
                s += "                    StrFixedLenField(\"" + col['name'] + "\", None)\n"                
            ## If this is a variable field
                # StrLenField("the_varfield", "the_default_value", length_from = lambda pkt: pkt.the_lenfield)
            iCol += 1
        s += "                  ]\n"

        ## Bind current layer with the underlying one
        # bind_layers( TCP, HTTP, sport=80 )
        # bind_layers( TCP, HTTP, dport=80 )

        return s

    #+---------------------------------------------- 
    #| slickRegex:
    #|  try to make smooth the regex, by deleting tiny static
    #|  sequences that are between big dynamic sequences
    #+----------------------------------------------
    def slickRegex(self):
        # Use the default protocol type for representation
        configParser = ConfigurationParser()
        valID = configParser.getInt("clustering", "protocol_type")
        if valID == 0:
            aType = "ascii"
        else:
            aType = "binary"

        res = False
        i = 1
        while i < len(self.columns) - 1:
            if self.isRegexStatic(self.columns[i]['regex']):
                if len(self.columns[i]['regex']) == 2: # Means a potential negligeable element that can be merged with its neighbours
                    if self.isRegexOnlyDynamic(self.columns[i - 1]['regex']):
                        if self.isRegexOnlyDynamic(self.columns[i + 1]['regex']):
                            res = True
                            col1 = self.columns.pop(i - 1) # we retrieve the precedent regex
                            col2 = self.columns.pop(i - 1) # we retrieve the current regex
                            col3 = self.columns.pop(i - 1) # we retrieve the next regex
                            lenColResult = int(col1['regex'][4:-2]) + 2 + int(col3['regex'][4:-2]) # We compute the len of the aggregated regex
                            self.columns.insert(i - 1, {'name' : "Name",
                                                        'regex' : "(.{," + str(lenColResult) + "})",
                                                        'selectedType' : aType,
                                                        'tabulation' : 0,
                                                        'description' : "",
                                                        'color' : ""
                                                        })
            i += 1

        if res:
            self.slickRegex() # Try to loop until no more merges are done
            self.log.debug("The regex has been slicked")

        # TODO: relaunch the matrix step of getting the maxIJ to merge column/row
        # TODO: memorize old regex/align
        # TODO: adapt align

    #+---------------------------------------------- 
    #| findSizeFields:
    #|  try to find the size fields of each regex
    #+----------------------------------------------    
    def findSizeFields(self, store):
        if len(self.columns) == 0:
            return
        typer = TypeIdentifier()
        iCol = 0
        # We cover each field for a potential size field
        for col in self.getColumns():
            if self.isRegexStatic(col['regex']): # Means the element is static, and we exclude it for performance issue
                iCol += 1
                continue
            cellsSize = self.getCellsByCol(iCol)
            j = 0
            # We cover each field and aggregate them for a potential payload
            while j < len(self.getColumns()):
                # Initialize the aggregate of messages from colJ to colK
                aggregateCellsData = []
                for l in range(len(cellsSize)):
                    aggregateCellsData.append("")

                # Fill the aggregate of messages and try to compare its length with the current expected length
                k = j
                while k < len(self.getColumns()):
                    if k != j:
                        for l in range(len(cellsSize)):
                            aggregateCellsData[l] += self.getCellsByCol(k)[l]

                    # We try to aggregate the successive right sub-parts of j if it's a static column (TODO: handle dynamic column / TODO: handle left subparts of the K column)
                    if self.isRegexStatic(self.getColumns()[j]['regex']):
                        lenJ = len(self.getColumns()[j]['regex'])
                        stop = 0
                    else:
                        lenJ = 2
                        stop = 0
                    for m in range(lenJ, stop, -2):
                        for n in [4, 0, 1]: # loop over different possible encoding of size field
                            res = True
                            for l in range(len(cellsSize)):
                                if self.isRegexStatic(self.getColumns()[j]['regex']):
                                    targetData = self.getColumns()[j]['regex'][lenJ - m:] + aggregateCellsData[l]
                                else:
                                    targetData = self.getCellsByCol(j)[l] + aggregateCellsData[l]

                                # Handle big and little endian for size field of 1, 2 and 4 octets length
                                rawMsgSize = typer.toBinary(cellsSize[l][:n * 2])
                                if len(rawMsgSize) == 1:
                                    expectedSizeType = "B"
                                elif len(rawMsgSize) == 2:
                                    expectedSizeType = "H"
                                elif len(rawMsgSize) == 4:
                                    expectedSizeType = "I"
                                else: # Do not consider size field with len > 4
                                    res = False
                                    break
                                (expectedSizeLE,) = struct.unpack("<" + expectedSizeType, rawMsgSize)
                                (expectedSizeBE,) = struct.unpack(">" + expectedSizeType, rawMsgSize)
                                if (expectedSizeLE != len(targetData) / 2) and (expectedSizeBE != len(targetData) / 2):
                                    res = False
                                    break
                            if res:
                                if self.isRegexStatic(self.getColumns()[j]['regex']): # Means the regex j element is static and a sub-part is concerned
                                    store.append([self.id, iCol, n * 2, j, lenJ - m, k, -1, "Group " + self.name + " : found potential size field (col " + str(iCol) + "[:" + str(n * 2) + "]) for an aggregation of data field (col " + str(j) + "[" + str(lenJ - m) + ":] to col " + str(k) + ")"])
                                    self.log.info("In group " + self.name + " : found potential size field (col " + str(iCol) + "[:" + str(n * 2) + "]) for an aggregation of data field (col " + str(j) + "[" + str(lenJ - m) + ":] to col " + str(k) + ")")
                                else:
                                    store.append([self.id, iCol, n * 2, j, -1, k, -1, "Group " + self.name + " : found potential size field (col " + str(iCol) + "[:" + str(n * 2) + "]) for an aggregation of data field (col " + str(j) + " to col " + str(k) + ")"])
                                    self.log.info("In group " + self.name + " : found potential size field (col " + str(iCol) + "[:" + str(n * 2) + "]) for an aggregation of data field (col " + str(j) + " to col " + str(k) + ")")
                                break
                    k += 1
                j += 1
            iCol += 1

    

    #+---------------------------------------------- 
    #| applyDataType_cb:
    #|  Called when user wants to apply a data type to a field
    #+----------------------------------------------
    def applyDataType_cb(self, button, iCol, dataType):
        self.setDescriptionByCol(iCol, dataType)

    

    #+---------------------------------------------- 
    #| search:
    #|  search a specific data in messages
    #+----------------------------------------------    
    def search(self, data):
        if len(self.columns) == 0:
            return None

        # Retrieve the raw data ('abcdef0123') from data
        rawData = data.encode("hex")
        hbox = gtk.HPaned()
        hbox.show()
        # Treeview containing potential data carving results ## ListStore format :
        # int: iCol
        # str: encoding
        store = gtk.ListStore(int, str)
        treeviewRes = gtk.TreeView(store)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Column')
        column.pack_start(cell, True)
        column.set_attributes(cell, text=0)
        treeviewRes.append_column(column)
        column = gtk.TreeViewColumn('Encoding')
        column.pack_start(cell, True)
        column.set_attributes(cell, text=1)
        treeviewRes.append_column(column)
        treeviewRes.set_size_request(200, 300)
        treeviewRes.show()
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.show()
        scroll.add(treeviewRes)
        hbox.add(scroll)

        ## Algo (first step) : for each column, and then for each cell, try to find data
        iCol = 0
        for col in self.getColumns():
            matchASCII = 0
            matchBinary = 0
            for cell in self.getCellsByCol(iCol):
                matchASCII += cell.count(rawData)
                matchBinary += cell.count(data)
            if matchASCII > 0:
                store.append([iCol, "ASCII"])
            if matchBinary > 0:
                store.append([iCol, "binary"])
            iCol += 1

        ## TODO: Algo (second step) : for each message, try to find data

        # Preview of matching fields in a treeview ## ListStore format :
        # str: data
        treeview = gtk.TreeView(gtk.ListStore(str))
        treeviewRes.connect("cursor-changed", self.searchResultSelected_cb, treeview, data)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Data')
        column.pack_start(cell, True)
        column.set_attributes(cell, markup=0)
        treeview.append_column(column)
        treeview.set_size_request(700, 300)
        treeview.show()
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.show()
        scroll.add(treeview)
        hbox.add(scroll)
        return hbox

    #+---------------------------------------------- 
    #| searchResultSelected_cb:
    #|  Callback when clicking on a search result.
    #|  It shows a preview of the finding
    #+----------------------------------------------
    def searchResultSelected_cb(self, treeview, treeviewTarget, data):
        typer = TypeIdentifier()
        treeviewTarget.get_model().clear()
        (model, it) = treeview.get_selection().get_selected()
        if(it):
            if(model.iter_is_valid(it)):
                iCol = model.get_value(it, 0)
                encoding = model.get_value(it, 1)
                treeviewTarget.get_column(0).set_title("Column " + str(iCol))
                for cell in self.getCellsByCol(iCol):
                    if encoding == "ASCII":
                        cell = typer.toASCII(cell)
                        arrayCell = cell.split(data)
                    elif encoding == "binary":
                        arrayCell = cell.split(data)
                    arrayCell = [ glib.markup_escape_text(a) for a in arrayCell ]
                    if len(arrayCell) > 1:
                        styledCell = str("<span foreground=\"red\" font_family=\"monospace\">" + data + "</span>").join(arrayCell)
                    else:
                        styledCell = cell
                    treeviewTarget.get_model().append([ styledCell ])

    

    

    #+---------------------------------------------- 
    #| Type handling
    #+----------------------------------------------
    def setTypeForCols(self, aType):
        for col in self.getColumns():
            col['selectedType'] = aType

    def setTypeForCol(self, iCol, aType):
        if iCol >= 0 and iCol < len(self.columns) :
            self.columns[iCol]['selectedType'] = aType
        else :
            self.log.warning("The type for the column " + str(iCol) + " is not defined ! ")

    def getSelectedTypeByCol(self, iCol):
        if iCol >= 0 and iCol < len(self.columns) :
            return self.columns[iCol]['selectedType']
        else :
            self.log.warning("The type for the column " + str(iCol) + " is not defined ! ")
            return "binary"

    def getPossibleTypesByCol(self, iCol):
        if iCol >= 0 and iCol < len(self.columns) :
            cells = self.getCellsByCol(iCol)
            typeIdentifier = TypeIdentifier()        
            return typeIdentifier.getTypes(cells)
        else :
            self.log.warning("The possible types for the column " + str(iCol) + " are not defined ! ")
            return ["binary"]

    

    

    

    #+---------------------------------------------- 
    #| GETTERS : 
    #+----------------------------------------------
    def getID(self):
        return self.id
    def getName(self):
        return self.name
    def getMessages(self):
        return self.messages   
    def getAlignment(self):
        return self.alignment.strip()
    def getScore(self):
        return self.score
    def getMessageByID(self, messageID):
        for message in self.getMessages():
            if str(message.getID()) == str(messageID):
                return message
        return None
    def getColumns(self):
        return self.columns
    def getProperties(self):
        return self.properties
    
    def getTabulationByCol(self, iCol):
        if iCol >= 0 and iCol < len(self.columns) :
            return self.columns[iCol]['tabulation']
    def getRegexByCol(self, iCol):
        if iCol >= 0 and iCol < len(self.columns) :
            return self.columns[iCol]['regex']
    def getDescriptionByCol(self, iCol):
        if iCol >= 0 and iCol < len(self.columns) :
            return self.columns[iCol]['description']
    def getColorByCol(self, iCol):
        if iCol >= 0 and iCol < len(self.columns) :
            return self.columns[iCol]['color']

    #+---------------------------------------------- 
    #| SETTERS : 
    #+----------------------------------------------
    def setID(self, id):
        self.id = id
    def setName(self, name):
        self.name = name
    def setMessages(self, messages): 
        self.messages = messages
    def setAlignment(self, alignment):
        self.alignment = alignment
    def setScore(self, score):
        self.score = score
    def setColumnNameByCol(self, iCol, name):
        if len(self.columns) > iCol:
            self.columns[iCol]['name'] = name
    def setColumns(self, columns):
        self.columns = columns
    def setProperties(self, properties):
        self.properties = properties
    def setTabulationByCol(self, iCol, n):
        if iCol >= 0 and iCol < len(self.columns) :
            self.columns[iCol]['tabulation'] = int(n)
    def setDescriptionByCol(self, iCol, descr):
        if iCol >= 0 and iCol < len(self.columns) :
            self.columns[iCol]['description'] = descr
    def setRegexByCol(self, iCol, regex):
        if iCol >= 0 and iCol < len(self.columns) :
            self.columns[iCol]['regex'] = regex
    def setColorByCol(self, iCol, color):
        if iCol >= 0 and iCol < len(self.columns) :
            self.columns[iCol]['color'] = color
