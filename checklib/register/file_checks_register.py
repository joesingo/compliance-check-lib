"""
file_checks_register.py
=======================

A register of checks at the file-level.

"""

import os, re
import numbers

from compliance_checker.base import Result, Dataset, GenericFile

from .parameterisable_check_base import ParameterisableCheckBase

from checklib.code import file_util

class FileCheckBase(ParameterisableCheckBase):
    "Base class for all File Checks (that work on a file path)."

    supported_ds = [Dataset, GenericFile]

    def _check_primary_arg(self, primary_arg):
        fpath = primary_arg.filepath()
        if not os.path.isfile(fpath):
            raise Exception("File not found: {}".format(fpath))


class FileSizeCheck(FileCheckBase):
    """
    Data file {strictness} size limit: {threshold}Gbytes.
    """
    short_name = "File size {strictness} limit {threshold}Gbytes"
    defaults = {"threshold": 2, "strictness": "hard"}
    message_templates = ["Data file exceeds {strictness} limit of {threshold}Gbytes in size."]
    level = "HIGH"
    required_parameters = {"threshold": numbers.Number, "strictness": str}

    def _get_result(self, primary_arg):
        fpath = primary_arg.filepath()
        threshold = float(self.kwargs["threshold"])

        success = file_util._is_file_size_less_than(fpath, threshold * (2.**30))
        messages = []

        if success:
            score = self.out_of
        else:
            score = 0
            messages.append(self.get_messages()[score])

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)


class FileNameStructureCheck(FileCheckBase):
    """
    File name must consist of items separated by '{delimiter}', followed by '{extension}'.
    """

    short_name = "File name structure"
    defaults = {"delimiter": "_", "extension": ".nc"}
    message_templates = [
        "File name does not follow required format of '{delimiter}' delimiters and '{extension}' extension."]
    level = "HIGH"
    _ALLOWED_CHARACTERS = '[A-Za-z0-9\-\.]'
    required_parameters = {"delimiter": str, "extension": str}

    def _get_result(self, primary_arg):
        fpath = os.path.basename(primary_arg.filepath())
        self.kwargs["AC"] = self._ALLOWED_CHARACTERS
        regex = re.compile("{AC}+({delimiter}{AC}+)+\{extension}".format(**self.kwargs))

        success = regex.match(fpath)
        messages = []

        if success:
            score = self.out_of
        else:
            score = 0
            messages.append(self.get_messages()[score])

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)


class FileNameRegexCheck(FileCheckBase):
    """
    File name must match regex '{regex}'
    """
    short_name = "File name regex check"
    message_templates = ["File name did not match regex '{regex}'"]
    required_parameters = {"regex": str}

    def _setup(self):
        """
        Fix backslashes in regex
        """
        self.kwargs["regex"] = self.kwargs["regex"].replace("\\\\", "\\")

    def _get_result(self, primary_arg):
        fpath = os.path.basename(primary_arg.filepath())
        messages = []
        if re.match(self.kwargs["regex"], fpath):
            score = self.out_of
        else:
            print("Failed to match {} against regex {}".format(fpath, self.kwargs["regex"]))
            score = 0
            messages.append(self.get_messages()[score])
        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)

