
from model import get_datum_by_name

def get_text_and_commands(text):

    def _find_commands(text):
        rest = None
        if text.startswith('#'):
            text = text[1:]
            # Find the end
            import re
            split = re.split(r'[ \n]+', text, 1)
            command = split[0]
            if len(split) > 1:
                rest = split[1]
            if ':' in command:
                name, value = command.split(':', 1)
                if name == 'e':
                    yield(('equation', value))
                elif name.startswith('*'):
                    yield(('star_declaration', (name[1:], value)))
                elif name.startswith('@'):
                    yield (('at_declaration', (name[1:], value)))
                else:
                    yield (('declaration', (name, value)))
            elif '@' in command:
                yield('link', command[1:])
            else:
                yield(('evaluation', command))
        else:
            # Find the end
            #import re
            #split = re.split(r'[# \n]+', text, 1)
            split = text.split('#', 1)
            text = split[0]
            yield(('text'), text)
            if len(split) > 1:
                rest = '#{0}'.format(split[1])
        if rest:
            yield from _find_commands(rest)

    return list(_find_commands(text))

def evaluate(text, grid, clip=None):
    """Evaluate text, using grid and clip as context.

    Usually returns ex: [('value', 42)] but may not always?

    """
    # Here we eval code text. For example: 'foo+(2*&foo)'
    # assuming foo in the local is .65 and .42 on the secondary cursor
    # [('value', .65), ('token', '+'), ('token', '('), ('value', 2),
    # ('token', '*'), ('token', '&foo'), ('token', ')')
    # Note '&' not in tokens set, it checked for at beginning of words.
    tokens = {'+', '-', '/', '(', '*', ')'}
    result = []
    t = text
    while t:
        for index, token in enumerate(t):
            if token not in tokens and index != len(t) - 1:
                continue
            # Clip any preceding text
            non_token = t[0:index]
            if token not in tokens:
                # This is a statement that ends in a non-token, so the last
                # 'token' is not really a token.
                non_token = '{0}{1}'.format(non_token, token)
            # This is a non-token, it is expected to look up to a value.
            if non_token:
                # Is it already a value?
                is_text = False
                try:
                    non_token_value = int(non_token)
                except ValueError:
                    try:
                        non_token_value = float(non_token)
                    except ValueError:
                        non_token_value = non_token
                        is_text = True
                if is_text:
                    non_token_value = clip.grid.get_attr(non_token, clip=clip)
                result.append(('value', non_token_value))
            if token in tokens:  # In case last word is not a token.
                result.append(('token', token))
            t = t[index+1:]
            break

    # We've broken it up, now reduce it.
    def _reduce(l):
        # Any parens?
        left_paren_index = None
        right_paren_index = None
        for index, (kind, value) in enumerate(l):
            if kind == 'token':
                if '(' == value:
                    left_paren_index = index
                elif ')' == value:
                    right_paren_index = index
                    break

        if left_paren_index is not None and right_paren_index is not None:
            parens = _reduce(l[left_paren_index+1:right_paren_index])
            return _reduce(
                l[0:left_paren_index] + parens + l[right_paren_index+1:])

        # If no parens, see if you can reduce anything.
        new_result = []
        if len(l) >= 3 and \
            l[0][0] == 'value' and \
            l[1][0] == 'token' and l[1][1] in ['*', '-', '/', '+'] and \
            l[2][0] == 'value':
            t1 = l[0][1]
            t2 = l[2][1]
            op = l[1][1]
            if op == '*':
                value = t1 * t2
            elif op == '+':
                value = t1 + t2
            elif op == '/':
                value = float(t1) / float(t2)
            elif op == '-':
                value = t1 - t2
            new_result.append(('value', value))
            return _reduce(new_result + l[3:])
        # If we have a single string value left, see if it evaluates to
        # anything different than what we have now.
        elif len(l) == 1 and l[0][0] == 'value' and isinstance(l[0][1], str):
            sub_result = evaluate(l[0][1], grid, clip=clip)
            if sub_result != l:
                return _reduce(sub_result)
        return l

    return _reduce(result)
