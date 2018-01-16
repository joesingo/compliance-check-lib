"""
nc_file_checks_register.py
==========================

A register of checks for NetCDF4 files.

"""

import os
from netCDF4 import Dataset

from compliance_checker.base import Result

from .parameterisable_check_base import ParameterisableCheckBase
from checklib.code import nc_util
from checklib.cvs.ess_vocabs import ESSVocabs
from checklib.code.errors import FileError


class NCFileCheckBase(ParameterisableCheckBase):
    "Base class for all NetCDF4 File Checks (that work on a file path."

    supported_ds = [Dataset]

    def _check_primary_arg(self, primary_arg):
        if not isinstance(primary_arg, Dataset):
            raise FileError("Object for testing is not a netCDF4 Dataset: {}".format(str(primary_arg)))


class GlobalAttrRegexCheck(NCFileCheckBase):
    """
    The global attribute '{attribute}' must exist and have a valid format matching regular expression: ('{regex}').
    """
    short_name = "Global attribute: {attribute}"
    defaults = {}
    message_templates = ["Required '{attribute}' global attribute is not present.",
                         "Required '{attribute}' global attribute value is invalid."]
    level = "HIGH"
    required_parameters = {"attribute": str, "regex": str}

    def _setup(self):
        "Fixes double-escape in regex string"
        self.kwargs["regex"] = self.kwargs["regex"].replace("\\\\", "\\")

    def _get_result(self, primary_arg):
        ds = primary_arg

        score = nc_util.check_global_attr_against_regex(ds, self.kwargs["attribute"], self.kwargs["regex"])
        messages = []

        if score < self.out_of:
            messages.append(self.get_messages()[score])

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)


class GlobalAttrVocabCheck(NCFileCheckBase):
    """
    The global attribute '{attribute}' must exist and have a valid value from the relevant vocabulary.
    """
    short_name = "Global attribute: {attribute}"
    defaults = {"vocab_lookup": "canonical_name"}
    message_templates = ["Required '{attribute}' global attribute is not present.",
                         "Required '{attribute}' global attribute value is invalid."]
    level = "HIGH"
    required_parameters = {"attribute": str}

    def _get_result(self, primary_arg):
        ds = primary_arg
        vocabs = ESSVocabs(*self.vocabulary_ref.split(":")[:2])

        score = vocabs.check_global_attribute(ds, self.kwargs["attribute"], property=self.kwargs["vocab_lookup"])
        messages = []

        if score < self.out_of:
            messages.append(self.get_messages()[score])

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)


class OneMainVariablePerFileCheck(NCFileCheckBase):
    """
    Only 1 main variable must be written to each NetCDF file (except ancillary and coordinate
    variables that are required to understand the main variable).
    """
    short_name = "One main variable only"
    defaults = {}
    message_templates = ["More than 1 main variable found in the file. Only 1 main variable should be there."]
    level = "HIGH"

    def _get_result(self, primary_arg):
        ds = primary_arg

        success = nc_util.is_there_only_one_main_variable(ds)
        messages = []

        if success:
            score = self.out_of
        else:
            score = 0
            messages.append(self.get_messages()[score])

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)



class ValidGlobalAttrsMatchFileNameCheck(NCFileCheckBase):
    """
    All components in the file name must either be set as global attributes in
    the NetCDF file and must be valid terms in the relevant controlled
    vocabulary, or match the given regular expression(s)
    """
    short_name = "Global attributes match file name/vocab"
    defaults = {"delimiter": "_", "extension": ".nc"}
    message_templates = ["File name does not match global attributes.",
                         "Each global attribute is checked separately."]
    level = "HIGH"
    required_parameters = {"delimiter": str, "extension": str, "order": str}

    def _setup(self):
        """
        Uses the instructions given about the order of the file name components
        to work out the 'out of' value for the result.

        The delimiter is used to split up the file name.

        The extension is the extension of the file name.

        The order should include the list of facets or regex to check the
        components of the file name against. Regex should start with
        'regex:' followed by the regex.
        """
        self.kwargs["order"] = self.kwargs["order"].split("~")
        self.out_of = 0
        for order in self.kwargs["order"]:
            if order.startswith('regex:'):
                self.out_of += 1
            else:
                self.out_of += 3

    def _get_result(self, primary_arg):
        ds = primary_arg

        score = 0
        messages = []

        vocabs = ESSVocabs(*self.vocabulary_ref.split(":")[:2])
        fname = os.path.basename(ds.filepath())
        fn_score, msg = vocabs.check_file_name(fname, keys=self.kwargs["order"],
                                               delimiter=self.kwargs["delimiter"],
                                               extension=self.kwargs["extension"])
        score += fn_score
        if fn_score < self.out_of / 3:
            # a third of the marks are for the file name check
            messages.extend(msg)

        # Check global attributes one-by-one
        items = os.path.splitext(fname)[0].split(self.kwargs["delimiter"])

        for i, attr in enumerate(self.kwargs["order"]):
            if attr.startswith('regex:'):
                # we do not have the attribute name, so cannot look for it in
                # the file
                continue
            res, msg = vocabs.check_global_attribute_value(ds, attr, items[i],
                                                           property="canonical_name")
            score += res

            if res < 2:
                messages.extend(msg)

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)


class VariableExistsInFileCheck(NCFileCheckBase):
    """
    Variable {var_id} exists in NetCDF file.
    """
    short_name = "Variable exists: {var_id}"
    defaults = {}
    message_templates = ["Required variable {var_id} is not present."]
    level = "HIGH"
    required_parameters = {"var_id": str}

    def _get_result(self, primary_arg):
        ds = primary_arg

        score = 0
        if nc_util.is_variable_in_dataset(ds, self.kwargs["var_id"]):
            score = 1

        messages = []

        if score < self.out_of:
            messages.append(self.get_messages()[score])

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)


