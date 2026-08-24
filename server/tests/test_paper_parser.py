import pytest
from server.engine.paper_parser import parse_paper_structure

def test_parse_paper_structure():
    raw_text = r"""
Abstract
We present a new model.

Introduction
The dataset used is CIFAR-10. We set learning rate to 1e-4. The model achieves 95.5% accuracy.
We conclude that it works.

Methodology
\begin{equation}
L = - \log P(x)
\end{equation}

\begin{figure}
\caption{Model Architecture}
\end{figure}

\begin{table}
\caption{Results Table}
\end{table}

$$ \alpha = 0.5 $$
    """
    
    ast = parse_paper_structure(raw_text)
    
    assert len(ast['sections']) >= 3
    
    assert len(ast['datasets']) >= 1
    assert ast['datasets'][0]['name'].lower() == 'cifar-10'
    
    assert len(ast['claims']) >= 3
    types = [c['type'] for c in ast['claims']]
    assert 'parameter_statement' in types
    assert 'experimental_observation' in types
    assert 'scientific_conclusion' in types
    
    assert len(ast['equations']) == 2
    assert 'L' in ast['equations'][0]['variables']
    
    assert len(ast['figures']) == 1
    assert 'Architecture' in ast['figures'][0]['caption']
    
    assert len(ast['tables']) == 1
    
    assert len(ast['numbers']) >= 1
    values = [n['value'] for n in ast['numbers']]
    assert '95.5%' in values
