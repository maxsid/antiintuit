__all__ = [
    "TestSolverException",
    "AccountIsNotSubscribed",
    "NeedToPassAnotherTest",
    "IncorrectTestType",
    "CouldNotFindTest",
    "TestIsAlreadySolved",
    "TooManyCheckSessionIteration",
    "TestIsTemporarilyUnavailableForPassByAccount",
    "MaxIterationsReached"
]


class TestSolverException(Exception):
    pass


class IncorrectTestType(TestSolverException):
    pass


class NeedToPassAnotherTest(TestSolverException):
    def __init__(self, test, course_link_for_pass: str, *args):
        self.message = "Before to pass '{}' test need to pass the test on link '{}'.".format(
            str(test), course_link_for_pass)
        self.test = test
        self.course_link = course_link_for_pass
        super().__init__(self.message, *args)


class TestIsAlreadySolved(TestSolverException):
    pass


class AccountIsNotSubscribed(TestSolverException):
    pass


class CouldNotFindTest(TestSolverException):
    pass


class TooManyCheckSessionIteration(TestSolverException):
    pass


class TestIsTemporarilyUnavailableForPassByAccount(TestSolverException):
    def __init__(self, minutes_to_pass: int, *args):
        self.minutes_to_pass = minutes_to_pass
        super().__init__("The course is temporarily unavailable by account for a pass on the website about {} minutes."
                         .format(minutes_to_pass), *args)


class MaxIterationsReached(TestSolverException):
    pass
