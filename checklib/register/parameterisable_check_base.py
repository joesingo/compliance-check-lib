from compliance_checker.base import BaseCheck, Dataset, Result
from checklib.code.errors import FileError, ParameterError


class ParameterisableCheckBase(object):

    # Define empty values for required arguments
    short_name = ""
    defaults = {}
    message_templates = []
    level = "HIGH"
    supported_ds = [Dataset]

    def __init__(self, kwargs, messages=None, level=None):
        self.kwargs = self.defaults.copy()
        self.kwargs.update(kwargs)
        self._define_messages(messages)
        self.out_of = len(self.messages)
        self.level = getattr(BaseCheck, level or self.level or "HIGH")

        self._setup()

    def _setup(self):
        "Child classes can override this to perform validation or modification of arguments."
        pass

    def _define_messages(self, messages=None):
        if messages:
            self.messages = messages
        else:
            self.messages = []
            for tmpl in self.message_templates:
                try:
                    self.messages.append(tmpl.format(**self.kwargs))
                except KeyError as ex:
                    self.messages = []
                    raise ParameterError("Keyword arguments for {short_name} "
                                         "check must include {keywrd}".
                                         format(short_name=self.short_name,
                                                keywrd=ex))

    def get_description(self):
        """
        Generates description of check based on doc string and kwargs.

        :return: description of check with kwargs inserted (if necessary) [string].
        """
        return self.__doc__.format(**self.kwargs)

    def get_short_name(self):
        return self.short_name.format(**self.kwargs)

    def get_message_templates(self):
        return self.message_templates

    def get_messages(self):
        # Note: messages are only provided for error/failure cases
        #       and SUCCESS is silent.
        return self.messages

    def do_check(self, primary_arg):
        """
        Calls the check with primary arg and keyword args provided during instantiation.

        :param primary_arg: main argument (object to check)
        :return: Result object (from compliance checker)
        """
        try:
            self._check_primary_arg(primary_arg)
        except FileError as ex:
            return Result(self.level, (0, self.out_of),
                          self.get_short_name(), ex.message)
        return self._get_result(primary_arg)

    def _get_result(self, primary_arg):
        raise NotImplementedError

    def _check_primary_arg(self, primary_arg):
        raise NotImplementedError
