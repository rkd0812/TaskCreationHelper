"""
This module provides implementation of C++ external module.
"""

# Standard libraries
import typing
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Azad libraries
from .. import constants as Const
from ..misc import isExistingFile, removeExtension
from ..errors import AzadError
from .abstract import (
    AbstractProgrammingLanguage, AbstractExternalGenerator,
    AbstractExternalValidator, AbstractExternalSolution)


class AbstractCpp(AbstractProgrammingLanguage):
    """
    C++ specification of abstract programming language.
    """

    baseTypeStrTable = {
        Const.IOVariableTypes.INT: "int",
        Const.IOVariableTypes.LONG: "long long int",
        Const.IOVariableTypes.FLOAT: "float",
        Const.IOVariableTypes.DOUBLE: "double",
        Const.IOVariableTypes.BOOL: "bool",
        Const.IOVariableTypes.STRING: "std::string"
    }

    @classmethod
    def typeStr(cls, iovt: Const.IOVariableTypes, dimension: int):
        return cls.baseTypeStrTable[iovt] if dimension == 0 else \
            "std::vector<%s>" % cls.typeStr(iovt, dimension - 1)

    # Template file path
    generatorTemplatePath = Const.ResourcesPath / \
        "templates/generator_cpp.template"
    solutionTemplatePath = Const.ResourcesPath / \
        "templates/solution_cpp.template"
    validatorTemplatePath = Const.ResourcesPath / \
        "templates/validator_cpp.template"
    generatorHeaderTemplatePath = Const.ResourcesPath / \
        "templates/generator_cpp_header.template"
    solutionHeaderTemplatePath = Const.ResourcesPath / \
        "templates/solution_cpp_header.template"
    validatorHeaderTemplatePath = Const.ResourcesPath / \
        "templates/validator_cpp_header.template"
    helperHeadersPath = Const.ResourcesPath / "helpers"

    # Indent level
    indentLevelParameterInit = 1
    indentLevelParameterGet = 2
    indentLevelParameterPrint = 2

    # Converted variable name on C++ code
    vnameByPname = (lambda name: "_param_%s" % (name,))

    @classmethod
    def templateDict(
            cls, *args, parameterInfo: typing.List[typing.Tuple[
                str, Const.IOVariableTypes, int]] = (),
            generatorHeaderPath: Path = None,
            solutionHeaderPath: Path = None,
            validatorHeaderPath: Path = None,
            returnInfo: Const.ReturnInfoType = None,
            **kwargs) -> dict:

        # Language-common state
        result = super().templateDict(**kwargs)

        # Parameter arguments (for all modules)
        result["ParameterArgs"] = ", ".join(
            "%s %s" % (cls.typeStr(pType, dimension), pName)
            for pName, pType, dimension in parameterInfo)
        result["ParameterArgsRef"] = ", ".join(
            "%s &%s" % (cls.typeStr(pType, dimension), pName)
            for pName, pType, dimension in parameterInfo)
        result["SendParameters"] = ", ".join(
            cls.vnameByPname(pName) for pName, _1, _2 in parameterInfo)

        # Init all parameters (for all modules)
        result["InitParameters"] = cls.leveledNewline(cls.indentLevelParameterInit).join(
            cls.generateCodeInitParameter(*param) for param in parameterInfo)

        # Get all parameters (for validators and solutions)
        result["GetParameters"] = cls.leveledNewline(cls.indentLevelParameterGet).join(
            cls.generateCodeGetParameter(*param) for param in parameterInfo)

        # Print all parameters (for generators)
        result["PrintParameters"] = cls.leveledNewline(cls.indentLevelParameterPrint).join(
            cls.generateCodePutParameter(*param) for param in parameterInfo)

        # Result info
        if returnInfo:
            returnType, returnDimension = returnInfo
            result["ReturnType"] = cls.typeStr(returnType, returnDimension)
            result["ReturnDimension"] = returnDimension
            result["ReturnTypeBase"] = cls.typeStr(returnType, 0)

        def registerPath(key: str, path: Path):
            if path:
                if not isExistingFile(path):
                    raise OSError(
                        "Given path(key = %s, path = %s) isn't existing file" %
                        (key, path))
                result[key] = path.name  # Should not remove extension

        # Set paths
        registerPath("GeneratorHeaderPath", generatorHeaderPath)
        registerPath("SolutionHeaderPath", solutionHeaderPath)
        registerPath("ValidatorHeaderPath", validatorHeaderPath)

        # Return
        return result

    @classmethod
    def generateCodeInitParameter(
            cls, variableName: int,
            parameterType: Const.IOVariableTypes,
            parameterDimension: int) -> str:
        return "%s %s;" % \
            (cls.typeStr(parameterType, parameterDimension),
             cls.vnameByPname(variableName))

    @classmethod
    def generateCodeGetParameter(
            cls, variableName: int,
            parameterType: Const.IOVariableTypes,
            parameterDimension: int) -> str:
        return "%s = TCH::Data<%s, %d>::get(std::cin);" % \
            (cls.vnameByPname(variableName),
             cls.typeStr(parameterType, 0),
             parameterDimension)

    @classmethod
    def generateCodePutParameter(
            cls, variableName: int,
            parameterType: Const.IOVariableTypes,
            parameterDimension: int) -> str:
        """
        Return statement `TCHIO.print(varName);`.
        """
        return "TCH::Data<%s, %d>::put(outfile, %s);" % \
            (cls.typeStr(parameterType, 0),
             parameterDimension,
             cls.vnameByPname(variableName))


