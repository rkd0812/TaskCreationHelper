"""
This module is used to define and support I/O data (for problems) related stuffs.
"""

# Standard libraries
import typing
import os
from pathlib import Path
from decimal import Decimal
from fractions import Fraction

# Azad libraries
from .constants import (
    DefaultFloatPrecision,
    IODataTypesInfo, DefaultTypeStrings,
    MaxParameterDimensionAllowed,
    PrimitiveDataProtocolTargetTypes,
)
from .errors import FailedDataValidation


def cleanIOFilePath(path: typing.Union[str, Path],
                    targetExtensions: typing.Tuple[str] = ("in", "out", "txt")):
    """
    Remove all files with given extension in given path.
    """
    if isinstance(path, str):
        path = Path(path)
    for filename in path.iterdir():
        for extension in targetExtensions:
            if filename.name.endswith(extension):
                os.remove(filename)
                break


def PGizeData(data, typestr: str) -> str:
    """
    Transfer data into Programmers-compatible string.
    """
    if isinstance(data, (list, tuple)):
        return "[%s]" % (",".join(PGizeData(d, typestr) for d in data),)
    else:
        return IODataTypesInfo[typestr]["strize"](data)


def checkPrecision(a: float, b: float,
                   precision: float = DefaultFloatPrecision):
    """
    Check similarity between two float numbers with given precision.
    """
    if precision <= 0:
        raise ValueError("Non-positive precision %f given" % (precision,))
    elif abs(a) <= 1e-10:
        return abs(a - b) <= precision
    else:
        return abs(a - b) <= precision or abs((a - b) / a) <= precision


def checkDataCompatibility(data, targetType: typing.Union[str, type]) -> bool:
    """
    Check data compatibilities.
    For integers, it should be in range of int32 or int64.
    For real numbers, it should be in range of IEEE float/double standard.
    For string, it should not contain any wide characters(wchar_t).
    """
    # Check each element's data range
    if isinstance(data, (list, tuple)):
        for element in data:
            if not checkDataCompatibility(element, targetType):
                return False
        return True

    # Clean datatype
    elif isinstance(targetType, type):  # Types should be converted to typestr
        targetType = DefaultTypeStrings[targetType]
    elif not isinstance(targetType, str):
        raise TypeError

    # Filtering unknown target type
    if targetType not in IODataTypesInfo:
        raise ValueError("Given target type '%s' is unknown" % (targetType,))
    # Given data is not matching to target type
    elif not isinstance(data, IODataTypesInfo[targetType]["pytypes"]):
        raise TypeError("Data type is %s but wanted to match %s(%s)" %
                        (type(data), targetType, IODataTypesInfo[targetType]["pytypes"]))
    # Check constraints
    elif "constraint" in IODataTypesInfo[targetType]:
        return IODataTypesInfo[targetType]["constraint"](data)
    else:
        return True


def checkDataType(data, variableType: typing.Union[str, type, typing.List[type]],
                  dimension: int) -> bool:
    """
    Check data type and dimension. Return true if given data is valid.
    """
    if isinstance(variableType, str):  # Auto conversion
        variableType = IODataTypesInfo[variableType]["pytypes"]
    if dimension == 0:
        return isinstance(data, variableType)
    elif not isinstance(data, (list, tuple)):
        return False
    for element in data:
        if not checkDataType(element, variableType, dimension - 1):
            return False
    return True


def compareAnswers(*answers, floatPrecision: float = DefaultFloatPrecision):
    """
    Compare answers and return boolean value.
    Don't confuse, this function validates `(answer[1] == answer[2] == ... == answer[n])`.
    Consider first answer argument as main answer.
    """
    l = len(answers)
    if l < 2:
        raise ValueError("%d answer given to be compared. (Too small)" % (l,))

    # Dimension 1+
    if isinstance(answers[0], (list, tuple)):  # Iterable
        for i in range(l):
            if not isinstance(answers[i], (list, tuple)) or \
                    len(answers[0]) != len(answers[i]):
                return False
        for i in range(len(answers[0])):
            if not compareAnswers(*[answer[i] for answer in answers]):
                return False
        return True

    # Dimension 0
    else:
        for i in range(1, l):  # Type checking
            if not isinstance(answers[i], type(answers[0])):
                return False
        if isinstance(answers[0],
                      (float, Decimal, Fraction)):  # Float: Precision checking
            for i in range(1, l):
                if not checkPrecision(
                        answers[0], answers[i], floatPrecision):
                    return False
        elif isinstance(answers[0], (int, bool, str)):  # General cases
            for i in range(1, l):
                if answers[0] != answers[i]:
                    return False
        else:
            raise TypeError("Invalid answer type.")
        return True


