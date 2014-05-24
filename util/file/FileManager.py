import os
import os.path as path
import gzip
import shutil as sh

def delete_files_from_dir(dir_path, prefix_=''):
# Gather directory contents
    contents = [os.path.join(dir_path, i) for i in os.listdir(dir_path)]
    # Iterate and remove each item in the appropriate manner
    [os.unlink(i) for i in contents if i.startswith(prefix_)]


def exists(pathname, isDir=False):
    return path.exists(pathname) and (path.isdir(pathname) if isDir else path.isfile(pathname))


def createDir(pathname, recreate=False, prefix_=''):
    if not path.exists(pathname):
        os.makedirs(pathname)
    elif recreate:
        delete_files_from_dir(pathname, prefix_)

def fileName(pathname):
    return path.basename(pathname)

def copy(file_, to_dir):
    sh.copy(file_, to_dir)

class FileManager:
    
    def __init__(self, filePath, mode = 'r'):
        if (filePath.endswith('.gz')):
            self.__fh = gzip.open(filePath)
        else:
            self.__fh = open(filePath,mode)
        
    def getFileObject(self):
        return self.__fh
    
    def readFile(self, bytes=0, nrOfLines=0):
        
        if bytes!=0:
            return self.__fh.readlines(bytes)
        elif nrOfLines!=0:
            lines = []
            for i in range(0,nrOfLines):
                currentLine =self.__fh.readline()
                if currentLine == '':
                    continue
                elif currentLine == '\n' or currentLine == '\r\n':
                    break
                else:
                    lines.append(currentLine)
            return lines
        else:
            self.__fh.seek(0)
            return self.__fh.readlines()
    
    def close(self):
        self.__fh.close()
    
    def readLine(self):
        return self.__fh.readline()

    def writeLine(self, line):
        return self.__fh.writelines(line)
    

    def getFilename(self):
        return self.__fh.name

    def writeFile(self, lines, type='dict', separator='', endLine = '\n'):
        if type == 'array':
            #write a string representations of an array
            linesOut = self.__writeArray(lines, endLine)
           
        elif type=='flat':
            #write lines
            linesOut = lines

        elif type=='obj':
            #write a string representations of an array of objects
            linesOut = self.__writeObjects(lines, endLine)

        elif type=='dict':
            #write a string representations of an array of dictionaries
            #print "writing file from array of dict..."
            linesOut = self.__writeDict(lines, separator)
        elif type=='tuple':
            #write a string representations of an array of tuples (e.g. records from a database)
            linesOut = self.__writeTuples(lines)

        self.__fh.writelines(linesOut)
        self.__fh.flush()
        #print "file wrote"

    def __writeArray(self, items, endLine='\n'):

        linesOut = ''
        for item in items:
            linesOut += str(item)+endLine
        return linesOut

    def __writeObjects(self, items, endLine='\n'):
        #the objects to write MUST have the method getStringHeader() implemented which returns an header with fields' names.
        linesOut = items[0].getStringHeader()
        for item in items:
            linesOut += str(item)+endLine
        return linesOut

    def __writeDict(self, items, separator,endLine='\n'):
        #write an array of dictionaries
        if separator!='':
            keyys = items[0].keys()
            keyys.sort()
            linesOut = ''
            separatorTemp = separator
            k = 0
            for key in keyys:
                if k == len(keyys)-1:
                    separatorTemp=''
                linesOut += key+ separatorTemp
                k += 1

            linesOut +=endLine+endLine

            for i in range(0, len(items)):
                separatorTemp = separator
                k = 0
                for key in keyys:
                    if k == len(keyys)-1:
                        separatorTemp=''
                    linesOut +=str(items[i][key])+separatorTemp
                    k += 1
                linesOut+=endLine

        else:
            maxLength = 0
            for i in range(0,len(items)):
                maxTemp = len(str(items[i][max(items[i], key=lambda x: len(str(items[i].get(x))))]))
                if maxTemp>maxLength:
                    maxLength = maxTemp
            spacing = maxLength + 2

            keyys = items[0].keys()
            keyys.sort()
            linesOut = ''
            for key in keyys:
                linesOut += key.ljust(spacing)#+ '\t'
            linesOut += "\n\n"

            for i in range(0, len(items)):
                for key in keyys:
                    linesOut +=str(items[i][key]).ljust(spacing)#+ '\t'
                linesOut += "\n"

        return linesOut

    def __writeTuples(self, tuples, separator="\t", endLine = "\n"):
        linesOut=''
        numberOfLines = len(tuples)
        if numberOfLines>0:
            lengthOfTuple = len(tuples[0])
            #print "tuple length: "+str(lengthOfTuple)
        else:
            return linesOut

        for t in tuples:
            line = ''
            #print "writing "+str(t)
            for i in range(0,lengthOfTuple-1):
                line+=str(t[i])+separator
            line+=str(t[lengthOfTuple-1])+endLine
            linesOut+=line
        return linesOut