class CppGenerator(AbstractExternalGenerator, AbstractCpp):
    """
    C++ implementation of external generator module.
    `generateExecutionArgs` is not overrided, because in C++
    we invokes executable created by compilation.

    - argv: `[executable, *super().argv]`
    """

    @classmethod
    def generateCompilationArgs(
            cls, mainModulePath: Path, executable: Path,
            originalModulePath: Path, *args, **kwargs) -> Const.ArgType:
        return [
            "g++", "-Wall", "-std=c++17", "-O2",
            "-I", cls.helperHeadersPath,
            mainModulePath, originalModulePath,
            "-o", executable
        ]

    @classmethod
    def generateCode(
            cls, generatorPath: Path, parameterInfo: Const.ParamInfoList,
            *args, **kwargs) -> str:
        """
        Consider `generatorPath` as `generatorHeaderPath`.
        """
        return cls.replaceSymbols(
            cls.generatorTemplatePath, cls.templateDict(
                parameterInfo=parameterInfo,
                generatorHeaderPath=generatorPath)
        )

    def preparePipeline(self):

        # Prepare original stuffs
        originalModuleHeaderCode = self.replaceSymbols(
            self.generatorHeaderTemplatePath,
            self.templateDict(parameterInfo=self.parameterInfo)
        )
        originalModuleHeaderPath = self.fs.newTempFile(
            content=originalModuleHeaderCode,
            filename=removeExtension(self.originalModulePath.name),
            extension="hpp"
        )
        code = self.generateCode(originalModuleHeaderPath, self.parameterInfo)
        self.modulePath = self.fs.newTempFile(
            content=code, extension="cpp", namePrefix="generator")

        # Compile
        self.executable = self.fs.newTempFile(
            extension="exe", namePrefix="generator")
        compilationArgs = self.generateCompilationArgs(
            self.modulePath, self.executable, self.originalModulePath)
        compilationErrorLog = self.fs.newTempFile(
            extension="log", namePrefix="err")
        compilationExitCode = self.invoke(
            compilationArgs, stderr=compilationErrorLog,
            cwd=self.fs.basePath)
        if compilationExitCode is not Const.ExitCode.Success:
            with open(compilationErrorLog, "r") as errLogFile:
                logger.error("Generator '%s' compilation failed (args = %s), log:\n%s",
                             self.originalModulePath, compilationArgs,
                             errLogFile.read())
            raise AzadError(
                "Compilation failed (args = %s)" % (compilationArgs,))

        self.prepared = True


