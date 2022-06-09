Templating
==========

Monaco uses a custom templating library to inject values in files.

Available functions
-------------------

All the functions available inside the templates can be called by using the syntax ``..function::``. 

``..define::`` Allows to define a variable and assign it a value. If the variable already exists, the value is overwritten. Variables can then be used by writting them with the same syntax for functions. In the case of array variables, they can be indexed like python arrays.

.. code-block:: text
    :caption: Example

    ..define:: foo 10
    ..define:: bar Hello

    5 + 5 = ..foo::
    ..bar:: World
    ..arr::[0]


``..undef::`` Will undefine a variable. If the variable does not exist, it does nothing.

.. code-block:: text
    :caption: Example

    ..undef:: foo

``..if::`` and ``..ifnot::`` can be used to 

General example
---------------

.. code-block:: text

    ..define:: _abc 5

    ..ifnot:: _hello
    ..define:: _hello 20
    ..end::

    V1 1 gnd
    V.._abc:: 1 gnd

    ..if:: true
    This will remain
        ..if:: _abc
            This will too
        ..end::
    ..else::
    This will not remain
    ..end::

    Array..vals::[0] test

    ..for:: 0 .._abc::
    Iter_..it:: test
    ..end::

    ..undef:: _abc
    V.._abc:: 1 gnd

After executing the template, the following output is produced.


.. code-block:: text

    V1 1 gnd
    V5 1 gnd
    
    This will remain
            This will too

    Array_0 test

    Iter_0 test
    Iter_1 test
    Iter_2 test
    Iter_3 test
    Iter_4 test

    V.._abc:: 1 gnd
