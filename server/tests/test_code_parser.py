import pytest
from server.engine.code_parser import extract_code_symbols, parse_python_ast

def test_parse_python_ast_success():
    code = """
import os
from sys import path

learning_rate = 1e-4

class Model:
    def __init__(self):
        self.weights = []
        
    def train(self, data):
        self.optimizer = 'Adam'
        self.run_loop()
        
    def run_loop(self):
        pass

def load_data():
    return []
    """
    
    symbols = parse_python_ast(code, 'test.py')
    
    types = {s['type'] for s in symbols}
    assert 'Import' in types
    assert 'ImportFrom' in types
    assert 'Class' in types
    assert 'Function' in types
    assert 'Method (Model)' in types
    assert 'Assignment' in types
    assert 'Call' in types
    
    names = {s['symbol'] for s in symbols}
    assert 'os' in names
    assert 'sys.path' in names
    assert 'learning_rate' in names
    assert 'Model' in names
    assert 'train' in names
    assert 'run_loop' in names
    assert 'load_data' in names
    assert 'self.weights' in names
    assert 'self.optimizer' in names
    assert 'self.run_loop' in names # The call
    
def test_parse_python_ast_syntax_error():
    code = "def oops("
    symbols = parse_python_ast(code, 'bad.py')
    # Because of fallback, it shouldn't raise exception, but return empty or partial
    # The regex fallback doesn't catch `def oops(` since it's malformed, so it will be empty
    assert isinstance(symbols, list)