class CppValidator(AbstractExternalValidator, AbstractCpp):
    """
    C++ implementation of external validator module.
    `generateExecutionArgs` is not overrided, because in C++
    we invokes executable created by compilation.

    - argv: `[executable, *super().argv]`
    """

    @classmethod
    def generateCompilationArgs(
            cls, mainModulePath: Path, executable: Path,
            originalModulePath: Path, *args, **kwargs) -> Const.ArgType:
        return [
            "g++", "-Wall", "-std=c++17", "-O2",
            "-I", cls.helperHeadersPath,
            mainModulePath, originalModulePath,
            "-o", executable
        ]

    @classmethod
    def generateCode(
            cls, validatorPath: Path, parameterInfo: Const.ParamInfoList,
            returnInfo: Const.ReturnInfoType,
            *args, **kwargs) -> str:
        """
        Consider `validatorPath` as `validatorHeaderPath`.
        """
        return cls.replaceSymbols(
            cls.validatorTemplatePath, cls.templateDict(
                parameterInfo=parameterInfo,
                validatorHeaderPath=validatorPath,
                returnInfo=returnInfo)
        )

    def preparePipeline(self):

        # Prepare original stuffs
        originalModuleHeaderCode = self.replaceSymbols(
            self.validatorHeaderTemplatePath,
            self.templateDict(parameterInfo=self.parameterInfo)
        )
        originalModuleHeaderPath = self.fs.newTempFile(
            content=originalModuleHeaderCode,
            filename=removeExtension(self.originalModulePath.name),
            extension="hpp"
        )
        code = self.generateCode(
            originalModuleHeaderPath,
            self.parameterInfo, self.returnInfo)
        self.modulePath = self.fs.newTempFile(
            content=code, extension="cpp", namePrefix="validator")

        # Compile
        self.executable = self.fs.newTempFile(
            extension="exe", namePrefix="validator")
        compilationArgs = self.generateCompilationArgs(
            self.modulePath, self.executable, self.originalModulePath)
        compilationErrorLog = self.fs.newTempFile(
            extension="log", namePrefix="err")
        compilationExitCode = self.invoke(
            compilationArgs, stderr=compilationErrorLog,
            cwd=self.fs.basePath)
        if compilationExitCode is not Const.ExitCode.Success:
            with open(compilationErrorLog, "r") as errLogFile:
                logger.error("Validator '%s' compilation failed (args = %s), log:\n%s",
                             self.originalModulePath, compilationArgs,
                             errLogFile.read())
            raise AzadError(
                "Compilation failed (args = %s)" % (compilationArgs,))

        self.prepared = True


class CppSolution(AbstractExternalSolution, AbstractCpp):
    """
    C++ implementation of external solution module.
    `generateExecutionArgs` is not overrided, because in C++
    we invokes executable created by compilation.

    - argv: `[executable, *super().argv]`
    """

    @classmethod
    def generateCompilationArgs(
            cls, mainModulePath: Path, executable: Path,
            originalModulePath: Path, *args, **kwargs) -> Const.ArgType:
        return [
            "g++", "-Wall", "-std=c++17", "-O2",
            "-I", cls.helperHeadersPath,
            mainModulePath, originalModulePath,
            "-o", executable
        ]

    @classmethod
    def generateCode(
            cls, solutionPath: Path, parameterInfo: Const.ParamInfoList,
            returnInfo: Const.ReturnInfoType,
            *args, **kwargs) -> str:
        """
        Consider `solutionPath` as `solutionHeaderPath`.
        """
        return cls.replaceSymbols(
            cls.solutionTemplatePath, cls.templateDict(
                parameterInfo=parameterInfo,
                solutionHeaderPath=solutionPath,
                returnInfo=returnInfo)
        )

    def preparePipeline(self):

        # Prepare original stuffs
        originalModuleHeaderCode = self.replaceSymbols(
            self.solutionHeaderTemplatePath,
            self.templateDict(
                parameterInfo=self.parameterInfo,
                returnInfo=self.returnInfo)
        )
        originalModuleHeaderPath = self.fs.newTempFile(
            content=originalModuleHeaderCode,
            filename=removeExtension(self.originalModulePath.name),
            extension="hpp"
        )
        code = self.generateCode(
            originalModuleHeaderPath,
            self.parameterInfo, self.returnInfo)
        self.modulePath = self.fs.newTempFile(
            content=code, extension="cpp", namePrefix="solution")

        # Compile
        self.executable = self.fs.newTempFile(
            extension="exe", namePrefix="solution")
        compilationArgs = self.generateCompilationArgs(
            self.modulePath, self.executable,
            self.originalModulePath, originalModuleHeaderPath)
        compilationErrorLog = self.fs.newTempFile(
            extension="log", namePrefix="err")
        compilationExitCode = self.invoke(
            compilationArgs, stderr=compilationErrorLog,
            cwd=self.fs.basePath)
        if compilationExitCode is not Const.ExitCode.Success:
            with open(compilationErrorLog, "r") as errLogFile:
                logger.error("Solution '%s' compilation failed (args = %s), log:\n%s",
                             self.originalModulePath, compilationArgs,
                             errLogFile.read())
            raise AzadError("Compilation failed (args = %s)" %
                            (compilationArgs,))

        self.prepared = True
