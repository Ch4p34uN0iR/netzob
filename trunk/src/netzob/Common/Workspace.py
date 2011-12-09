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

#+---------------------------------------------------------------------------+ 
#| Standard library imports
#+---------------------------------------------------------------------------+
import logging
import os
import datetime
import re


from lxml import etree

from xml.etree import ElementTree

from netzob.Common.TypeConvertor import TypeConvertor
import shutil


#+---------------------------------------------------------------------------+
#| Local Imports
#+---------------------------------------------------------------------------+

WORKSPACE_NAMESPACE = "http://www.netzob.org/workspace"

def loadWorkspace_0_1(workspacePath, workspaceFile):  
    
    
    
    # Parse the XML Document as 0.1 version
    tree = ElementTree.ElementTree()
    
    tree.parse(workspaceFile)
    xmlWorkspace = tree.getroot()
    wsName = xmlWorkspace.get('name', 'none')
    wsCreationDate = TypeConvertor.xsdDatetime2PythonDatetime(xmlWorkspace.get('creation_date'))[0]
    
    # Parse the configuration to retrieve the main paths
    xmlWorkspaceConfig = xmlWorkspace.find("{" + WORKSPACE_NAMESPACE + "}configuration")
    pathOfTraces = xmlWorkspaceConfig.find("{" + WORKSPACE_NAMESPACE + "}traces").text
    
    pathOfLogging = None
    if xmlWorkspaceConfig.find("{" + WORKSPACE_NAMESPACE + "}logging") != None and xmlWorkspaceConfig.find("{" + WORKSPACE_NAMESPACE + "}logging").text != None and len(xmlWorkspaceConfig.find("{" + WORKSPACE_NAMESPACE + "}logging").text) > 0:
        pathOfLogging = xmlWorkspaceConfig.find("{" + WORKSPACE_NAMESPACE + "}logging").text
        
    pathOfPrototypes = None
    if xmlWorkspaceConfig.find("{" + WORKSPACE_NAMESPACE + "}prototypes") != None and xmlWorkspaceConfig.find("{" + WORKSPACE_NAMESPACE + "}prototypes").text != None and len(xmlWorkspaceConfig.find("{" + WORKSPACE_NAMESPACE + "}prototypes").text) > 0:
        pathOfPrototypes = xmlWorkspaceConfig.find("{" + WORKSPACE_NAMESPACE + "}prototypes").text
    
    # Instantiation of the workspace
    workspace = Workspace(wsName, wsCreationDate, workspacePath, pathOfTraces, pathOfLogging, pathOfPrototypes)
    
    # Load the projects
    if xmlWorkspace.find("{" + WORKSPACE_NAMESPACE + "}projects") != None :
        for xmlProject in xmlWorkspace.findall("{" + WORKSPACE_NAMESPACE + "}projects/{" + WORKSPACE_NAMESPACE + "}project") :
            project_path = xmlProject.get("path")
            workspace.referenceProject(project_path)
    
    return workspace    
    