def guessDataType(
    data: typing.Union[int, float, str, list, tuple],
    dimension: int = None, validateConstraints: bool = False) \
        -> typing.Tuple[str, int]:
    """
    Guess the object's datatype.
    If result is ambigious, then the lowest possible dimension
    and arbitrary possible type will be chosen.
    If there isn't any correct type and dimension, it will raise FailedDataValidation.
    """
    for dimension in (range(MaxParameterDimensionAllowed + 1)
                      if dimension is None else [dimension]):
        for varType in IODataTypesInfo:
            if checkDataType(data, varType[::], dimension):
                if not validateConstraints or \
                        checkDataCompatibility(data, varType[::]):
                    return (varType, dimension)
    else:
        raise FailedDataValidation(
            "None of (type, dimension) could validate it.")


def sendingPrimitiveDataProtocol(
        data: PrimitiveDataProtocolTargetTypes, identifier=None):
    """
    Generate list of object needed to send by 'Primitive Protocol'.
    This protocol supports primitive data type only.
    """

    if isinstance(data, dict):
        yield {"type": dict, "len": len(data), "id": identifier}
        for key in data:  # Yield key and value consecutively
            yield from sendingPrimitiveDataProtocol(key)
            yield from sendingPrimitiveDataProtocol(data[key])
    elif isinstance(data, (list, tuple, set, frozenset)):
        yield {"type": list, "len": len(data), "id": identifier}
        for element in data:  # Yield by indices
            yield from sendingPrimitiveDataProtocol(element)
    elif isinstance(data, (str, bytes, bytearray)):  # Yield each atomic unit
        yield {"type": type(data), "len": len(data), "id": identifier}
        yield from data
    elif isinstance(data, (int, float, bool)) or data is None:
        yield data
    else:
        raise TypeError("Invalid type %s found" % (type(data),))


def receiveByPrimitiveDataProtocol(iterable: typing.Iterable, checkEnd: bool = False) \
        -> PrimitiveDataProtocolTargetTypes:
    """
    Receive object from iterable by 'Primitive Protocol' with safety guards.
    """

    # Checking end
    if checkEnd:
        result = receiveByPrimitiveDataProtocol(iterable)
        try:
            extraValue = next(iterable)
        except StopIteration:
            return result
        else:
            raise Exception(
                "There is an unexpected additional space on iterable")

    # Get head
    iterator = iter(iterable)
    head = next(iterator)

    # Iterable coming
    if isinstance(head, dict):
        varType = head["type"]
        length = head["len"]

        # Guard bad data
        if not isinstance(varType, type):
            raise TypeError(
                "Non-type object (type %s) given as head.type" % (type(varType),))
        elif not isinstance(length, int):
            raise TypeError(
                "Non-int object (type %s) given as head.len" % (type(length),))
        elif not (0 <= length):
            raise ValueError("Negative length %d given" % (length,))

        # Case handling
        if varType is dict:
            data = {}
            for i in range(length):
                # Python 3.7- / 3.8+ have different order of key/value expr evaluation,
                # so I don't use dict comprehension here.
                key = receiveByPrimitiveDataProtocol(iterator)
                value = receiveByPrimitiveDataProtocol(iterator)
                data[key] = value
        elif varType in (list, tuple):
            data = [receiveByPrimitiveDataProtocol(iterator)
                    for i in range(length)]
        elif varType in (set, frozenset):
            data = varType(receiveByPrimitiveDataProtocol(iterator)
                           for i in range(length))
        elif varType is str:
            data = "".join(next(iterator) for i in range(length))
        elif varType is bytes:
            data = b''.join(next(iterator) for i in range(length))
        elif varType is bytearray:
            data = bytearray(next(iterator) for i in range(length))
        else:
            raise TypeError("Unsupported type %s given" % (varType,))
        return data

    # Literal
    elif isinstance(head, (int, float, bool)) or head is None:
        return head
    else:
        raise TypeError("Unsupported data type %s returned" % (type(head),))