class VariableRangeCheck(NCFileCheckBase):
    """
    The variable {var_id} must have values in the range {minimum}
    to {maximum}.
    """
    short_name = "Variable range {var_id}: {minimum} to {maximum}"
    defaults = {}
    message_templates = ["Variable {var_id} does not exist.",
                         "Variable {var_id} has values outside the permitted range: "
                         "{minimum} to {maximum}"]
    level = "HIGH"
    required_parameters = {"var_id": str, "minimum": float, "maximum": float}

    def _get_result(self, primary_arg):
        ds = primary_arg
        var_id = self.kwargs["var_id"]
        mn, mx = self.kwargs["minimum"], self.kwargs["maximum"]

        score = 0
        if nc_util.is_variable_in_dataset(ds, var_id):
            score = 1

        if nc_util.variable_is_within_valid_bounds(ds, var_id, mn, mx):
            score += 1

        messages = []

        if score < self.out_of:
            messages.append(self.get_messages()[score])

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)


class _VariableTypeCheckBase(NCFileCheckBase):
    """
    Base (abstract) class for building variable type checks.
    """
    defaults = {}
    level = "HIGH"

    def _package_result(self, success):
        "Package up result depending on success (boolean)."
        messages = []

        if success:
            score = self.out_of
        else:
            score = 0
            messages.append(self.get_messages()[score])

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)


class VariableTypeCheck(_VariableTypeCheckBase):
    """
    The variable {var_id} must be of type: {dtype}.
    """
    short_name = "Variable data type: {var_id}"
    message_templates = ["The variable {var_id} was not of the required type: {dtype}"]
    required_parameters = {"var_id": str, "dtype": str}

    def _get_result(self, primary_arg):
        ds = primary_arg
        success = nc_util.check_variable_type(ds, self.kwargs["var_id"], self.kwargs["dtype"])
        return self._package_result(success)


class MainVariableTypeCheck(_VariableTypeCheckBase):
    """
    The main variable must be of type: {dtype}.
    """
    short_name = "Main variable data type"
    message_templates = ["Main variable was not of the required type: {dtype}"]
    required_parameters = {"dtype": str}

    def _get_result(self, primary_arg):
        ds = primary_arg
        success = nc_util.check_main_variable_type(ds, self.kwargs["dtype"])
        return self._package_result(success)


class NCVariableMetadataCheck(NCFileCheckBase):
    """
    The variable '{var_id}' must exist in the file with the attributes defined in the
    controlled vocabulary specified.
    """
    short_name = "Variable metadata: {var_id}"
    defaults = {}
    message_templates = ["Variable '{var_id}' not found in the file so cannot perform other checks.",
                         "Each variable attribute is checked separately."]
    level = "HIGH"
    required_parameters = {"var_id": str}

    def _check_nc_attribute(self, variable, attr, expected_value):
        """
        Checks that attribute ``attr`` is in the netCDF4 Variable and the value
        matches the expected value. Returns True for success and False for failure.

        :param variable: netCDF4 Variable instance.
        :param attr: attribute name (string).
        :param expected_value: value that we expect to find (varied type).
        :return: boolean.
        """
        value = getattr(variable, attr)
        KNOWN_IGNORES = ("<derived from file>",)

        if expected_value in KNOWN_IGNORES:
            return True

        if value == expected_value:
            return True

        return False


    def _get_result(self, primary_arg):
        ds = primary_arg
        var_id = self.kwargs["var_id"]

        # First, work out the overall 'out of' value based on number of attributes
        vocabs = ESSVocabs(*self.vocabulary_ref.split(":")[:2])
        lookup = "variable:{}".format(var_id)
        expected_attr_dict = vocabs.get_value(lookup, "data")

        self.out_of = 1 + len(expected_attr_dict) * 2
        score = 0

        # Check the variable first
        if var_id not in ds.variables:
            messages = self.get_messages()[:1]
            return Result(self.level, (score, self.out_of),
                          self.get_short_name(), messages)

        score += 1
        variable = ds.variables[var_id]
        messages = []

        # Check the variable attributes one-by-one
        for attr, expected_value in expected_attr_dict.items():
            if attr not in variable.ncattrs():
                messages.append("Required variable attribute '{}' is not present for "
                                "variable: '{}'.".format(attr, var_id))
            else:
                score += 1
                # Check the value of attribute
                check = self._check_nc_attribute(variable, attr, expected_value)
                if check:
                    score += 1
                else:
                    messages.append("Required variable attribute '{}' has incorrect value ('{}') "
                                    "for variable: '{}'. Value should be: '{}'.".format(attr,
                                                                                        getattr(variable, attr), var_id,
                                                                                        expected_value))

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)


class NetCDFFormatCheck(NCFileCheckBase):
    """
    The NetCDF sub-format must be: {format}.
    """
    short_name = "NetCDF sub-format: {format}"
    defaults = {}
    message_templates = ["The NetCDF sub-format must be: {format}."]
    level = "HIGH"
    required_parameters = {"format": str}

    def _get_result(self, primary_arg):
        ds = primary_arg
        file_format = getattr(ds, "file_format", None)

        score = 0
        if file_format == self.kwargs["format"]:
            score = 1

        messages = []

        if score < self.out_of:
            messages.append(self.get_messages()[score])

        return Result(self.level, (score, self.out_of),
                      self.get_short_name(), messages)


