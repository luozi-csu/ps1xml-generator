# -*- coding: utf-8 -*-
import numpy as np
import yaml
import os
import sys
import getopt
from xml.dom import minidom

modelPrefix = "Sangfor.Acloud.Models."

def dealPath(path):
    # 使用栈对路径中的'.'和'..'进行处理
    res = []
    for item in path:
        if item == '.':
            continue
        elif item == '..':
            res.pop()
        else:
            res.append(item)
    return res

# Generator成员:
# filePath - yaml文件的绝对路径，可以唯一标识一个Generator
# data - yaml文件中的内容
# models - yaml文件中的schemas
class Generator:
    def __init__(self, filePath):
        self.filePath = os.path.abspath(filePath)
        with open(filePath) as file:
            content = file.read()
            self.data = yaml.load(content, Loader=yaml.FullLoader)
            self.models = {}
            if self.data.has_key("components") and self.data["components"].has_key("schemas"):
                self.models = self.data["components"]["schemas"]
            self.dealModels()

    def getData(self):
        return self.data

    def getModels(self):
        return self.models

    def getListControl(self):
        return self.listControl

    # 判断引用路径是否为#/components/schemas/xxx的格式
    def isBackValid(self, comps):
        if not len(comps) == 4:
            return False
        return (comps[0] == "") and (comps[1] == "components") and (comps[2] == "schemas")

    def dealRelative(self, front):
        # 分解相对路径
        comps = front.split('/')
        parts = self.filePath.split('\\')
        # 调用pop移除当前文件名
        parts.pop()
        # 完整的文件路径
        allComps = parts + comps
        newComps = dealPath(allComps)
        newFilePath = '/'.join(newComps)
        return newFilePath

    def getProperties(self, objName):
        if not self.models.has_key(objName):
            print self.filePath + "不存在类型: " + objName
            sys.exit()
        # 对引用的结构的成员作递归处理
        elif self.models[objName].has_key("properties"):
            return self.dealProperties(self.models[objName]["properties"])
        else:
            return []

    # 添加结构名前缀
    def addObjectName(self, objName, subs):
        i = 0
        objName = objName[0].upper() + objName[1:]
        while i < len(subs):
            # autorest生成的字段名最多添加一次结构名前缀
            # 添加结构名时在字段头部添加'$'作为界定符
            # 如果添加前发现字段头部已存在'$'，则不再添加结构名前缀
            if not subs[i][0] == '$':
                subs[i] = subs[i][0].upper() + subs[i][1:]
                subs[i] = '$' + objName + subs[i]
            i += 1
        return subs

    def dealReference(self, ref, key):
        i = 0
        while i < len(ref):
            if ref[i] == '#':
                break
            i += 1
        if i == len(ref):
            print self.filePath + "引用路径配置错误: " + ref
            sys.exit()
        front = ref[0: i]
        back = ref[i + 1:]
        comps = back.split('/')
        if not self.isBackValid(comps):
            print self.filePath + "引用路径配置错误: " + ref
            sys.exit()
        # 引用的结构在当前文件中，即在self.models中
        if front == "":
            typeName = comps[-1]
            subs = self.getProperties(typeName)
            return self.addObjectName(key, subs)
        else:
            typeName = comps[-1]
            newFilePath = self.dealRelative(front)
            g = Generator(newFilePath)
            subs = g.getProperties(typeName)
            return self.addObjectName(key, subs)

    def dealProperties(self, properties):
        res = []
        for key, value in properties.items():
            # 如果没有x-ListControl标签，则跳过
            if not value.has_key("x-ListControl"):
                continue
            # 如果有x-ListControl标签，但为false，则跳过
            if value["x-ListControl"] == "false":
                continue
            # 对引用字段进行处理
            if value.has_key("$ref"):
                ref = value["$ref"]
                subs = self.dealReference(ref, key)
                if subs:
                    for sub in subs:
                        res.append(sub)
                # 如果引用的结构返回空数组，则作为非结构类型处理
                else:
                    res.append(key)
            # 除去上方所有情况，将字段名插入返回结果中
            else:
                res.append(key)
        return res

    def dealModels(self):
        self.listControl = {}
        if not self.models:
            return
        # schemas值被解析为一个字典，每个键对应一个结构名称
        for key in self.models.keys():
            name = modelPrefix + key
            res = []
            if not self.models[key].has_key("properties"):
                continue
            # 处理结构中的所有成员
            properties = self.models[key]["properties"]
            res = self.dealProperties(properties)
            # 去除'$'界定符
            i = 0
            while i < len(res):
                if res[i][0] == '$':
                    res[i] = res[i][1:]
                i += 1
            self.listControl[name] = res

def genps1xml(listControls, outputDir):

    for data in listControls:
        for key, value in data.items():
            if value == []:
                continue
            
            # # 按字符串长度由小到大排序
            # value.sort(key=lambda str: len(str))

            ps1xml = minidom.Document()

            configuration = ps1xml.createElement("Configuration")
            ps1xml.appendChild(configuration)

            viewDefinitions = ps1xml.createElement("ViewDefinitions")
            configuration.appendChild(viewDefinitions)

            view = ps1xml.createElement("View")

            name = ps1xml.createElement("Name")
            name.appendChild(ps1xml.createTextNode(key))
            view.appendChild(name)

            viewSelectedBy = ps1xml.createElement("ViewSelectedBy")
            typeName = ps1xml.createElement("TypeName")
            typeName.appendChild(ps1xml.createTextNode(key))
            viewSelectedBy.appendChild(typeName)
            view.appendChild(viewSelectedBy)

            listControl = ps1xml.createElement("ListControl")
            listEntries = ps1xml.createElement("ListEntries")
            listEntry = ps1xml.createElement("ListEntry")
            listItems = ps1xml.createElement("ListItems")
            listEntry.appendChild(listItems)
            listEntries.appendChild(listEntry)
            listControl.appendChild(listEntries)

            for ele in value:
                listItem = ps1xml.createElement("ListItem")
                propertyName = ps1xml.createElement("PropertyName")
                propertyName.appendChild(ps1xml.createTextNode(ele))
                listItem.appendChild(propertyName)

                listItems.appendChild(listItem)
            
            view.appendChild(listControl)
            viewDefinitions.appendChild(view)

            f = open(outputDir + key + '.Format.ps1xml', 'w')
            ps1xml.writexml(f, indent='', addindent='  ', newl='\n', encoding='utf-8')
            f.close()

def main(argv):
    basePath = ""
    outputDir = ""
    try:
        opts, _ = getopt.getopt(argv, "hb:o:", ["basepath=", "outpath="])
    except getopt.GetoptError:
        print "gen-ps1xml.py -b <basepath> -o <outpath>"
        sys.exit()
    for opt, arg in opts:
        if opt == '-h':
            print "gen-ps1xml.py -b <basepath> -o <outpath>"
            sys.exit()
        elif opt in ("-b", "--basepath"):
            basePath = arg
        elif opt in ("-o", "--outpath"):
            outputDir = arg
    fileList = os.listdir(basePath)
    listControls = []
    for fileName in fileList:
        g = Generator(basePath + fileName)
        listControl = g.getListControl()
        listControls.append(listControl)
    genps1xml(listControls, outputDir)

if __name__ == "__main__":
    main(sys.argv[1:])