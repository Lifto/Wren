
def pluralize(count, singular, plural='%ss'):
    """Pluralizes a number.

    >>> pluralize(22, 'goose', 'geese')
    '22 geese'

    If a list or set is given its length is used for the count.
    Notice the plural is not needed in the simple append-an-s case.

    >>> pluralize([1,2,3], 'bird')
    '3 birds'

    If the plural string contains a %s the singluar string is substituted in.

    >>> pluralize(5, 'potato', '%ses')
    '5 potatoes'

    None and 0 are acceptable inputs.

    >>> pluralize(None, 'fallacy', 'fallacies')
    'no fallacies'

    Negative input is acceptable.
    >>> pluralize(-1, 'unit')
    '-1 unit'
    >>> pluralize(-10, 'unit')
    '-10 units'

    """
    if hasattr(count, '__iter__'):
        count = len(count)
    if '%s' in plural:
        plural = plural % singular
    if count is None or count == 0:
        return "no %s" % plural
    elif count == 1 or count == -1:
        return "1 %s" % singular
    else:
        return "%s %s" % (count, plural)