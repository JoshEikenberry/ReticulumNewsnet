# Intentionally empty — do NOT use collect_submodules('RNS') here.
# It imports RNS at analysis time, which triggers the broken glob-based
# wildcard import before our build.py patch takes effect.
# All needed hidden imports are listed in newsnet.spec instead.
