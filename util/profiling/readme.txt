#!/usr/bin/python
from profilehooks import profile

class SampleClass:

    @profile
    def silly_fibonacci_example(self, n):
        """Return the n-th Fibonacci number.

        This is a method rather rather than a function just to illustrate that
        you can use the 'profile' decorator on methods as well as global
        functions.

        Needless to say, this is a contrived example.
        """
        if n < 1:
            raise ValueError('n must be >= 1, got %s' % n)
        if n in (1, 2):
            return 1
        else:
            return (self.silly_fibonacci_example(n - 1) +
                    self.silly_fibonacci_example(n - 2))


if __name__ == '__main__':
    fib = SampleClass().silly_fibonacci_example
    print fib(10)

Demonstration:

mg: ~$ python sample.py
55

*** PROFILER RESULTS ***
silly_fibonacci_example (sample.py:6)
function called 109 times

         325 function calls (5 primitive calls) in 0.004 CPU seconds

   Ordered by: internal time, call count

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    108/2    0.001    0.000    0.004    0.002 profilehooks.py:79(<lambda>)
    108/2    0.001    0.000    0.004    0.002 profilehooks.py:131(__call__)
    109/1    0.001    0.000    0.004    0.004 sample.py:6(silly_fibonacci_example)
        0    0.000             0.000          profile:0(profiler)

This decorator is useful when you do not want the profiler output to include time spent
waiting for user input in interactive programs, or time spent waiting for requests in
a network server.

In a similair vein you can produce code coverage reports for a function.

#!/usr/bin/python
from profilehooks import coverage

@coverage
def silly_factorial_example(n):
    """Return the factorial of n."""
    if n < 1:
        raise ValueError('n must be >= 1, got %s' % n)
    if n == 1:
        return 1
    else:
        return silly_factorial_example(n - 1) * n


if __name__ == '__main__':
    print silly_factorial_example(1)

Demonstration:

mg: ~$ python sample2.py
1

*** COVERAGE RESULTS ***
silly_factorial_example (sample2.py:5)
function called 1 times

       def silly_factorial_example(n):
           """Return the factorial of n."""
    1:     if n < 1:
>>>>>>         raise ValueError('n must be >= 1, got %s' % n)
    1:     if n == 1:
    1:         return 1
           else:
>>>>>>         return silly_factorial_example(n - 1) * n

2 lines were not executed.
