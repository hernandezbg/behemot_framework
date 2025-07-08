# morphing/__init__.py
from .morphing_manager import MorphingManager
from .instant_triggers import InstantMorphTriggers
from .gradual_analyzer import GradualMorphAnalyzer
from .state_manager import MorphStateManager
from .transition_manager import TransitionManager
from .feedback_system import MorphingFeedbackSystem
from .ab_testing import MorphingABTesting, ABTestConfig, PredefinedABTests

__all__ = [
    'MorphingManager',
    'InstantMorphTriggers', 
    'GradualMorphAnalyzer',
    'MorphStateManager',
    'TransitionManager',
    'MorphingFeedbackSystem',
    'MorphingABTesting',
    'ABTestConfig',
    'PredefinedABTests'
]