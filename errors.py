class MissingRequiredArgumentError(Exception):
    ...
class CriteriaNotFilledError(Exception):
    def __init__(self, variable_name, variable_type):
        self.variable_name = variable_name
        self.variable_type = variable_type