#+---------------------------------------------------------------------------+
#| Workspace :
#|     Class definition of a Workspace
#| @author     : {gbt,fgy}@amossys.fr
#| @version    : 0.2
#+---------------------------------------------------------------------------+
class Workspace(object):
    
    # The name of the configuration file
    CONFIGURATION_FILENAME = "workspace.xml"
    
    # /!\ WARNING :
    # The dict{} which defines the parsing function associated with each schema
    # is added to the end of the document
    
    #+-----------------------------------------------------------------------+
    #| Constructor
    #| @param path : path of the workspace
    #+-----------------------------------------------------------------------+
    def __init__(self, name, creationDate, path, pathOfTraces, pathOfLogging, pathOfPrototypes):
        self.name = name
        self.path = path
        self.creationDate = creationDate
        self.projects_path = []
        self.pathOfTraces = pathOfTraces
        self.pathOfLogging = pathOfLogging
        self.pathOfPrototypes = pathOfPrototypes
        
    def getProjects(self):
        projects = []
        for project_path in self.getProjectsPath() :
            from netzob.Common.Project import Project
            project = Project.loadProject(self, project_path)
            if project != None :
                projects.append(project)
                
        return projects
           
        
    #+-----------------------------------------------------------------------+
    #| referenceProject :
    #|     reference a project in the workspace
    #+-----------------------------------------------------------------------+
    def referenceProject(self, project_path):
        path = project_path
        if not path in self.projects_path :
            self.projects_path.append(path)
        else :
            logging.warn("The project declared in " + path + " is already referenced in the workspace.")
        
    def saveConfigFile(self):
        
        workspaceFile = os.path.join(self.path, Workspace.CONFIGURATION_FILENAME)
        
        logging.info("Save the config file of the workspace " + self.getName() + " in " + workspaceFile)
        
        # Dump the file
        ElementTree.register_namespace('netzob', WORKSPACE_NAMESPACE)
        
        root = ElementTree.Element("{" + WORKSPACE_NAMESPACE + "}workspace")
        print TypeConvertor.pythonDatetime2XSDDatetime(self.getCreationDate())
        root.set("creation_date", TypeConvertor.pythonDatetime2XSDDatetime(self.getCreationDate()))
        root.set("name", str(self.getName()))
        
        xmlWorkspaceConfig = ElementTree.SubElement(root, "{" + WORKSPACE_NAMESPACE + "}configuration")
        
        xmlTraces = ElementTree.SubElement(xmlWorkspaceConfig, "{" + WORKSPACE_NAMESPACE + "}traces")
        xmlTraces.text = str(self.getPathOfTraces())
        
        xmlLogging = ElementTree.SubElement(xmlWorkspaceConfig, "{" + WORKSPACE_NAMESPACE + "}logging")
        xmlLogging.text = str(self.getPathOfLogging())
        
        xmlPrototypes = ElementTree.SubElement(xmlWorkspaceConfig, "{" + WORKSPACE_NAMESPACE + "}prototypes")
        xmlPrototypes.text = str(self.getPathOfPrototypes())
        
        xmlWorkspaceProjects = ElementTree.SubElement(root, "{" + WORKSPACE_NAMESPACE + "}projects")        
        for projectPath in self.getProjectsPath():
            xmlProject = ElementTree.SubElement(xmlWorkspaceProjects, "{" + WORKSPACE_NAMESPACE + "}project")
            xmlProject.set("path", projectPath)
        
        
        tree = ElementTree.ElementTree(root)
        tree.write(workspaceFile)
    
    
    @staticmethod
    def createWorkspace(name, path):        
        tracesPath = os.path.join(path, "traces")
        projectsPath = os.path.join(path, "projects")
        prototypesPath = os.path.join(path, "prototypes")
        pathOfLogging = os.path.join(path, "logging/logging.conf")
        
        # we create a "traces" directory if it doesn't yet exist
        if not os.path.isdir(tracesPath) :
            os.mkdir(tracesPath)
            
        # we create a "projects" directory if it doesn't yet exist
        if not os.path.isdir(projectsPath) :
            os.mkdir(projectsPath)
        
        # we create the "prototypes" directory if it doesn't yet exist
        if not os.path.isdir(prototypesPath) :
            os.mkdir(prototypesPath)
            # we upload in it the default repository file
            from netzob.Common.ResourcesConfiguration import ResourcesConfiguration
            staticRepositoryPath = os.path.join(os.path.join(ResourcesConfiguration.getStaticResources(), "defaults"), "repository.xml.default")
            shutil.copy(staticRepositoryPath, os.path.join(prototypesPath, "repository.xml"))
            
        workspace = Workspace(name, datetime.datetime.now(), path, tracesPath, pathOfLogging, prototypesPath)
        workspace.saveConfigFile()
        
        return workspace
    
    @staticmethod
    def loadWorkspace(workspacePath):    
        
        workspaceFile = os.path.join(workspacePath, Workspace.CONFIGURATION_FILENAME)
        
        # verify we can open and read the file
        if workspaceFile == None :
            return None
        # is the workspaceFile is a file
        if not os.path.isfile(workspaceFile) :
            logging.warn("The specified workspace's configuration file (" + str(workspaceFile) + ") is not valid : its not a file.")
            return None
        # is it readable
        if not os.access(workspaceFile, os.R_OK) :
            logging.warn("The specified workspace's configuration file (" + str(workspaceFile) + ") is not readable.")
            return None
        
        # We validate the file given the schemas
        for xmlSchemaFile in Workspace.WORKSPACE_SCHEMAS.keys() :            
            from netzob.Common.ResourcesConfiguration import ResourcesConfiguration
            xmlSchemaPath = os.path.join(ResourcesConfiguration.getStaticResources(), xmlSchemaFile)
            # If we find a version which validates the XML, we parse with the associated function
            if Workspace.isSchemaValidateXML(xmlSchemaPath, workspaceFile) :
                logging.debug("The file " + str(xmlSchemaPath) + " validates the workspace configuration file.")
                parsingFunc = Workspace.WORKSPACE_SCHEMAS[xmlSchemaFile]
                workspace = parsingFunc(workspacePath, workspaceFile)
                if workspace != None :
                    return workspace
        
        return None
        
    
    @staticmethod
    def isSchemaValidateXML(schemaFile, xmlFile):
        # is the schema is a file
        if not os.path.isfile(schemaFile) :
            logging.warn("The specified schema file (" + str(schemaFile) + ") is not valid : its not a file.")
            return False
        # is it readable
        if not os.access(schemaFile, os.R_OK) :
            logging.warn("The specified schema file (" + str(schemaFile) + ") is not readable.")
            return False
        
        schemaF = open(schemaFile, "r")
        schemaContent = schemaF.read()
        schemaF.close()
        
        if schemaContent == None or len(schemaContent) == 0:
            logging.warn("Impossible to read the schema file (no content found in it)")
            return False
        
        schema_root = etree.XML(schemaContent)
        schema = etree.XMLSchema(schema_root)
        
        try :
            xmlRoot = etree.parse(xmlFile)
            schema.assertValid(xmlRoot)
            return True
        except :
            log = schema.error_log
            error = log.last_error
            logging.info(error)
            return False
        return False
    
    # Dictionary of workspace versions, must be sorted by version DESC
    WORKSPACE_SCHEMAS = {"xsds/0.1/Workspace.xsd": loadWorkspace_0_1}   
    
    def getName(self):
        return self.name
    def getCreationDate(self):
        return self.creationDate
    def getPath(self):
        return self.path
    def getProjectsPath(self):
        return self.projects_path
    def getPathOfTraces(self):
        return self.pathOfTraces
    def getPathOfLogging(self):
        return self.pathOfLogging
    def getPathOfPrototypes(self):
        return self.pathOfPrototypes
    
