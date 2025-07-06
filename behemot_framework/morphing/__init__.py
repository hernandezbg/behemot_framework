# morphing/__init__.py
from .morphing_manager import MorphingManager
from .instant_triggers import InstantMorphTriggers
from .gradual_analyzer import GradualMorphAnalyzer
from .state_manager import MorphStateManager
from .transition_manager import TransitionManager

__all__ = [
    'MorphingManager',
    'InstantMorphTriggers', 
    'GradualMorphAnalyzer',
    'MorphStateManager',
    'TransitionManager'
]