"""Keep benchmark answer fixtures out of the installable tool distribution."""
from setuptools.command.build_py import build_py
EXCLUDED={'calibration','bias_checks','claim_controls','interventions','supplemental','_build'}
class ToolBuild(build_py):
    def find_package_modules(self,package,package_dir):
        return [item for item in super().find_package_modules(package,package_dir) if not (package=='editorial_guard' and item[1] in EXCLUDED)]
