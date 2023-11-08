# This snippet was ~~stolen~~borrowed from https://github.com/gravitational/rbac-linter/blob/main/role_analyzer.py

import re
import sre_constants
import sre_parse
import z3 # type: ignore

# The Z3 regex matching all strings accepted by re1 but not re2.
# Formatted in camelcase to mimic Z3 regex API.
def Minus(re1 : z3.ReRef, re2 : z3.ReRef) -> z3.ReRef:
  return z3.Intersect(re1, z3.Complement(re2))

# The Z3 regex matching any character (currently only ASCII supported).
# Formatted in camelcase to mimic Z3 regex API.
def AnyChar() -> z3.ReRef:
  return z3.Range(chr(0), chr(127))
  #return z3.AllChar(z3.StringSort())

# Defines regex categories in Z3.
def category_regex(category : sre_constants._NamedIntConstant) -> z3.ReRef:
  if sre_constants.CATEGORY_DIGIT == category:
    return z3.Range('0', '9')
  elif sre_constants.CATEGORY_SPACE == category:
    return z3.Union(z3.Re(' '), z3.Re('\t'), z3.Re('\n'), z3.Re('\r'), z3.Re('\f'), z3.Re('\v'))
  elif sre_constants.CATEGORY_WORD == category:
    return z3.Union(z3.Range('a', 'z'), z3.Range('A', 'Z'), z3.Range('0', '9'), z3.Re('_'))
  else:
    raise NotImplementedError(f'ERROR: regex category {category} not yet implemented')
    
# Translates a specific regex construct into its Z3 equivalent.
def regex_construct_to_z3_expr(regex_construct) -> z3.ReRef:
  node_type, node_value = regex_construct
  if sre_constants.LITERAL == node_type: # a
    return z3.Re(chr(node_value))
  if sre_constants.NOT_LITERAL == node_type: # [^a]
    return Minus(AnyChar(), z3.Re(chr(node_value)))
  if sre_constants.SUBPATTERN == node_type:
    _, _, _, value = node_value
    return regex_to_z3_expr(value)
  elif sre_constants.ANY == node_type: # .
    return AnyChar()
  elif sre_constants.MAX_REPEAT == node_type:
    low, high, value = node_value
    if (0, 1) == (low, high): # a?
      return z3.Option(regex_to_z3_expr(value))
    elif (0, sre_constants.MAXREPEAT) == (low, high): # a*
      return z3.Star(regex_to_z3_expr(value))
    elif (1, sre_constants.MAXREPEAT) == (low, high): # a+
      return z3.Plus(regex_to_z3_expr(value))
    else: # a{3,5}, a{3}
      return z3.Loop(regex_to_z3_expr(value), low, high)
  elif sre_constants.IN == node_type: # [abc]
    first_subnode_type, _ = node_value[0]
    if sre_constants.NEGATE == first_subnode_type: # [^abc]
      return Minus(AnyChar(), z3.Union([regex_construct_to_z3_expr(value) for value in node_value[1:]]))
    else:
      return z3.Union([regex_construct_to_z3_expr(value) for value in node_value])
  elif sre_constants.BRANCH == node_type: # ab|cd
    _, value = node_value
    return z3.Union([regex_to_z3_expr(v) for v in value])
  elif sre_constants.RANGE == node_type: # [a-z]
    low, high = node_value
    return z3.Range(chr(low), chr(high))
  elif sre_constants.CATEGORY == node_type: # \d, \s, \w
    if sre_constants.CATEGORY_DIGIT == node_value: # \d
      return category_regex(node_value)
    elif sre_constants.CATEGORY_NOT_DIGIT == node_value: # \D
      return Minus(AnyChar(), category_regex(sre_constants.CATEGORY_DIGIT))
    elif sre_constants.CATEGORY_SPACE == node_value: # \s
      return category_regex(node_value)
    elif sre_constants.CATEGORY_NOT_SPACE == node_value: # \S
      return Minus(AnyChar(), category_regex(sre_constants.CATEGORY_SPACE))
    elif sre_constants.CATEGORY_WORD == node_value: # \w
      return category_regex(node_value)
    elif sre_constants.CATEGORY_NOT_WORD == node_value: # \W
      return Minus(AnyChar(), category_regex(sre_constants.CATEGORY_WORD))
    else:
      raise NotImplementedError(f'ERROR: regex category {node_value} not implemented')
  elif sre_constants.AT == node_type:
    if node_value in {sre_constants.AT_BEGINNING, sre_constants.AT_BEGINNING_STRING}: # ^a, \A
      raise NotImplementedError(f'ERROR: regex position {node_value} not implemented')
    elif sre_constants.AT_BOUNDARY == node_value: # \b
      raise NotImplementedError(f'ERROR: regex position {node_value} not implemented')
    elif sre_constants.AT_NON_BOUNDARY == node_value: # \B
      raise NotImplementedError(f'ERROR: regex position {node_value} not implemented')
    elif node_value in {sre_constants.AT_END, sre_constants.AT_END_STRING}: # a$, \Z
      raise NotImplementedError(f'ERROR: regex position {node_value} not implemented')
    else:
      raise NotImplementedError(f'ERROR: regex position {node_value} not implemented')
  else:
    raise NotImplementedError(f'ERROR: regex construct {regex_construct} not implemented')

# Translates a parsed regex into its Z3 equivalent.
# The parsed regex is a sequence of regex constructs (literals, *, +, etc.)
def regex_to_z3_expr(regex : sre_parse.SubPattern) -> z3.ReRef:
  if 0 == len(regex.data):
    raise ValueError('ERROR: regex is empty')
  elif 1 == len(regex.data):
    return regex_construct_to_z3_expr(regex[0])
  else:
    return z3.Concat([regex_construct_to_z3_expr(construct) for construct in regex.data])
